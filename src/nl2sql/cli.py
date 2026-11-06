# -*- coding: utf-8 -*-
"""命令行入口：不启动 Web 服务也能验证整条链路。

    python -m nl2sql ask "2025 年各品类的销售额排名" --offline
    python -m nl2sql schema --db data/ecommerce.db
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace

from .config import Settings
from .executor import QueryError
from .guard import GuardError
from .llm import LLMError
from .schema import render_ddl
from .service import QueryService


def _print_table(columns: list[str], rows: list[dict]) -> None:
    if not columns:
        print("(无结果列)")
        return
    widths = {c: len(str(c)) for c in columns}
    for row in rows:
        for c in columns:
            widths[c] = max(widths[c], len(str(row.get(c, ""))))

    header = "  ".join(str(c).ljust(widths[c]) for c in columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))


def _build_service(args) -> QueryService:
    settings = Settings.from_env()
    db = getattr(args, "db", None)
    if db:
        settings = replace(settings, db_path=db)
    if getattr(args, "offline", False):
        settings = replace(settings, offline=True)
    return QueryService(settings)


def cmd_ask(args) -> int:
    service = _build_service(args)
    try:
        answer = service.ask(args.question, use_cache=not args.no_cache)
    except GuardError as exc:
        print(f"[护栏拦截] {exc}", file=sys.stderr)
        return 2
    except QueryError as exc:
        print(f"[执行失败] {exc}", file=sys.stderr)
        return 3
    except LLMError as exc:
        print(f"[模型调用失败] {exc}", file=sys.stderr)
        return 4

    if args.json:
        print(json.dumps(answer.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"问题：{answer.question}")
    print("SQL ：")
    print(answer.sql)
    print()
    _print_table(answer.columns, answer.rows)
    print()
    print(
        f"行数 {answer.row_count}"
        f"{'（已截断）' if answer.truncated else ''} ｜ "
        f"耗时 {answer.latency_ms:.1f}ms ｜ "
        f"缓存 {'命中' if answer.cached else '未命中'} ｜ "
        f"tokens {answer.tokens.get('total', 0)} ｜ "
        f"模型 {answer.model}"
    )
    for w in answer.warnings:
        print(f"提示：{w}")
    return 0


def cmd_schema(args) -> int:
    service = _build_service(args)
    tables, fp = service.schema()
    print(f"共 {len(tables)} 张表，结构指纹 {fp}")
    print()
    print(render_ddl(tables))
    return 0


def build_parser() -> argparse.ArgumentParser:
    # 子命令里也允许写 --db/--offline；用 SUPPRESS 避免覆盖写在子命令前面的值
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=argparse.SUPPRESS, help="SQLite 数据库路径")
    common.add_argument(
        "--offline",
        action="store_true",
        default=argparse.SUPPRESS,
        help="使用内置规则模型，不调用真实大模型",
    )

    parser = argparse.ArgumentParser(
        prog="nl2sql", description="把中文业务问题翻译成 SQL 并只读执行"
    )
    parser.add_argument("--db", default=None, help="SQLite 数据库路径")
    parser.add_argument(
        "--offline", action="store_true", help="使用内置规则模型，不调用真实大模型"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    ask_p = sub.add_parser("ask", parents=[common], help="提问并执行")
    ask_p.add_argument("question", help="中文业务问题")
    ask_p.add_argument("--json", action="store_true", help="输出完整 JSON")
    ask_p.add_argument("--no-cache", action="store_true", help="跳过缓存")
    ask_p.set_defaults(func=cmd_ask)

    schema_p = sub.add_parser("schema", parents=[common], help="打印表结构")
    schema_p.set_defaults(func=cmd_schema)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

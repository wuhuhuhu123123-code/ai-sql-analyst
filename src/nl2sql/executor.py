# -*- coding: utf-8 -*-
"""只读执行器：以 mode=ro 打开 SQLite，并对失控查询做时间熔断。"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote


class QueryError(RuntimeError):
    """SQL 执行失败（语法错误、表不存在等）。"""


class QueryTimeout(QueryError):
    """查询超过时间上限被中断。"""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False
    elapsed_ms: float = 0.0

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _readonly_uri(db_path: str) -> str:
    path = Path(db_path).resolve().as_posix()
    return f"file:{quote(path, safe='/:')}?mode=ro"


def run_query(
    db_path: str,
    sql: str,
    max_rows: int = 200,
    timeout_s: float = 3.0,
) -> QueryResult:
    """执行只读查询。结果最多 max_rows 行，多取一行用于判断是否被截断。"""
    if not Path(db_path).exists():
        raise QueryError(f"数据库文件不存在：{db_path}")

    started = time.perf_counter()
    try:
        conn = sqlite3.connect(_readonly_uri(db_path), uri=True, timeout=5.0)
    except sqlite3.Error as exc:  # pragma: no cover - 环境相关
        raise QueryError(f"无法打开数据库：{exc}") from exc

    conn.row_factory = sqlite3.Row
    deadline = started + timeout_s

    def _watchdog() -> int:
        if time.perf_counter() > deadline:
            raise QueryTimeout(f"查询超过 {timeout_s:g}s 上限，已中断")
        return 0

    conn.set_progress_handler(_watchdog, 1000)
    try:
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        fetched = cursor.fetchmany(max_rows + 1)
        truncated = len(fetched) > max_rows
        rows = [dict(r) for r in fetched[:max_rows]]
    except QueryTimeout:
        raise
    except sqlite3.Error as exc:
        raise QueryError(f"SQL 执行失败：{exc}") from exc
    finally:
        conn.close()

    return QueryResult(
        columns=columns,
        rows=rows,
        truncated=truncated,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )

# -*- coding: utf-8 -*-
"""SQL 安全护栏：只放行单条只读查询，并强制行数上限。

设计取舍：
* 不追求「完整 SQL 解析」，而是「词法级白名单 + 数据库层只读」双重约束。
  LLM 生成的 SQL 不可信，最坏情况下也必须在 mode=ro 连接上执行。
* 先用字符串扫描拦截注释与多语句，再校验首关键字与危险词，
  最后在缺少 LIMIT 时补一个上限，避免全表扫描把结果集撑爆。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_LEADING = ("select", "with")

# 出现即拒绝：写操作、DDL、事务控制、元数据探测
FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "upsert", "merge",
    "drop", "create", "alter", "truncate", "rename", "attach", "detach",
    "vacuum", "reindex", "analyze", "pragma", "grant", "revoke",
    "begin", "commit", "rollback", "savepoint", "release", "transaction",
    "load_extension", "readfile", "writefile", "edit",
}

_COMMENT_PATTERNS = ("--", "/*", "*/", "#")

# 聚合函数：若没有 GROUP BY，结果只会有一行，不必再补 LIMIT
_AGGREGATE = re.compile(r"\b(count|sum|avg|min|max|total)\s*\(", re.IGNORECASE)


class GuardError(ValueError):
    """SQL 未通过安全校验。"""


@dataclass(frozen=True)
class GuardResult:
    sql: str
    limit_injected: bool
    warnings: tuple[str, ...] = ()


def strip_code_fence(text: str) -> str:
    """去掉模型常见的 Markdown 代码围栏。"""
    s = text.strip()
    if s.startswith("```"):
        # ```sql\n...\n```
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def validate(sql: str, max_rows: int = 200) -> GuardResult:
    """校验并规范化 SQL，返回可直接执行的语句。"""
    if sql is None:
        raise GuardError("SQL 为空")
    s = strip_code_fence(sql)
    if not s:
        raise GuardError("SQL 为空")

    # 去掉结尾分号后再检查是否还存在语句分隔符
    s = s.rstrip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    if ";" in s:
        raise GuardError("仅允许执行单条语句")

    for marker in _COMMENT_PATTERNS:
        if marker in s:
            raise GuardError(f"SQL 中不允许出现注释或 # 字符：{marker}")

    lowered = s.lower()
    if not lowered.startswith(ALLOWED_LEADING):
        raise GuardError("仅允许 SELECT 或 WITH 开头的只读查询")

    if "sqlite_" in lowered:
        raise GuardError("不允许访问 sqlite_ 内部表")

    words = set(re.findall(r"[a-z_]+", lowered))
    hits = sorted(words & FORBIDDEN_KEYWORDS)
    if hits:
        raise GuardError(f"SQL 含被禁止的关键字：{', '.join(hits)}")

    warnings = []
    limit_injected = False
    single_row_aggregate = bool(_AGGREGATE.search(s)) and "group by" not in lowered
    if not single_row_aggregate and not re.search(r"\blimit\b", lowered):
        s = f"{s}\nLIMIT {int(max_rows)}"
        limit_injected = True
        warnings.append(f"未显式限制行数，已自动追加 LIMIT {int(max_rows)}")

    return GuardResult(sql=s, limit_injected=limit_injected, warnings=tuple(warnings))

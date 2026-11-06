# -*- coding: utf-8 -*-
"""编排层：把「问题 → 提示词 → 模型 → 护栏 → 只读执行」串成一条可测的链路。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import TTLCache, make_key
from .config import Settings
from .executor import QueryError, QueryResult, QueryTimeout, run_query
from .guard import GuardError, validate
from .llm import FakeLLM, LLMClient, LLMError, LLMResult
from .prompt import build_messages, extract_sql
from .schema import TableInfo, fingerprint, introspect, render_ddl


@dataclass
class Answer:
    question: str
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    cached: bool = False
    model: str = ""
    latency_ms: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "sql": self.sql,
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "truncated": self.truncated,
            "cached": self.cached,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "tokens": self.tokens,
            "warnings": self.warnings,
        }


def build_llm(settings: Settings):
    """按配置选择真实客户端或离线替身。"""
    if settings.offline or not settings.llm_api_key:
        return FakeLLM()
    return LLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
    )


class QueryService:
    def __init__(self, settings: Settings, llm=None, cache: TTLCache | None = None):
        self.settings = settings
        self.llm = llm if llm is not None else build_llm(settings)
        self.cache = cache or TTLCache(
            ttl_s=settings.cache_ttl_s, max_entries=settings.cache_max_entries
        )
        self._schema_mtime: float | None = None
        self._tables: list[TableInfo] = []
        self._fingerprint: str = ""

    # ---------------- schema ----------------
    def schema(self, refresh: bool = False) -> tuple[list[TableInfo], str]:
        """读取表结构；数据库文件未变化时复用上一次结果。"""
        path = Path(self.settings.db_path)
        if not path.exists():
            raise FileNotFoundError(f"数据库文件不存在：{path}")
        mtime = path.stat().st_mtime
        if refresh or self._schema_mtime != mtime or not self._tables:
            tables = introspect(self.settings.db_path)
            self._tables = tables
            self._fingerprint = fingerprint(tables)
            self._schema_mtime = mtime
        return self._tables, self._fingerprint

    # ---------------- main ----------------
    def ask(self, question: str, use_cache: bool = True) -> Answer:
        started = time.perf_counter()
        if not question or not question.strip():
            raise ValueError("问题不能为空")

        tables, fp = self.schema()
        key = make_key(question, fp, self.settings.llm_model)

        if use_cache:
            hit = self.cache.get(key)
            if hit is not None:
                cached = Answer(**hit)
                cached.cached = True
                cached.latency_ms = round((time.perf_counter() - started) * 1000, 2)
                return cached

        bundle = build_messages(question, render_ddl(tables))

        result: LLMResult = self.llm.chat(bundle.messages)
        raw_sql = extract_sql(result.text)
        guarded = validate(raw_sql, max_rows=self.settings.max_rows)

        try:
            qr: QueryResult = run_query(
                self.settings.db_path,
                guarded.sql,
                max_rows=self.settings.max_rows,
                timeout_s=self.settings.query_timeout_s,
            )
        except QueryTimeout as exc:
            raise QueryError(f"查询超时：{exc}") from exc

        answer = Answer(
            question=question,
            sql=guarded.sql,
            columns=qr.columns,
            rows=qr.rows,
            row_count=qr.row_count,
            truncated=qr.truncated,
            cached=False,
            model=result.model,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            tokens={
                "prompt": result.prompt_tokens,
                "completion": result.completion_tokens,
                "total": result.total_tokens,
            },
            warnings=list(guarded.warnings),
        )
        if answer.truncated:
            answer.warnings.append(f"结果超过 {self.settings.max_rows} 行，已截断")

        if use_cache:
            # 只缓存「可复现的答案」，cached 与 latency 属于调用现场信息
            snapshot = answer.to_dict()
            snapshot["cached"] = False
            snapshot["latency_ms"] = 0.0
            self.cache.set(key, snapshot)

        return answer

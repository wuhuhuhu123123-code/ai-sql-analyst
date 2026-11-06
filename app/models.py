# -*- coding: utf-8 -*-
"""HTTP 层的数据契约（Pydantic v2）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="中文业务问题，例如「2025 年各品类的销售额排名」",
        examples=["订单量最多的 5 个城市"],
    )
    use_cache: bool = Field(default=True, description="是否使用结果缓存")


class QueryResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    cached: bool
    model: str
    latency_ms: float
    tokens: dict[str, int]
    warnings: list[str]


class ColumnOut(BaseModel):
    name: str
    type: str
    pk: bool


class TableOut(BaseModel):
    name: str
    row_count: int
    columns: list[ColumnOut]


class SchemaResponse(BaseModel):
    fingerprint: str
    table_count: int
    column_count: int
    tables: list[TableOut]


class HealthResponse(BaseModel):
    status: str
    model: str
    offline: bool
    db_path: str
    version: str


class CacheResponse(BaseModel):
    hits: int
    misses: int
    size: int
    evictions: int
    expirations: int
    hit_rate: float

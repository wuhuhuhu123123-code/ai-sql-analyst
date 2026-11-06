# -*- coding: utf-8 -*-
"""FastAPI 适配层：路由很薄，业务逻辑都在 nl2sql.service 里。"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nl2sql import __version__
from nl2sql.config import Settings
from nl2sql.executor import QueryError
from nl2sql.guard import GuardError
from nl2sql.llm import LLMError
from nl2sql.service import QueryService

from .models import (
    CacheResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SchemaResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    app.state.settings = settings
    app.state.service = QueryService(settings)
    yield
    app.state.service = None


app = FastAPI(
    title="AI SQL Analyst",
    version=__version__,
    description="把中文业务问题翻译成 SQL，并在只读连接上执行。",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_process_time(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-ms"] = f"{elapsed:.2f}"
    return response


def _service(request: Request) -> QueryService:
    return request.app.state.service


@app.exception_handler(GuardError)
async def guard_error_handler(request: Request, exc: GuardError):
    return JSONResponse(
        status_code=400, content={"error": "guard_error", "detail": str(exc)}
    )


@app.exception_handler(QueryError)
async def query_error_handler(request: Request, exc: QueryError):
    return JSONResponse(
        status_code=422, content={"error": "query_error", "detail": str(exc)}
    )


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    return JSONResponse(
        status_code=502, content={"error": "llm_error", "detail": str(exc)}
    )


@app.get("/healthz", response_model=HealthResponse, tags=["meta"])
def healthz(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        model=settings.llm_model,
        offline=settings.offline or not settings.llm_api_key,
        db_path=settings.db_path,
        version=__version__,
    )


@app.get("/api/schema", response_model=SchemaResponse, tags=["data"])
def schema(request: Request) -> SchemaResponse:
    tables, fp = _service(request).schema()
    return SchemaResponse(
        fingerprint=fp,
        table_count=len(tables),
        column_count=sum(len(t.columns) for t in tables),
        tables=[
            {
                "name": t.name,
                "row_count": t.row_count,
                "columns": [
                    {"name": c.name, "type": c.type, "pk": c.pk} for c in t.columns
                ],
            }
            for t in tables
        ],
    )


@app.post("/api/query", response_model=QueryResponse, tags=["query"])
def query(payload: QueryRequest, request: Request) -> QueryResponse:
    answer = _service(request).ask(payload.question, use_cache=payload.use_cache)
    return QueryResponse(**answer.to_dict())


@app.get("/api/cache", response_model=CacheResponse, tags=["meta"])
def cache_stats(request: Request) -> CacheResponse:
    stats = _service(request).cache.stats()
    return CacheResponse(
        hits=stats.hits,
        misses=stats.misses,
        size=stats.size,
        evictions=stats.evictions,
        expirations=stats.expirations,
        hit_rate=stats.hit_rate,
    )

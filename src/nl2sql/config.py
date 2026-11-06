# -*- coding: utf-8 -*-
"""运行配置：全部来自环境变量，带安全默认值。"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """服务配置。所有字段都可以用同名大写环境变量覆盖。"""

    db_path: str = str(PROJECT_ROOT / "data" / "ecommerce.db")
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2
    cache_ttl_s: int = 600
    cache_max_entries: int = 256
    max_rows: int = 200
    query_timeout_s: float = 3.0
    offline: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        env = os.environ
        return replace(
            d,
            db_path=env.get("NL2SQL_DB_PATH", d.db_path),
            llm_base_url=env.get("LLM_BASE_URL", d.llm_base_url).rstrip("/"),
            llm_api_key=env.get("LLM_API_KEY", ""),
            llm_model=env.get("LLM_MODEL", d.llm_model),
            llm_timeout_s=float(env.get("LLM_TIMEOUT_S", d.llm_timeout_s)),
            cache_ttl_s=int(env.get("NL2SQL_CACHE_TTL_S", d.cache_ttl_s)),
            cache_max_entries=int(env.get("NL2SQL_CACHE_MAX", d.cache_max_entries)),
            max_rows=int(env.get("NL2SQL_MAX_ROWS", d.max_rows)),
            query_timeout_s=float(env.get("NL2SQL_QUERY_TIMEOUT_S", d.query_timeout_s)),
            offline=env.get("NL2SQL_OFFLINE", "").lower() in {"1", "true", "yes"},
        )

    def public_dict(self) -> dict:
        """可安全对外暴露的配置（不含 API Key）。"""
        return {
            "db_path": self.db_path,
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "max_rows": self.max_rows,
            "cache_ttl_s": self.cache_ttl_s,
            "offline": self.offline,
        }

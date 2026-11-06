# -*- coding: utf-8 -*-
"""表结构内省：把库表信息压缩成提示词里的 DDL 片段。"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from urllib.parse import quote
from pathlib import Path

# 不注入提示词的系统表前缀
_SKIP_PREFIXES = ("sqlite_",)

# 语义备注：让模型知道中文业务含义，比让模型猜列名更稳
TABLE_NOTES = {
    "customers": "客户表，一个客户一行",
    "products": "商品表，含品类 category 与单价 price",
    "orders": "订单主表，status 为订单状态（已完成/已取消/退款中）",
    "order_items": "订单明细表，一单多行商品；金额 = quantity * unit_price",
}


@dataclass
class ColumnInfo:
    name: str
    type: str
    pk: bool = False


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int = 0
    note: str = ""


def _connect_ro(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).resolve().as_posix()
    return sqlite3.connect(f"file:{quote(path, safe='/:')}?mode=ro", uri=True)


def introspect(db_path: str) -> list[TableInfo]:
    """读取库中的用户表、字段与行数。"""
    if not Path(db_path).exists():
        raise FileNotFoundError(f"数据库文件不存在：{db_path}")
    conn = _connect_ro(db_path)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            if not r[0].startswith(_SKIP_PREFIXES)
        ]
        tables: list[TableInfo] = []
        for name in names:
            cols = [
                ColumnInfo(name=r[1], type=(r[2] or "").upper(), pk=bool(r[5]))
                for r in conn.execute(f'PRAGMA table_info("{name}")')
            ]
            count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append(
                TableInfo(
                    name=name,
                    columns=cols,
                    row_count=count,
                    note=TABLE_NOTES.get(name, ""),
                )
            )
        return tables
    finally:
        conn.close()


def render_ddl(tables: list[TableInfo]) -> str:
    """渲染成紧凑 DDL：只保留列名/类型/主键，避免提示词过长。"""
    blocks = []
    for t in tables:
        cols = []
        for c in t.columns:
            cols.append(f"  {c.name} {c.type}" + (" PRIMARY KEY" if c.pk else ""))
        block = f"CREATE TABLE {t.name} (\n" + ",\n".join(cols) + "\n)"
        if t.note:
            block += f"\n-- 备注：{t.note}；当前约 {t.row_count} 行"
        blocks.append(block)
    return "\n\n".join(blocks)


def fingerprint(tables: list[TableInfo]) -> str:
    """表结构指纹，用于缓存键与结果可追溯。"""
    raw = "|".join(
        f"{t.name}:" + ",".join(f"{c.name}:{c.type}:{int(c.pk)}" for c in t.columns)
        for t in tables
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

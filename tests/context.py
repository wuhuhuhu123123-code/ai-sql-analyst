# -*- coding: utf-8 -*-
"""测试公共设施：把 src 加入导入路径，并生成一个微型数据库。"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(SRC),):
    if p not in sys.path:
        sys.path.insert(0, p)

MINI_SCHEMA = """
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL
);
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    price      REAL NOT NULL
);
CREATE TABLE orders (
    order_id    TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    order_date  TEXT NOT NULL,
    status      TEXT NOT NULL
);
CREATE TABLE order_items (
    item_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   TEXT NOT NULL,
    product_id TEXT NOT NULL,
    quantity   INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
"""

MINI_ROWS = {
    "customers": [
        ("C1", "张三", "长沙"),
        ("C2", "李四", "深圳"),
        ("C3", "王五", "长沙"),
    ],
    "products": [
        ("P1", "充电宝", "数码配件", 129.0),
        ("P2", "电热水壶", "家用电器", 199.0),
        ("P3", "数据线", "数码配件", 29.0),
    ],
    "orders": [
        ("O1", "C1", "2025-03-01", "已完成"),
        ("O2", "C2", "2025-03-02", "已完成"),
        ("O3", "C1", "2025-04-11", "已取消"),
        ("O4", "C3", "2025-05-06", "已完成"),
    ],
    "order_items": [
        ("O1", "P1", 2, 129.0),
        ("O1", "P3", 3, 29.0),
        ("O2", "P2", 1, 199.0),
        ("O3", "P3", 1, 29.0),
        ("O4", "P1", 1, 129.0),
    ],
}


MINI_COLUMNS = {
    "customers": "customer_id, name, city",
    "products": "product_id, name, category, price",
    "orders": "order_id, customer_id, order_date, status",
    "order_items": "order_id, product_id, quantity, unit_price",
}


def build_mini_db(path: Path | str | None = None) -> str:
    """在临时目录（或指定路径）创建一个带数据的只读测试库。"""
    if path is None:
        fd, name = tempfile.mkstemp(suffix=".db", prefix="nl2sql-test-")
        os.close(fd)
        path = name
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(MINI_SCHEMA)
        for table, rows in MINI_ROWS.items():
            placeholders = ",".join("?" * len(rows[0]))
            conn.executemany(
                f"INSERT INTO {table} ({MINI_COLUMNS[table]}) VALUES ({placeholders})",
                rows,
            )
        conn.commit()
    finally:
        conn.close()
    return str(path)


def temporary_db():
    """返回一个需要调用方负责清理的临时库路径。"""
    return build_mini_db()

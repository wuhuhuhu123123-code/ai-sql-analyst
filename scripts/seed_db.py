#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成演示用的电商 SQLite 数据库（确定性随机，可重复执行）。

用法：
    python scripts/seed_db.py --out data/ecommerce.db
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sqlite3
from pathlib import Path

SCHEMA = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    city          TEXT NOT NULL,
    signup_date   TEXT NOT NULL
);

CREATE TABLE products (
    product_id    TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    price         REAL NOT NULL
);

CREATE TABLE orders (
    order_id      TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES customers(customer_id),
    order_date    TEXT NOT NULL,
    status        TEXT NOT NULL,
    channel       TEXT NOT NULL
);

CREATE TABLE order_items (
    item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      TEXT NOT NULL REFERENCES orders(order_id),
    product_id    TEXT NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order ON order_items(order_id);
"""

CITIES = ["长沙", "深圳", "广州", "杭州", "成都", "武汉", "西安", "厦门"]
SURNAMES = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张")
GIVEN = ["伟", "芳", "娜", "敏", "静", "磊", "洋", "强", "军", "杰", "娟", "涛", "明", "超", "燕", "勇"]

CATEGORIES = {
    "数码配件": (["充电宝", "数据线", "手机壳", "蓝牙耳机", "支架"], (29, 399)),
    "家用电器": (["电热水壶", "吹风机", "加湿器", "电饭煲", "台灯"], (89, 799)),
    "食品饮料": (["坚果礼盒", "咖啡豆", "绿茶", "燕麦片", "蜂蜜"], (19, 129)),
    "运动户外": (["瑜伽垫", "跳绳", "运动水壶", "登山杖", "护膝"], (25, 269)),
    "家居日用": (["收纳箱", "拖把", "纸巾", "洗衣液", "垃圾桶"], (15, 159)),
}

ORDER_STATUS = ["已完成", "已完成", "已完成", "已取消", "退款中"]
CHANNELS = ["App", "小程序", "网页", "直播"]


def build(out_path: Path, seed: int = 42) -> dict:
    rng = random.Random(seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(out_path)
    conn.executescript(SCHEMA)

    # customers
    customers = []
    for i in range(1, 201):
        customers.append((
            f"C{i:04d}",
            rng.choice(SURNAMES) + rng.choice(GIVEN),
            rng.choice(CITIES),
            (dt.date(2024, 9, 1) + dt.timedelta(days=rng.randint(0, 500))).isoformat(),
        ))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?)", customers)

    # products
    products = []
    pid = 0
    for category, (names, (lo, hi)) in CATEGORIES.items():
        for name in names:
            for variant in ("标准版", "升级版"):
                pid += 1
                products.append((
                    f"P{pid:03d}",
                    f"{name}{variant}",
                    category,
                    round(rng.uniform(lo, hi), 1),
                ))
    conn.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    # orders + items
    orders, items = [], []
    item_id = 0
    start = dt.date(2025, 1, 1)
    for i in range(1, 1201):
        oid = f"O{i:05d}"
        odate = start + dt.timedelta(days=rng.randint(0, 540))
        orders.append((
            oid,
            rng.choice(customers)[0],
            odate.isoformat(),
            rng.choice(ORDER_STATUS),
            rng.choice(CHANNELS),
        ))
        for _ in range(rng.randint(1, 4)):
            item_id += 1
            product = rng.choice(products)
            qty = rng.randint(1, 3)
            items.append((oid, product[0], qty, product[3]))

    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?,?,?,?)",
        items,
    )
    conn.commit()

    counts = {
        "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "order_items": conn.execute("SELECT COUNT(*) FROM order_items").fetchone()[0],
    }
    conn.close()
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="生成演示电商数据库")
    ap.add_argument("--out", default="data/ecommerce.db")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    counts = build(Path(args.out), args.seed)
    print(f"已生成 {args.out}")
    for table, n in counts.items():
        print(f"  {table:12s} {n:>6d} 行")


if __name__ == "__main__":
    main()

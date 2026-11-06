# -*- coding: utf-8 -*-
"""提示词构造：System Prompt + 表结构 DDL + few-shot 示例。"""
from __future__ import annotations

import re
from dataclasses import dataclass

SYSTEM_PROMPT = """你是一名严谨的数据分析师，负责把中文业务问题翻译成 SQLite 查询语句。

规则：
1. 只输出一条 SQL 语句，不要输出解释、注释、Markdown 代码围栏或分号。
2. 只能查询下面给出的表，只能使用表中出现的列名。
3. 必须显式写 LIMIT，除非是聚合后的单行结果。
4. 不要使用 SELECT *，只选取回答该问题所需的列。
5. 金额相关计算使用 order_items.quantity * order_items.unit_price。
6. 需要中文可读的列名时使用 AS 起别名。
7. 无法用给定表回答时，输出：SELECT '无法回答：缺少所需数据' AS error;"""

FEW_SHOTS: tuple[tuple[str, str], ...] = (
    (
        "2025 年各品类的销售额排名",
        """SELECT p.category AS 品类,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS 销售额
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
JOIN products p ON p.product_id = oi.product_id
WHERE o.status = '已完成' AND o.order_date LIKE '2025%'
GROUP BY p.category
ORDER BY 销售额 DESC""",
    ),
    (
        "订单量最多的 5 个城市",
        """SELECT c.city AS 城市,
       COUNT(DISTINCT o.order_id) AS 订单量
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
GROUP BY c.city
ORDER BY 订单量 DESC
LIMIT 5""",
    ),
    (
        "已完成订单的平均客单价",
        """SELECT ROUND(SUM(oi.quantity * oi.unit_price) /
             COUNT(DISTINCT o.order_id), 2) AS 平均客单价
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status = '已完成'""",
    ),
)


@dataclass
class PromptBundle:
    messages: list[dict[str, str]]
    estimated_chars: int


def build_messages(question: str, ddl: str) -> PromptBundle:
    """组装 OpenAI 兼容的 messages 数组。"""
    question = question.strip()
    if not question:
        raise ValueError("问题不能为空")

    examples = "\n\n".join(
        f"问题：{q}\nSQL：{s}" for q, s in FEW_SHOTS
    )
    user_content = (
        f"数据库表结构：\n{ddl}\n\n"
        f"参考示例：\n{examples}\n\n"
        f"请为下面的问题生成一条 SQL：\n问题：{question}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    chars = sum(len(m["content"]) for m in messages)
    return PromptBundle(messages=messages, estimated_chars=chars)


_SQL_START = re.compile(r"\b(select|with)\b", re.IGNORECASE)


def extract_sql(raw: str) -> str:
    """从模型回复里抽出 SQL：去围栏、去前缀说明、截到第一个分号。"""
    if not raw or not raw.strip():
        raise ValueError("模型返回为空")
    text = raw.strip()

    fence = re.search(r"```(?:sql)?\s*(.+?)```", text, re.IGNORECASE | re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    match = _SQL_START.search(text)
    if match:
        text = text[match.start():]

    text = text.strip()
    if ";" in text:
        text = text.split(";")[0]
    return text.strip()

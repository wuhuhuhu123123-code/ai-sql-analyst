# -*- coding: utf-8 -*-
"""提示词与 SQL 抽取测试。"""
from __future__ import annotations

import unittest

from context import *  # noqa: F401,F403

from nl2sql.prompt import FEW_SHOTS, build_messages, extract_sql


class TestBuildMessages(unittest.TestCase):
    def test_roles_and_content(self):
        bundle = build_messages("各品类销售额", "CREATE TABLE orders (order_id TEXT);")
        roles = [m["role"] for m in bundle.messages]
        self.assertEqual(roles, ["system", "user"])
        self.assertIn("CREATE TABLE orders", bundle.messages[1]["content"])
        self.assertIn("各品类销售额", bundle.messages[1]["content"])

    def test_few_shots_included(self):
        bundle = build_messages("任意问题", "DDL")
        self.assertTrue(len(FEW_SHOTS) >= 3)
        for question, _ in FEW_SHOTS:
            self.assertIn(question, bundle.messages[1]["content"])

    def test_system_prompt_mentions_readonly_rules(self):
        bundle = build_messages("q", "DDL")
        system = bundle.messages[0]["content"]
        self.assertIn("只输出一条 SQL", system)
        self.assertIn("LIMIT", system)

    def test_empty_question_rejected(self):
        with self.assertRaises(ValueError):
            build_messages("   ", "DDL")

    def test_char_estimate_positive(self):
        bundle = build_messages("q", "DDL")
        self.assertGreater(bundle.estimated_chars, len("DDL"))


class TestExtractSql(unittest.TestCase):
    def test_plain_sql(self):
        self.assertEqual(extract_sql("SELECT 1"), "SELECT 1")

    def test_fenced_sql(self):
        raw = "```sql\nSELECT city FROM customers\n```"
        self.assertEqual(extract_sql(raw), "SELECT city FROM customers")

    def test_leading_chinese_explanation_removed(self):
        raw = "查询语句如下：\nSELECT city FROM customers"
        self.assertEqual(extract_sql(raw), "SELECT city FROM customers")

    def test_trailing_semicolon_and_extra_text_cut(self):
        raw = "SELECT 1;\n以上语句可以直接执行"
        self.assertEqual(extract_sql(raw), "SELECT 1")

    def test_with_cte(self):
        raw = "```\nWITH t AS (SELECT 1 AS a) SELECT a FROM t\n```"
        self.assertTrue(extract_sql(raw).startswith("WITH"))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            extract_sql("   ")


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""SQL 护栏测试：这是整个项目最该被覆盖的部分。"""
from __future__ import annotations

import unittest

from context import *  # noqa: F401,F403  (设置 sys.path)

from nl2sql.guard import GuardError, strip_code_fence, validate


class TestValidate(unittest.TestCase):
    def test_plain_select_passes(self):
        result = validate("SELECT city FROM customers LIMIT 5", max_rows=200)
        self.assertIn("LIMIT 5", result.sql)
        self.assertFalse(result.limit_injected)

    def test_limit_injected_when_missing(self):
        result = validate("SELECT city FROM customers", max_rows=50)
        self.assertTrue(result.limit_injected)
        self.assertTrue(result.sql.strip().lower().endswith("limit 50"))
        self.assertTrue(result.warnings)

    def test_with_cte_allowed(self):
        sql = "WITH t AS (SELECT city FROM customers) SELECT city FROM t LIMIT 3"
        self.assertTrue(validate(sql).sql.startswith("WITH"))

    def test_markdown_fence_removed(self):
        sql = "```sql\nSELECT city FROM customers LIMIT 2\n```"
        self.assertEqual(validate(sql).sql.lower().count("select"), 1)

    def test_multiple_statements_rejected(self):
        with self.assertRaises(GuardError):
            validate("SELECT city FROM customers; DROP TABLE customers")

    def test_trailing_semicolon_is_fine(self):
        self.assertIn("SELECT", validate("SELECT city FROM customers LIMIT 1;").sql)

    def test_comment_rejected(self):
        with self.assertRaises(GuardError):
            validate("SELECT city -- 这里注释\nFROM customers")

    def test_delete_rejected(self):
        with self.assertRaises(GuardError):
            validate("DELETE FROM orders")

    def test_insert_rejected(self):
        with self.assertRaises(GuardError):
            validate("INSERT INTO orders VALUES ('x','y','2025-01-01','已完成')")

    def test_pragma_rejected(self):
        with self.assertRaises(GuardError):
            validate("PRAGMA table_info(orders)")

    def test_sqlite_internal_table_rejected(self):
        with self.assertRaises(GuardError):
            validate("SELECT name FROM sqlite_master")

    def test_empty_rejected(self):
        for bad in ("", "   ", None):
            with self.assertRaises(GuardError):
                validate(bad)

    def test_statement_must_start_with_select_or_with(self):
        with self.assertRaises(GuardError):
            validate("EXPLAIN SELECT 1")

    def test_replace_function_is_not_blocked(self):
        """REPLACE 作为字符串函数是合法只读用法，不应被误杀。"""
        sql = "SELECT REPLACE(city, '长沙', '长沙市') AS c FROM customers LIMIT 3"
        self.assertTrue(validate(sql).sql)

    def test_single_row_aggregate_needs_no_limit(self):
        result = validate("SELECT COUNT(*) AS n FROM orders")
        self.assertFalse(result.limit_injected)

    def test_grouped_aggregate_still_gets_limit(self):
        result = validate("SELECT city, COUNT(*) AS n FROM customers GROUP BY city")
        self.assertTrue(result.limit_injected)


class TestStripCodeFence(unittest.TestCase):
    def test_plain_text_untouched(self):
        self.assertEqual(strip_code_fence("  SELECT 1  "), "SELECT 1")

    def test_fence_with_language(self):
        self.assertEqual(strip_code_fence("```sql\nSELECT 1\n```"), "SELECT 1")

    def test_fence_without_language(self):
        self.assertEqual(strip_code_fence("```\nSELECT 1\n```"), "SELECT 1")


if __name__ == "__main__":
    unittest.main()

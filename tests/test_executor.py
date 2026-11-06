# -*- coding: utf-8 -*-
"""执行器测试：只读约束、截断标记、错误分类。"""
from __future__ import annotations

import os
import unittest

from context import build_mini_db

from nl2sql.executor import QueryError, run_query


class TestRunQuery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = build_mini_db()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db):
            os.unlink(cls.db)

    def test_returns_rows_and_columns(self):
        result = run_query(self.db, "SELECT city FROM customers ORDER BY city")
        self.assertEqual(result.columns, ["city"])
        self.assertEqual(result.row_count, 3)
        self.assertEqual({r["city"] for r in result.rows}, {"长沙", "深圳"})

    def test_aggregation(self):
        sql = """
        SELECT p.category AS category, SUM(oi.quantity * oi.unit_price) AS amount
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        GROUP BY p.category
        ORDER BY amount DESC
        """
        result = run_query(self.db, sql)
        self.assertEqual(result.columns, ["category", "amount"])
        self.assertEqual(result.rows[0]["category"], "数码配件")

    def test_truncation_flag(self):
        result = run_query(self.db, "SELECT * FROM order_items", max_rows=2)
        self.assertTrue(result.truncated)
        self.assertEqual(result.row_count, 2)

    def test_elapsed_ms_recorded(self):
        result = run_query(self.db, "SELECT 1 AS one")
        self.assertGreaterEqual(result.elapsed_ms, 0.0)

    def test_write_is_rejected_by_readonly_connection(self):
        with self.assertRaises(QueryError):
            run_query(self.db, "DELETE FROM orders")

    def test_bad_sql_raises_query_error(self):
        with self.assertRaises(QueryError):
            run_query(self.db, "SELECT no_such_column FROM orders")

    def test_missing_db_raises_query_error(self):
        with self.assertRaises(QueryError):
            run_query("Z:/definitely/not/here.db", "SELECT 1")


if __name__ == "__main__":
    unittest.main()

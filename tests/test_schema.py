# -*- coding: utf-8 -*-
"""表结构内省测试。"""
from __future__ import annotations

import os
import unittest

from context import build_mini_db

from nl2sql.schema import fingerprint, introspect, render_ddl


class TestIntrospect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = build_mini_db()
        cls.tables = introspect(cls.db)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db):
            os.unlink(cls.db)

    def test_finds_all_user_tables(self):
        names = [t.name for t in self.tables]
        self.assertEqual(names, ["customers", "order_items", "orders", "products"])

    def test_columns_and_row_counts(self):
        orders = next(t for t in self.tables if t.name == "orders")
        self.assertEqual(len(orders.columns), 4)
        self.assertEqual(orders.row_count, 4)
        self.assertTrue(orders.columns[0].pk)

    def test_render_ddl_contains_notes(self):
        ddl = render_ddl(self.tables)
        self.assertIn("CREATE TABLE orders", ddl)
        self.assertIn("备注", ddl)

    def test_fingerprint_stable_across_calls(self):
        self.assertEqual(fingerprint(self.tables), fingerprint(introspect(self.db)))

    def test_fingerprint_changes_when_schema_changes(self):
        other = [t for t in self.tables if t.name != "orders"]
        self.assertNotEqual(fingerprint(self.tables), fingerprint(other))

    def test_missing_db_raises(self):
        with self.assertRaises(FileNotFoundError):
            introspect("Z:/definitely/not/here.db")


if __name__ == "__main__":
    unittest.main()

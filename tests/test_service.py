# -*- coding: utf-8 -*-
"""编排层端到端测试：用 FakeLLM 替换真实模型，链路其余部分全部真实执行。"""
from __future__ import annotations

import os
import unittest

from context import build_mini_db

from nl2sql.cache import TTLCache
from nl2sql.config import Settings
from nl2sql.guard import GuardError
from nl2sql.executor import QueryError
from nl2sql.llm import CITY_SQL, FakeLLM
from nl2sql.service import QueryService


class ServiceTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = build_mini_db()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db):
            os.unlink(cls.db)

    def make_service(self, responses=None, max_rows: int = 200, **llm_kwargs) -> QueryService:
        settings = Settings(db_path=self.db, offline=True, max_rows=max_rows)
        llm = FakeLLM(responses=list(responses or []), **llm_kwargs)
        cache = TTLCache(ttl_s=60, max_entries=16)
        return QueryService(settings, llm=llm, cache=cache)


class TestAsk(ServiceTestBase):
    def test_end_to_end_answer(self):
        service = self.make_service()
        answer = service.ask("订单量最多的 5 个城市")
        self.assertEqual(answer.columns, ["城市", "订单量"])
        self.assertGreater(answer.row_count, 0)
        self.assertTrue(answer.sql.startswith("SELECT"))
        self.assertFalse(answer.cached)
        self.assertGreater(answer.tokens["total"], 0)

    def test_answer_rows_match_db(self):
        service = self.make_service()
        answer = service.ask("订单量最多的 5 个城市")
        cities = {r["城市"] for r in answer.rows}
        self.assertTrue(cities.issubset({"长沙", "深圳"}))

    def test_second_call_hits_cache(self):
        service = self.make_service()
        first = service.ask("订单量最多的 5 个城市")
        second = service.ask("订单量最多的 5 个城市")
        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(len(service.llm.calls), 1)
        self.assertEqual(first.sql, second.sql)
        self.assertEqual(first.rows, second.rows)

    def test_cache_can_be_bypassed(self):
        service = self.make_service()
        service.ask("订单量最多的 5 个城市", use_cache=False)
        service.ask("订单量最多的 5 个城市", use_cache=False)
        self.assertEqual(len(service.llm.calls), 2)

    def test_schema_exposed(self):
        tables, fp = self.make_service().schema()
        self.assertEqual(len(tables), 4)
        self.assertEqual(len(fp), 16)

    def test_empty_question_rejected(self):
        with self.assertRaises(ValueError):
            self.make_service().ask("  ")


class TestFailureModes(ServiceTestBase):
    def test_guard_blocks_write_sql_from_model(self):
        service = self.make_service(responses=["DELETE FROM orders"])
        with self.assertRaises(GuardError):
            service.ask("删掉所有订单")

    def test_second_statement_is_dropped_before_guard(self):
        """模型返回多语句时，抽取阶段只保留第一条，后续语句不会被执行。"""
        service = self.make_service(
            responses=["SELECT city FROM customers LIMIT 1; DROP TABLE orders"]
        )
        answer = service.ask("城市")
        self.assertNotIn("DROP", answer.sql.upper())
        self.assertEqual(answer.row_count, 1)

    def test_bad_sql_surfaces_as_query_error(self):
        service = self.make_service(responses=["SELECT nope FROM customers"])
        with self.assertRaises(QueryError):
            service.ask("不存在的列")

    def test_limit_injected_warning_present(self):
        service = self.make_service(responses=["SELECT city FROM customers"])
        answer = service.ask("所有城市")
        self.assertIn("LIMIT", answer.sql.upper())
        self.assertTrue(answer.warnings)

    def test_truncation_warning_after_limit(self):
        service = self.make_service(
            responses=["SELECT item_id FROM order_items LIMIT 5"], max_rows=2
        )
        answer = service.ask("所有明细")
        self.assertTrue(answer.truncated)
        self.assertEqual(answer.row_count, 2)
        self.assertTrue(any("截断" in w for w in answer.warnings))


class TestOfflineRules(ServiceTestBase):
    def test_rule_router_picks_category_sql(self):
        service = self.make_service()
        answer = service.ask("各品类的销售额排名")
        self.assertIn("品类", "".join(answer.columns))
        self.assertGreater(answer.row_count, 0)

    def test_unknown_question_falls_back_to_trend(self):
        service = self.make_service()
        answer = service.ask("随便问一个没命中关键词的问题")
        self.assertEqual(answer.columns, ["月份", "订单量"])


if __name__ == "__main__":
    unittest.main()

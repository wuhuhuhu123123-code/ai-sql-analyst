# -*- coding: utf-8 -*-
"""缓存测试：命中率、过期、容量淘汰、键的稳定性。"""
from __future__ import annotations

import unittest

from context import *  # noqa: F401,F403

from nl2sql.cache import TTLCache, make_key


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestMakeKey(unittest.TestCase):
    def test_same_inputs_same_key(self):
        a = make_key("订单量最多的城市", "fp1", "m1")
        b = make_key("  订单量最多的城市  ", "fp1", "m1")
        self.assertEqual(a, b)

    def test_different_schema_changes_key(self):
        self.assertNotEqual(
            make_key("q", "fp1", "m1"), make_key("q", "fp2", "m1")
        )

    def test_different_model_changes_key(self):
        self.assertNotEqual(
            make_key("q", "fp1", "m1"), make_key("q", "fp1", "m2")
        )


class TestTTLCache(unittest.TestCase):
    def test_set_then_get(self):
        cache = TTLCache(ttl_s=10, max_entries=4, clock=FakeClock())
        cache.set("k", {"v": 1})
        self.assertEqual(cache.get("k"), {"v": 1})

    def test_expiry(self):
        clock = FakeClock()
        cache = TTLCache(ttl_s=5, max_entries=4, clock=clock)
        cache.set("k", "v")
        clock.advance(6)
        self.assertIsNone(cache.get("k"))
        self.assertEqual(cache.stats().expirations, 1)

    def test_lru_eviction(self):
        cache = TTLCache(ttl_s=100, max_entries=2, clock=FakeClock())
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # a 变成最近使用
        cache.set("c", 3)  # 淘汰 b
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.stats().evictions, 1)

    def test_stats_hit_rate(self):
        cache = TTLCache(ttl_s=100, max_entries=8, clock=FakeClock())
        cache.set("k", 1)
        cache.get("k")
        cache.get("miss")
        stats = cache.stats()
        self.assertEqual((stats.hits, stats.misses), (1, 1))
        self.assertAlmostEqual(stats.hit_rate, 0.5)

    def test_clear(self):
        cache = TTLCache(ttl_s=100, max_entries=8, clock=FakeClock())
        cache.set("k", 1)
        cache.clear()
        self.assertEqual(cache.stats().size, 0)


if __name__ == "__main__":
    unittest.main()

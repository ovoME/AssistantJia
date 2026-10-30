"""推荐新书批次的质量边界；不读取真实读者数据。"""
import random
import json
import subprocess
import sys
import unittest

from data.datasets import FIXTURE_ROOT
from data.recommendation import Recommender, recommendation_topic
from test_recommendation import book, engine_for


class DiscoveryTests(unittest.TestCase):
    def test_anonymous_discovery_is_not_ordered_by_borrow_count(self):
        books = [book(i) for i in range(1, 9)]
        pairs = [("a", 0)] * 50 + [("b", i) for i in range(1, 8)]
        engine, _, _ = engine_for(books, pairs)
        outcomes = [engine.discover(limit=3, rng=random.Random(seed)) for seed in range(20)]
        self.assertGreater(len({tuple(row["book_key"] for row in batch) for batch in outcomes}), 1)
        self.assertTrue(any(batch[0]["count"] < 50 for batch in outcomes))
        self.assertTrue(all(len({row["book_key"] for row in batch}) == 3 for batch in outcomes))
        self.assertTrue(all(row["strategy"] == "discovery" for batch in outcomes for row in batch))

    def test_duplicate_borrow_events_do_not_change_discovery(self):
        books = [book(i) for i in range(1, 9)]
        pairs = [("target", 0), ("peer", 0), ("peer", 1)] + [("other", i) for i in range(2, 8)]
        original, _, _ = engine_for(books, pairs)
        repeated, _, _ = engine_for(books, pairs + [("peer", 1)] * 100)
        for reader in (None, "target"):
            first = original.discover(reader, 5, rng=random.Random(17))
            second = repeated.discover(reader, 5, rng=random.Random(17))
            self.assertEqual([(r["book_key"], r["score"]) for r in first],
                             [(r["book_key"], r["score"]) for r in second])
        self.assertNotIn(books[0]["book_key"], {r["book_key"] for r in original.discover("target", 7)})

    def test_topic_filters_and_unmatched_topic_stays_empty(self):
        engine = Recommender.from_directory(FIXTURE_ROOT)
        python = engine.discover(query="请给我推荐几本关于 Python 的书", limit=10)
        self.assertTrue(python)
        self.assertTrue(all("python" in row["title"].lower() for row in python))
        computers = engine.discover(query="推荐计算机类图书", limit=10)
        self.assertTrue(computers)
        self.assertTrue(all(row["call_number"].startswith("TP3") or "计算机" in row["title"] for row in computers))
        self.assertEqual(engine.discover(query="推荐不存在的xyz主题的书"), [])
        self.assertEqual(recommendation_topic("最近大家都在看什么热门好书，推荐几本"), "")
        self.assertEqual(recommendation_topic("最近有什么好书推荐"), "")
        self.assertEqual(recommendation_topic("图书馆有什么好书推荐"), "")
        self.assertEqual(recommendation_topic("你能推荐三本书吗"), "")
        self.assertEqual(recommendation_topic("推荐 3 本关于Python的书"), "python")
        self.assertEqual(recommendation_topic("推荐点书"), "")
        self.assertEqual(recommendation_topic("推荐适合我的书"), "")
        self.assertEqual(recommendation_topic("推荐图书馆学的书"), "图书馆学")
        self.assertEqual(recommendation_topic("推荐书法的书"), "书法")
        self.assertEqual(recommendation_topic("推荐《平凡的世界》"), "平凡的世界")
        self.assertEqual(recommendation_topic("推荐《看见》"), "看见")
        self.assertEqual(recommendation_topic("推荐机器学习的书"), "机器学习")
        self.assertEqual(recommendation_topic("推荐看见这本书"), "看见")
        self.assertEqual(recommendation_topic("推荐C++的书"), "c++")
        self.assertEqual(engine.discover(query="推荐《平凡的世界》")[0]["title"], "平凡的世界")
        self.assertTrue(all(row["call_number"].startswith("TP")
                            for row in engine.discover(category="TP", limit=20)))

    def test_cli_defaults_to_topic_aware_discovery(self):
        result = subprocess.run([sys.executable, "-S", "-W", "error", "-m", "data.scripts.recommend",
                                 "--data-dir", str(FIXTURE_ROOT), "--query", "Python", "--limit", "5"],
                                capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)["data"]
        self.assertTrue(rows)
        self.assertTrue(all("python" in row["title"].lower() and row["strategy"] == "topic" for row in rows))

    def test_avoid_previous_batch_without_losing_candidates(self):
        engine = Recommender.from_directory(FIXTURE_ROOT)
        first = engine.discover(limit=5, rng=random.Random(1))
        previous = {row["book_key"] for row in first}
        second = engine.discover(limit=5, avoid=previous, rng=random.Random(2))
        self.assertFalse(previous & {row["book_key"] for row in second})
        small, _, _ = engine_for([book(i) for i in range(1, 4)], [("a", i) for i in range(3)])
        rows = small.discover(limit=5, avoid={item["book_key"] for item in [book(1), book(2)]})
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["book_key"], book(3)["book_key"])
        self.assertEqual(len({row["book_key"] for row in rows}), 3)

    def test_empty_or_fully_read_catalog_and_invalid_arguments(self):
        empty = Recommender([], [])
        self.assertEqual(empty.discover(), [])
        books = [book(1), book(2)]
        engine, _, _ = engine_for(books, [("target", 0), ("target", 1)])
        self.assertEqual(engine.discover("target"), [])
        for args in ({"limit": 0}, {"reader_id": 1}, {"query": 1}, {"query": "x" * 2001}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                engine.discover(**args)

    def test_new_candidates_are_preferred_even_when_the_previous_batch_was_relevant(self):
        books = [book(1, "I")] + [book(i, "I") for i in range(2, 7)] + [book(7, "F")]
        engine, _, _ = engine_for(books, [("target", 0)] + [("other", i) for i in range(1, 7)])
        first = engine.discover("target", 5, rng=random.Random(1))
        previous = {row["book_key"] for row in first}
        second = engine.discover("target", 5, avoid=previous, rng=random.Random(2))
        self.assertNotEqual(previous, {row["book_key"] for row in second})
        self.assertNotIn(books[0]["book_key"], {row["book_key"] for row in second})

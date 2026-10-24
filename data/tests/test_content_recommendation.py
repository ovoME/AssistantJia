"""以独立构造的书目关系检查内容召回、回退和隔离评估。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data.content import ContentIndex, features
from data.recommendation import Recommender
from data.scripts.compare_recommendations import compare, split_readers
from data.scripts.validate_recommendations import _digest, build_holdout
from data.tests.test_recommendation import book, engine_for, write_source


class ContentRecommendationTests(unittest.TestCase):
    def fixture(self):
        books = [
            book(1, "T", "TP311.1/1", title="Python程序设计", author="甲"),
            book(2, "T", "TP311.1/8", title="Python编程实践", author="乙"),
            book(3, "I", "I247/1", title="海岛故事", author="丙"),
            book(4, "F", "F123/1", title="城市经济", author="丁"),
        ]
        return engine_for(books, [("target", 0), ("other", 2)] * 2)

    def test_zero_borrow_book_can_be_recommended_from_content(self):
        engine, books, _ = self.fixture()
        rows = engine.recommend("target", limit=1)
        self.assertEqual(rows[0]["book_key"], books[1]["book_key"])
        self.assertEqual(rows[0]["count"], 0)
        self.assertEqual(rows[0]["strategy"], "content")
        self.assertNotIn("target", json.dumps(rows))

    def test_content_does_not_override_seen_filter_or_requested_category(self):
        engine, books, _ = self.fixture()
        self.assertNotIn(books[0]["book_key"], [row["book_key"] for row in engine.recommend("target")])
        rows = engine.recommend("target", category="I")
        self.assertEqual([row["book_key"] for row in rows], [books[2]["book_key"]])
        self.assertNotEqual(rows[0]["strategy"], "content")
        self.assertEqual(engine.recommend("target", category="Z"), [])

    def test_cold_start_and_explicit_baselines_keep_popularity(self):
        engine, books, _ = self.fixture()
        for strategy in ("hybrid", "popular", "collaborative", "category"):
            self.assertEqual(engine.recommend(None, strategy=strategy)[0]["book_key"], books[0]["book_key"])
        for strategy in ("popular", "collaborative"):
            self.assertEqual(engine.recommend("target", strategy=strategy)[0]["book_key"], books[2]["book_key"])

    def test_content_results_ignore_repeated_loans_and_input_order(self):
        engine, books, loans = self.fixture()
        # 直接检查内容分数，热门度仍允许受复借影响。
        history = engine._histories["target"]
        scores = engine._content.scores(history)
        shuffled = Recommender(reversed(books), reversed(loans))
        self.assertEqual(scores, shuffled._content.scores(history))
        repeated_loans = loans + [loans[0]] * 10
        repeated_books = [{**row, "borrow_count": str(int(row["borrow_count"]) +
                          (10 if row["book_key"] == loans[0]["book_key"] else 0))} for row in books]
        repeated = Recommender(repeated_books, repeated_loans)
        self.assertEqual(scores, repeated._content.scores(repeated._histories["target"]))
        self.assertTrue(all(0 <= score <= 1 + 1e-12 for score in scores.values()))
        self.assertEqual(shuffled.recommend("target"), engine.recommend("target"))

    def test_author_alone_can_recall_but_shared_placeholders_cannot(self):
        books = [book(1, title="山风", author="同一责任者", call_number=""),
                 book(2, title="海潮", author="同一责任者", call_number=""),
                 book(3, title="城市", author="另一作者", call_number="")]
        engine, _, _ = engine_for(books, [("a", 0)])
        self.assertGreater(engine._content.scores(engine._histories["a"])[books[1]["book_key"]], 0)
        for row in books:
            row["author"] = "未知"
        index = ContentIndex({row["book_key"]: row for row in books})
        self.assertEqual(index.scores({books[0]["book_key"]}), {})

    def test_features_normalize_fullwidth_and_exclude_copy_suffix_and_publisher(self):
        first = book(1, title="Ｐｙｔｈｏｎ", call_number="ＴＰ３１１．１／１２", author=" 作 者 ")
        second = {**first, "title": "python", "call_number": "TP311.1/999", "author": "作者", "publisher": "变化"}
        self.assertEqual(features(first), features(second))
        self.assertFalse(any("999" in token or "１２" in token for token in features(first)))


class SplitEvaluationTests(unittest.TestCase):
    def fixture(self):
        books = [book(1), book(2), book(3), book(4)]
        pairs = [(f"private-{i}", j) for i in range(12) for j in (0, 1 + i % 3)]
        return engine_for(books, pairs)

    def test_validation_test_and_previous_readers_are_disjoint_and_stable(self):
        engine, books, loans = self.fixture()
        groups = split_readers(engine, 3, 4, 2)
        old = set(sorted(engine._histories, key=lambda r: _digest("c2-eval-20261024/" + r))[:2])
        self.assertFalse(set(groups["validation"]) & set(groups["test"]))
        self.assertFalse((set(groups["validation"]) | set(groups["test"])) & old)
        shuffled = Recommender(reversed(books), reversed(loans))
        self.assertEqual(groups, split_readers(shuffled, 3, 4, 2))
        with self.assertRaises(ValueError):
            split_readers(engine, 10, 10, 2)

    def test_training_excludes_both_cohorts_targets_including_aliases_and_repeats(self):
        books = [book(1), book(1, key="copy:01"), book(2), book(3)]
        engine, catalog, loans = engine_for(books, [("a", 0), ("a", 1), ("a", 2), ("b", 2), ("b", 2), ("b", 3)])
        heldout = {"a": books[0]["book_key"], "b": books[2]["book_key"]}
        training, removed = build_holdout(engine, {row["book_key"]: row for row in catalog}, loans, heldout)
        self.assertEqual(removed, 4)
        self.assertEqual(training._counts[books[0]["book_key"]], 0)
        self.assertIn(books[0]["book_key"], training._books)
        for reader, target in heldout.items():
            self.assertNotIn(target, training._histories[reader])

    def test_only_validation_selects_weight_and_reports_are_aggregate(self):
        _, books, loans = self.fixture()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            directory = Path(tmp)
            write_source(directory, books, loans)
            validation = compare(directory, "validation", validation_size=3, test_size=4, legacy_size=2)
            self.assertEqual(len(validation["results"]), 5)
            with patch.object(Recommender, "CONTENT_WEIGHT", validation["selected_weight"]):
                test = compare(directory, "test", validation, 3, 4, 2)
            self.assertEqual(test["selected_weight"], validation["selected_weight"])
            self.assertEqual(test["training_rows"], validation["training_rows"])
            self.assertLessEqual(len(test["results"]), 2)
            self.assertTrue(all(row["readers"] == 4 for row in test["results"].values()))
            self.assertNotIn("private-", json.dumps([validation, test]))
            self.assertNotIn('"reader_id"', json.dumps([validation, test]))
            with self.assertRaises(ValueError):
                compare(directory, "test", None, 3, 4, 2)
            with self.assertRaises(ValueError):
                compare(directory, "test", validation, 4, 3, 2)
            with patch.object(Recommender, "CONTENT_WEIGHT", 0.123):
                with self.assertRaises(ValueError):
                    compare(directory, "test", validation, 3, 4, 2)


if __name__ == "__main__":
    unittest.main()

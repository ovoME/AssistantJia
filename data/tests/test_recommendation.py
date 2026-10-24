"""用可人工推导的借阅关系验证 C2，测试书目和读者均为虚构。"""

import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from data.recommendation import Recommender
from data.scripts.generate_demo import demo_isbn


ROOT = Path(__file__).resolve().parents[2]


def book(number, category="I", call_number=None, key=None, title=None, author="虚构作者", publisher="虚构出版社"):
    isbn = demo_isbn(number)
    return {
        "book_key": key or "isbn:" + isbn, "title": title or f"虚构图书{number}",
        "author": author, "publisher": publisher,
        "isbn": isbn if key is None else "",
        "call_number": call_number if call_number is not None else category + str(number),
        "category_code": category, "category_name": {"I": "文学", "T": "工业技术", "F": "经济"}.get(category, "未识别分类"),
    }


def engine_for(books, pairs, label="simulated"):
    """pairs 使用图书在 books 中的下标，次数等于流水数。"""
    loans = [{"reader_id": reader, "book_key": books[index]["book_key"]} for reader, index in pairs]
    counts = Counter(loan["book_key"] for loan in loans)
    catalog = [{**item, "borrow_count": str(counts[item["book_key"]])} for item in books]
    return Recommender(catalog, loans, label), catalog, loans


def write_source(folder, books, loans, label="simulated"):
    for name, rows, fields in (("books", books, list(book(1)) + ["borrow_count"]),
                               ("borrow_records", loans, ["reader_id", "book_key"])):
        with (folder / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (folder / "quality_report.json").write_text(
        json.dumps({"dataset_label": label, "accepted_rows": len(loans)}), encoding="utf-8")


class RecommendationTests(unittest.TestCase):
    def test_popularity_counts_loans_and_ties_break_by_book_key(self):
        books = [book(1), book(2), book(3)]
        engine, _, _ = engine_for(books, [("a", 0), ("a", 0), ("b", 1), ("c", 2)])
        rows = engine.hot_books(limit=3)
        self.assertEqual([row["count"] for row in rows], [2, 1, 1])
        self.assertEqual([row["book_key"] for row in rows], [item["book_key"] for item in books])

    def test_new_and_unknown_readers_fall_back_to_popularity(self):
        engine, _, _ = engine_for([book(1), book(2)], [("0001", 0), ("0002", 1), ("0003", 1)])
        for strategy in ("hybrid", "category", "collaborative", "popular"):
            for reader in (None, "", "unknown"):
                with self.subTest(strategy=strategy, reader=reader):
                    rows = engine.recommend(reader, strategy=strategy)
                    self.assertEqual([row["title"] for row in rows], ["虚构图书2", "虚构图书1"])
                    self.assertTrue(all(row["strategy"] == "popular" for row in rows))

    def test_all_strategies_filter_complete_history_and_preserve_leading_zero_ids(self):
        books = [book(i) for i in range(1, 121)]
        pairs = [("0001", i) for i in range(119)] + [("1", 119)]
        engine, _, _ = engine_for(books, pairs)
        for strategy in ("hybrid", "category", "collaborative", "popular"):
            with self.subTest(strategy=strategy):
                rows = engine.recommend("0001", limit=100, strategy=strategy)
                self.assertEqual([row["book_key"] for row in rows], [books[-1]["book_key"]])
        self.assertEqual(len(engine.recommend("1", limit=100)), 100)

    def test_category_filter_precedes_limit_and_supports_t_and_tp(self):
        books = [book(i, "F") for i in range(1, 105)] + [
            book(105, "T", "TP311/1"), book(106, "T", "TU2/1"), book(107, "I"),
            book(108, "UNKNOWN", "???"),
        ]
        engine, _, _ = engine_for(books, [(str(i), i) for i in range(len(books))])
        self.assertEqual(len(engine.hot_books(limit=100)), 100)
        self.assertEqual([row["title"] for row in engine.hot_books(" ｔｐ ")], ["虚构图书105"])
        self.assertEqual(len(engine.hot_books("T")), 2)
        self.assertEqual(engine.recommend(category="I")[0]["title"], "虚构图书107")
        self.assertEqual(engine.hot_books("UNKNOWN")[0]["title"], "虚构图书108")
        self.assertEqual(engine.recommend(category="Z"), [])

    def test_category_preferences_use_distinct_books_and_rank_before_popular_fallback(self):
        books = [book(1, "T"), book(2, "I"), book(3, "T"), book(4, "F")]
        pairs = [("target", 0)] * 12 + [("target", 1), ("peer", 2)] + [("other", 3)] * 10
        engine, _, _ = engine_for(books, pairs)
        rows = engine.recommend("target", strategy="category")
        self.assertEqual([row["title"] for row in rows], ["虚构图书3", "虚构图书4"])
        self.assertEqual([row["strategy"] for row in rows], ["category", "popular"])
        self.assertIn("工业技术", rows[0]["reason"])

    def test_collaborative_cosine_scores_match_manual_calculation(self):
        books = [book(i) for i in range(1, 5)]
        pairs = [("target", 0), ("target", 1), ("peer-a", 0), ("peer-a", 1),
                 ("peer-a", 2), ("peer-b", 0), ("peer-b", 3)]
        engine, _, _ = engine_for(books, pairs)
        rows = engine.recommend("target", strategy="collaborative")
        self.assertEqual([row["title"] for row in rows], ["虚构图书3", "虚构图书4"])
        first_similarity, second_similarity = 2 / math.sqrt(6), 0.5
        expected = 0.9 * first_similarity / (first_similarity + second_similarity) + 0.1
        self.assertAlmostEqual(rows[0]["score"], expected, places=7)
        self.assertTrue(all(row["strategy"] == "collaborative" for row in rows))
        duplicated, _, _ = engine_for(books, pairs + [("peer-a", 0)] * 20)
        self.assertEqual(duplicated.recommend("target", strategy="collaborative"), rows)

    def test_hybrid_combines_preference_and_collaboration(self):
        books = [book(1, "I"), book(2, "F"), book(3, "I")]
        engine, _, _ = engine_for(books, [("target", 0), ("peer", 0), ("peer", 1), ("other", 2)])
        rows = engine.recommend("target")
        self.assertEqual([row["title"] for row in rows], ["虚构图书2", "虚构图书3"])
        self.assertEqual([row["strategy"] for row in rows], ["collaborative", "category"])
        self.assertEqual([row["score"] for row in rows], [0.7, 0.4])

    def test_collaborative_neighbors_are_capped_at_thirty_with_stable_ties(self):
        books = [book(i) for i in range(32)]
        pairs = [("target", 0)]
        for index in range(31):
            pairs.extend([(f"neighbor-{index:02d}", 0), (f"neighbor-{index:02d}", index + 1)])
        engine, _, _ = engine_for(books, pairs)
        rows = engine.recommend("target", limit=100, strategy="collaborative")
        self.assertEqual(len(rows), 31)
        self.assertEqual([row["strategy"] for row in rows], ["collaborative"] * 30 + ["popular"])
        self.assertEqual(rows[-1]["title"], "虚构图书31")

    def test_no_neighbors_unknown_categories_and_exhausted_history(self):
        books = [book(1, "UNKNOWN", "???"), book(2, "I")]
        engine, _, _ = engine_for(books, [("target", 0), ("peer", 1)])
        self.assertEqual(engine.recommend("target")[0]["strategy"], "popular")
        all_read, _, _ = engine_for(books, [("target", 0), ("target", 1)])
        self.assertEqual(all_read.recommend("target"), [])
        empty = Recommender([], [])
        self.assertEqual(empty.recommend(), [])
        self.assertEqual(empty.hot_books(), [])

    def test_missing_isbn_copies_merge_and_are_excluded_as_the_same_book(self):
        books = [book(1), book(1, key="copy:0002"), book(2)]
        engine, _, _ = engine_for(books, [("target", 1), ("peer", 0), ("peer", 2)])
        rows = engine.hot_books()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["isbn"], books[0]["isbn"])
        self.assertEqual([row["title"] for row in engine.recommend("target")], ["虚构图书2"])

    def test_unidentified_copies_merge_only_with_complete_unambiguous_metadata(self):
        books = [book(1, key="copy:02"), book(1, key="copy:01"), book(2)]
        engine, _, _ = engine_for(books, [("target", 0), ("peer", 1), ("peer", 2)])
        self.assertEqual(len(engine.hot_books()), 2)
        self.assertEqual(engine.hot_books()[0]["book_key"], "copy:01")
        self.assertEqual(len(engine.recommend("target")), 1)
        books[1]["author"] = ""
        incomplete, _, _ = engine_for(books, [("a", 0), ("b", 1), ("c", 2)])
        self.assertEqual(len(incomplete.hot_books()), 3)

    def test_distinct_valid_isbns_with_the_same_metadata_are_not_merged(self):
        books = [book(1, title="同名书"), book(2, title="同名书"), book(1, key="copy:03", title="同名书")]
        engine, _, _ = engine_for(books, [("a", 0), ("b", 1), ("c", 2)])
        self.assertEqual(len(engine.hot_books()), 3)
        self.assertEqual(len(engine.recommend("a")), 2)

    def test_shuffle_is_deterministic_and_queries_do_not_change_other_readers(self):
        books = [book(i) for i in range(1, 5)]
        pairs = [("a", 0), ("b", 0), ("b", 1), ("c", 0), ("c", 2), ("d", 3)]
        engine, catalog, loans = engine_for(books, pairs)
        shuffled = Recommender(list(reversed(catalog)), list(reversed(loans)), "simulated")
        before = engine.response("a")
        engine.response("unknown")
        engine.response("b", category="I")
        self.assertEqual(engine.response("a"), before)
        self.assertEqual(shuffled.response("a"), before)

    def test_response_contract_privacy_and_historical_scope(self):
        engine, _, _ = engine_for([book(1), book(2)], [("private-target", 0), ("private-peer", 1)])
        payload = engine.response("private-target")
        self.assertEqual((payload["code"], payload["message"], payload["dataset_label"]), (0, "success", "simulated"))
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        for forbidden in ("reader_id", "private-target", "private-peer", "location", "available", "status"):
            self.assertNotIn(forbidden, encoded)
        self.assertNotIn("近期", payload["data"][0]["reason"])
        self.assertTrue({"title", "author", "isbn", "call_number", "reason", "book_key"}.issubset(payload["data"][0]))

    def test_invalid_options_are_rejected(self):
        engine = Recommender([], [])
        for limit in (0, -1, 101, 1.5, True, "5"):
            for method in (engine.recommend, engine.hot_books):
                with self.subTest(limit=limit, method=method):
                    with self.assertRaises(ValueError):
                        method(limit=limit)
        for category in ("", "计算机", "TP3", "M", 1):
            with self.subTest(category=category):
                with self.assertRaises(ValueError):
                    engine.recommend(category=category)
        with self.assertRaises(ValueError):
            engine.recommend(reader_id=1)
        with self.assertRaises(ValueError):
            engine.recommend(strategy="random")

    def test_bad_catalog_and_stale_loans_fail_instead_of_inventing_results(self):
        _, catalog, loans = engine_for([book(1)], [("a", 0)])
        bad_inputs = [
            (catalog * 2, loans),
            ([{**catalog[0], "borrow_count": "1.5"}], loans),
            (catalog, loans * 2),
            (catalog, [{"reader_id": "a", "book_key": "missing"}]),
            (catalog, [{"reader_id": "", "book_key": catalog[0]["book_key"]}]),
            ([{"book_key": "a"}], loans),
        ]
        for bad_books, bad_loans in bad_inputs:
            with self.subTest(books=bad_books, loans=bad_loans):
                with self.assertRaises(ValueError):
                    Recommender(bad_books, bad_loans)
        with self.assertRaises(ValueError):
            Recommender([], [], "unverified")

    def test_directory_loader_and_cli_export(self):
        _, catalog, loans = engine_for([book(1), book(2)], [("0001", 0), ("0002", 1)])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            write_source(folder, catalog, loans)
            engine = Recommender.from_directory(folder)
            self.assertEqual(engine.recommend("0001")[0]["title"], "虚构图书2")
            output = folder / "private/result.json"
            result = subprocess.run([
                sys.executable, "-S", "-W", "error", "-m", "data.scripts.recommend", "--data-dir", str(folder),
                "--reader-id", "0001", "--limit", "2", "--output", str(output),
            ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=self._utf8_env())
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(result.stdout), payload)
            self.assertEqual(payload, engine.response("0001", limit=2))
            for args in (["--limit", "0"], ["--category", "TP3"], ["--data-dir", str(folder / "missing")]):
                failed = subprocess.run([
                    sys.executable, "-m", "data.scripts.recommend", "--data-dir", str(folder), *args,
                ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=self._utf8_env())
                self.assertEqual(failed.returncode, 2)
                self.assertNotIn("Traceback", failed.stderr)

    @staticmethod
    def _utf8_env():
        import os
        return {**os.environ, "PYTHONUTF8": "1"}

    def test_empty_directory_and_quality_report_validation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            write_source(folder, [], [])
            self.assertEqual(Recommender.from_directory(folder).response()["data"], [])
            quality_path = folder / "quality_report.json"
            quality_path.unlink()
            self.assertEqual(Recommender.from_directory(folder).dataset_label, "unknown")
            for quality in ([], {"accepted_rows": 99}, {"dataset_label": "bad"}, {"dataset_label": []}):
                quality_path.write_text(json.dumps(quality), encoding="utf-8")
                with self.assertRaises(ValueError):
                    Recommender.from_directory(folder)
            (folder / "books.csv").write_text("title\n书\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "表头"):
                Recommender.from_directory(folder)

    def test_c1_pipeline_output_is_directly_consumable(self):
        import pandas as pd
        from data.pipeline import clean_file

        rows = [
            ["0001", "O4/1", "copy01", "虚构物理", "虚构作者", "0-306-40615-2", "虚构出版社"],
            ["0002", "O4/1", "copy02", "虚构物理", "虚构作者", "9780306406157", "虚构出版社"],
            ["0002", "O4/1", "copy03", "虚构物理", "虚构作者", "", "虚构出版社"],
            ["0002", "I1/1", "copy04", "虚构文学", "虚构作者", "", "虚构出版社"],
        ]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            source = folder / "input.csv"
            pd.DataFrame(rows, columns=["reader_id", "call_number", "book_id", "title", "author", "isbn", "publisher"]).to_csv(source, index=False)
            clean_file(source, folder / "result", "simulated")
            engine = Recommender.from_directory(folder / "result")
            self.assertEqual(len(engine.hot_books()), 2)
            self.assertEqual(engine.hot_books()[0]["count"], 3)
            self.assertEqual(engine.hot_books()[0]["isbn"], "9780306406157")
            self.assertEqual([row["title"] for row in engine.recommend("0001")], ["虚构文学"])

    def test_batch_validation_reports_aggregates_without_reader_details(self):
        from data.scripts.validate_recommendations import validate

        _, catalog, loans = engine_for([book(1), book(2), book(3)], [
            ("private-a", 0), ("private-a", 1), ("private-b", 0), ("private-b", 2),
        ])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            write_source(folder, catalog, loans)
            report = validate(folder, limit=2, holdout_readers=2)
            self.assertEqual((report["accepted_rows"], report["reader_count"], report["cold_start_checks"]), (4, 2, 4))
            self.assertTrue(all(result["queries"] == 2 and result["history_overlap"] == 0
                                for result in report["strategies"].values()))
            self.assertEqual(report["holdout"]["training_rows"], 2)
            self.assertEqual(report["holdout"]["removed_loan_rows"], 2)
            encoded = json.dumps(report)
            for private in ("private-a", "private-b", '"reader_id"'):
                self.assertNotIn(private, encoded)

    def test_empty_batch_validation_and_invalid_limit(self):
        from data.scripts.validate_recommendations import validate

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            write_source(folder, [], [])
            report = validate(folder)
            self.assertEqual(report["reader_count"], 0)
            self.assertEqual(report["holdout"]["evaluated_readers"], 0)
            self.assertTrue(all(row["hit_rate"] is None for row in report["holdout"]["metrics"].values()))
            with self.assertRaises(ValueError):
                validate(folder, limit=0)

    def test_holdout_removes_all_repeat_loans_and_split_is_deterministic(self):
        from data.scripts.validate_recommendations import evaluate_holdout

        engine, catalog, loans = engine_for([book(1), book(2), book(3)], [
            ("a", 0), ("a", 1), ("a", 0), ("a", 1), ("b", 0), ("b", 2),
        ])
        first = evaluate_holdout(engine, {row["book_key"]: row for row in catalog}, loans, limit=2, max_readers=2)
        second = evaluate_holdout(engine, {row["book_key"]: row for row in catalog}, list(reversed(loans)), limit=2, max_readers=2)
        self.assertEqual(first, second)
        self.assertEqual(first["evaluated_readers"], 2)
        self.assertEqual(first["removed_loan_rows"], 3)
        self.assertEqual(first["training_rows"], 3)

    def test_validation_keeps_distinct_isbn_editions_separate(self):
        from data.scripts.validate_recommendations import validate

        _, catalog, loans = engine_for([book(1, title="同名虚构书"), book(2, title="同名虚构书")], [("a", 0), ("b", 1)])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            write_source(folder, catalog, loans)
            report = validate(folder, holdout_readers=0)
            self.assertEqual(report["strategies"]["hybrid"]["returned"], 2)

    def test_validation_cli_writes_only_summary_json(self):
        _, catalog, loans = engine_for([book(1), book(2)], [("private-a", 0), ("private-b", 1)])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            write_source(folder, catalog, loans)
            output = folder / "report.json"
            result = subprocess.run([
                sys.executable, "-S", "-W", "error", "-m", "data.scripts.validate_recommendations",
                "--data-dir", str(folder), "--output", str(output), "--holdout-readers", "0",
            ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=self._utf8_env())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), json.loads(output.read_text(encoding="utf-8")))
            self.assertNotIn("private-", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

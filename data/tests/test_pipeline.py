"""按人工可核对的小数据检查业务含义，使用标准库 unittest。"""
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from data.pipeline import api_data, analyze_file, analyze_frame, canonical_isbn, clean_file, clean_frame
from data.scripts.generate_demo import HEADERS, demo_rows


def fixture():
    return pd.DataFrame([
        ["0001", "O4/1", "00000001", "模拟物理", "作者甲", "978-0-306-40615-7", "出版社甲"],
        ["0001", "O4/1", "00000001", "模拟物理", "作者甲", "978-0-306-40615-7", "出版社甲"],
        ["0002", "O4/1", "00000002", "模拟物理", "作者甲", "0-306-40615-2", "出版社甲"],
        ["0002", " i247.5 / 2 ", "00000003", "  模拟文学　 ", "作者乙", "", "出版社乙"],
        ["0003", "F1/3", "00000004", "模拟经济", "作者丙", "9780000000000", ""],
        ["0004", "T1/4", "00000005", "", "作者丁", "", "出版社丁"],
        ["", "???", "00000006", "缺读者的图书", "", "", ""],
    ], columns=HEADERS)


class PipelineTests(unittest.TestCase):
    def test_counts_reconcile_and_preserve_repeated_loans(self):
        clean, books, readers, rejected, quality = clean_frame(fixture(), "simulated")
        self.assertEqual((len(clean), len(rejected), len(books), len(readers)), (5, 2, 3, 3))
        self.assertEqual(quality["input_rows"], quality["accepted_rows"] + quality["rejected_rows"])
        self.assertEqual(quality["normalized_duplicate_excess_rows"], 1)
        self.assertEqual(quality["invalid_isbn_rows"], 1)
        self.assertEqual(clean.iloc[0]["reader_id"], "0001")
        self.assertEqual(clean.iloc[0]["book_id"], "00000001")
        self.assertEqual(clean.iloc[3]["call_number"], "I247.5/2")
        self.assertEqual(clean.iloc[3]["title"], "模拟文学")
        physics = books[books["book_key"] == "isbn:9780306406157"].iloc[0]
        self.assertEqual((physics["borrow_count"], physics["observed_copy_count"]), (3, 2))

    def test_statistics_against_manual_answers(self):
        clean, *_ = clean_frame(fixture())
        summary, tables = analyze_frame(clean)
        self.assertEqual((summary["borrow_count"], summary["reader_count"], summary["book_count"]), (5, 3, 3))
        self.assertEqual(summary["observed_copy_count"], 4)
        self.assertEqual(summary["borrows_per_reader"], 1.6667)
        self.assertEqual(tables["hot_books"].iloc[0]["borrow_count"], 3)
        self.assertEqual(dict(zip(tables["categories"]["category_code"], tables["categories"]["borrow_count"])), {"O": 3, "F": 1, "I": 1})
        self.assertAlmostEqual(tables["categories"]["share"].sum(), 1)
        self.assertEqual(int((tables["reader_distribution"]["borrow_count"] * tables["reader_distribution"]["reader_count"]).sum()), 5)
        pref = tables["reader_preferences"]
        self.assertEqual(pref.loc[pref["reader_id"] == "0002", "share"].tolist(), [0.5, 0.5])
        self.assertTrue(tables["publishers"]["publisher_missing"].any())

    def test_isbn_checksums_and_equivalent_editions(self):
        self.assertEqual(canonical_isbn("0306406152"), "9780306406157")
        self.assertEqual(canonical_isbn("9780306406157"), "9780306406157")
        self.assertTrue(canonical_isbn("080442957X"))
        for value in ("9780000000000", "0306406153", "not-isbn", "", "1234567890128"):
            self.assertEqual(canonical_isbn(value), "")

    def test_missing_optional_columns_and_ambiguous_alias(self):
        clean, _, _, _, quality = clean_frame(pd.DataFrame([{"证件号": "001", "题名": "测试书"}]))
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean.iloc[0]["category_code"], "UNKNOWN")
        self.assertEqual(len(quality["missing_columns"]), 5)
        with self.assertRaisesRegex(ValueError, "多列映射"):
            clean_frame(fixture().assign(isbn=""))
        with self.assertRaisesRegex(ValueError, "必须包含"):
            clean_frame(pd.DataFrame({"作者": ["甲"]}))

    def test_missing_isbn_does_not_merge_different_copies(self):
        raw = fixture().iloc[:3].copy()
        raw["IISSBN"] = ""
        _, books, *_ = clean_frame(raw)
        self.assertEqual(len(books), 2)
        self.assertTrue(books["book_key"].str.startswith("copy:").all())

    def test_missing_isbn_resolves_through_unambiguous_copy(self):
        raw = fixture().iloc[:3].copy()
        raw.loc[1, "IISSBN"] = ""
        clean, books, _, _, quality = clean_frame(raw)
        self.assertEqual(len(books), 1)
        self.assertEqual(clean.iloc[1]["isbn"], "")
        self.assertEqual(clean.iloc[1]["book_key"], "isbn:9780306406157")
        self.assertEqual(quality["book_key_resolved_by_copy_rows"], 1)
        self.assertEqual(books.iloc[0]["isbn"], "9780306406157")

    def test_conflicting_copy_isbns_are_not_used_for_missing_link(self):
        raw = fixture().iloc[:3].copy()
        raw["财产号"] = "00000001"
        raw.loc[1, "IISSBN"] = "9780804429573"
        raw.loc[2, "IISSBN"] = ""
        clean, _, _, _, quality = clean_frame(raw)
        self.assertEqual(quality["copy_isbn_conflict_groups"], 1)
        self.assertEqual(clean.iloc[2]["book_key"], "copy:00000001")

    def test_empty_and_all_rejected_inputs(self):
        for raw in (pd.DataFrame(columns=HEADERS), fixture().iloc[5:]):
            clean, books, readers, rejected, quality = clean_frame(raw)
            summary, tables = analyze_frame(clean)
            self.assertEqual((len(clean), len(books), len(readers)), (0, 0, 0))
            self.assertEqual(len(rejected), len(raw))
            self.assertIsNone(summary["borrows_per_reader"])
            self.assertTrue(all(t.empty for t in tables.values()))

    def test_csv_roundtrip_and_dashboard_has_no_reader_ids(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            source = folder / "input.csv"
            fixture().to_csv(source, index=False, encoding="utf-8-sig")
            clean_file(source, folder / "result", "simulated")
            analyze_file(folder / "result/borrow_records.csv", folder / "result")
            roundtrip = pd.read_csv(folder / "result/borrow_records.csv", dtype=str, keep_default_na=False)
            self.assertEqual(roundtrip.iloc[0]["reader_id"], "0001")
            dashboard = json.loads((folder / "result/dashboard.json").read_text(encoding="utf-8"))
            self.assertEqual(dashboard["dataset_label"], "simulated")
            self.assertEqual(dashboard["data"]["summary"]["total_borrows"], 5)
            api_summary = json.loads((folder / "result/api_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(api_summary["data"], dashboard["data"]["summary"])
            self.assertEqual(api_summary["message"], "success")
            self.assertNotIn("reader_id", json.dumps(dashboard))
            for csv in (folder / "result").glob("*.csv"):
                self.assertTrue(len(pd.read_csv(csv).columns))

    def test_repeat_runs_are_deterministic(self):
        raw = pd.DataFrame(demo_rows(400), columns=HEADERS)
        first = clean_frame(raw)
        second = clean_frame(raw.sample(frac=1, random_state=1))
        pd.testing.assert_frame_equal(first[1], second[1])
        pd.testing.assert_frame_equal(first[2], second[2])
        self.assertEqual(demo_rows(30), demo_rows(30))

    def test_api_fields_match_existing_frontend_contract(self):
        clean, *_ = clean_frame(fixture())
        summary, tables = analyze_frame(clean)
        mapped = api_data(summary, tables)
        self.assertEqual(mapped["summary"], {
            "total_borrows": 5, "total_readers": 3, "total_titles": 3,
            "avg_borrow_per_reader": 1.6667,
        })
        self.assertEqual(mapped["hot_books"][0]["count"], 3)
        self.assertEqual(mapped["categories"][0]["category"], "O")
        self.assertEqual(mapped["categories"][0]["count"], 3)
        self.assertEqual(int(tables["hot_books"].iloc[0]["borrow_count"]), 3)
        self.assertNotIn("reader_id", json.dumps(mapped))

    def test_api_total_titles_is_title_count_and_empty_average_is_null(self):
        raw = fixture().iloc[:3].copy()
        raw.loc[2, "IISSBN"] = "9780804429573"
        clean, *_ = clean_frame(raw)
        summary, tables = analyze_frame(clean)
        self.assertEqual(summary["book_count"], 2)
        self.assertEqual(api_data(summary, tables)["summary"]["total_titles"], 1)
        empty, *_ = clean_frame(pd.DataFrame(columns=HEADERS))
        summary, tables = analyze_frame(empty)
        self.assertIsNone(api_data(summary, tables)["summary"]["avg_borrow_per_reader"])


if __name__ == "__main__":
    unittest.main()

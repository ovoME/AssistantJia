import csv
import json
import tempfile
import unittest
from pathlib import Path
from data.usage import analyze_usage, observed_date


class UsageTests(unittest.TestCase):
    def test_sources_remain_separate_and_report_contains_no_identifiers(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            directory = Path(tmp)
            with (directory / "座位预约.csv").open("w", encoding="gb18030", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["学号", "预约日期", "楼层", "状态"])
                writer.writerows([["private-reader", "2026/10/01", "一层", "完成"]] * 6)
                writer.writerow(["another-reader", "not-a-date", "二层", "取消"])
            with (directory / "读者数据.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["ID", "TYPE"])
                writer.writerows([["private-reader", "学生"], ["private-reader", "学生"], ["", "教工"]])
            result = analyze_usage(directory, "simulated")
            seats, readers = result["datasets"]["seats"], result["datasets"]["readers"]
            self.assertEqual((seats["rows"], seats["distinct_source_readers"], seats["duplicate_excess_rows"]), (7, 2, 5))
            self.assertEqual((readers["rows"], readers["distinct_source_readers"], readers["missing_reader_rows"]), (3, 1, 1))
            self.assertEqual(seats["observed_date_min"], "2026-10-01")
            self.assertEqual(seats["invalid_date_rows"], 1)
            self.assertEqual(seats["suppressed_dimension_rows"]["楼层"], 1)
            self.assertEqual(seats["dimensions"]["楼层"], [{"name": "一层", "count": 6}])
            self.assertNotIn("private-reader", json.dumps(result))
            self.assertNotIn("another-reader", json.dumps(result))

    def test_invalid_schema_is_not_silently_counted(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp) / "座位预约.csv"
            path.write_text("学号,状态\na,完成\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_usage(Path(tmp))

    def test_dates_require_a_real_year_not_a_guessed_serial(self):
        self.assertIsNone(observed_date("10月1日"))
        self.assertIsNone(observed_date(45000))
        self.assertEqual(observed_date("2026-10-01 09:00:00"), "2026-10-01")
        self.assertEqual(observed_date("2026-10-01 09:00:00.000"), "2026-10-01")
        self.assertEqual(observed_date("2026-1"), "2026-01")
        self.assertEqual(observed_date("2026"), "2026")

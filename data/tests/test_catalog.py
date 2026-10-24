"""C3 标准库测试：仅使用程序内虚构书目，不复制用户数据。"""

import csv
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from data.catalog import BASE_FIELDS, Catalog, SNAPSHOT_FIELDS, build_catalog, build_library_catalog
from data.isbn import canonical_isbn


ROOT = Path(__file__).resolve().parents[2]


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def c1_book(key="isbn:9780306406157", title="虚构物理", **overrides):
    return {
        "book_key": key, "title": title, "author": "虚构作者甲", "isbn": "9780306406157",
        "call_number": "O4/001", "publisher": "虚构出版社", "category_code": "O", "category_name": "数理科学和化学",
        **overrides,
    }


def library_book(identity="00001", title="虚构算法", **overrides):
    return {
        "NO": "1", "ID": identity, "TITLE": title, "AUTHOR": "虚构作者乙",
        "PUBLISHER": "虚构出版社", "YEAR": "2001", "CALLNO": "TP311/001",
        "LANGUAGE": "chi", "DOCTYPE": "图书", **overrides,
    }


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.folder = Path(self.temporary.name)
        self.database = self.folder / "目录 with spaces.sqlite3"
        self.source = self.folder / "export.csv"

    def tearDown(self):
        self.temporary.cleanup()

    def c1(self, rows=None, quality=None):
        write_csv(self.folder / "books.csv", rows if rows is not None else [c1_book()], BASE_FIELDS)
        if quality is not None:
            (self.folder / "quality_report.json").write_text(json.dumps(quality), encoding="utf-8")
        build_catalog(self.folder, self.database)
        return Catalog(self.database)

    def library(self, rows=None, label="simulated", holdings=None):
        rows = rows if rows is not None else [library_book()]
        write_csv(self.source, rows, list(library_book()))
        build_library_catalog(self.source, self.database, holdings, label)
        return Catalog(self.database)

    def test_library_export_mapping_preserves_identifier_and_no_invented_isbn(self):
        catalog = self.library([library_book(CALLNO=" ｔｐ３１１ / ００１ ")])
        row = catalog.get_book("catalog:00001")
        self.assertEqual(row["title"], "虚构算法")
        self.assertEqual(row["call_number"], "TP311/001")
        self.assertEqual((row["publication_year"], row["language"], row["document_type"]), ("2001", "chi", "图书"))
        self.assertEqual(row["category_code"], "T")
        self.assertEqual(row["isbn"], "")
        self.assertIsNone(row["location"])
        self.assertIsNone(row["available"])
        self.assertIsNone(row["holdings_snapshot"])
        self.assertEqual(row["status"], "unknown")
        self.assertFalse(row["is_live"])

    def test_titles_authors_publishers_call_numbers_and_multiterm_search(self):
        catalog = self.library([library_book(), library_book("00002", "虚构文学", AUTHOR="虚构作家丙", CALLNO="I247/2")])
        for query in ("算法", "作者乙", "TP311", "ｔｐ３１１", "算法 作者乙", "出版社 TP311"):
            with self.subTest(query=query):
                self.assertEqual([row["book_key"] for row in catalog.search(query)], ["catalog:00001"])
        self.assertEqual(len(catalog.search("出版社")), 2)
        self.assertEqual(catalog.search("算法 作家丙"), [])

    def test_empty_missing_and_unrelated_queries_never_fall_back(self):
        catalog = self.library()
        for query in ("", " \t ", "不存在的虚构图书", "1234567890128"):
            self.assertEqual(catalog.search(query), [])
        self.assertIsNone(catalog.get_book("catalog:missing"))
        self.assertEqual(catalog.lookup_isbn("bad isbn"), [])

    def test_isbn10_13_lookup_is_exact_and_checks_checksum(self):
        catalog = self.c1([c1_book(), c1_book("copy:02", "另一虚构书", isbn="9780804429573")])
        for query in ("0-306-40615-2", "9780306406157", "ISBN-13: 978-0-306-40615-7", "ISBN 0 306 40615 2"):
            with self.subTest(query=query):
                self.assertEqual(catalog.search(query)[0]["title"], "虚构物理")
                self.assertEqual(catalog.lookup_isbn(query)[0]["title"], "虚构物理")
        self.assertEqual(catalog.lookup_isbn("9780306406158"), [])
        self.assertEqual(canonical_isbn("080442957X"), "9780804429573")

    def test_sql_wildcards_and_injection_are_literal(self):
        catalog = self.library([library_book("a", "虚构50% A_B\\C"), library_book("b", "普通虚构书")])
        for query in ("%", "_", "\\", "A_B"):
            with self.subTest(query=query):
                self.assertEqual([row["book_key"] for row in catalog.search(query)], ["catalog:a"])
        self.assertEqual(catalog.search("' OR 1=1 --"), [])
        self.assertIsNone(catalog.get_book("' OR 1=1 --"))
        self.assertEqual(catalog.info()["book_count"], 2)

    def test_exact_matches_rank_first_and_ties_are_deterministic(self):
        rows = [library_book("b", "虚构算法进阶"), library_book("c", "虚构算法"), library_book("a", "虚构算法概论")]
        catalog = self.library(rows)
        first = catalog.search("虚构算法", limit=3)
        self.assertEqual([row["book_key"] for row in first], ["catalog:c", "catalog:a", "catalog:b"])
        self.assertEqual(self.library(list(reversed(rows))).search("虚构算法", limit=3), first)
        self.assertEqual(len(catalog.search("虚构算法", limit=1)), 1)

    def test_source_metadata_and_response_contract_have_no_reader_data(self):
        catalog = self.library()
        info = catalog.info()
        self.assertEqual((info["scope"], info["input_rows"], info["book_count"]), ("catalog_export", 1, 1))
        self.assertEqual(len(info["source_sha256"]), 64)
        payload = catalog.response("算法")
        self.assertEqual((payload["code"], payload["message"], payload["dataset_label"]), (0, "success", "simulated"))
        self.assertFalse(payload["is_live"])
        encoded = json.dumps(payload, allow_nan=False)
        for field in ("reader_id", "ReadNum", "DEPARTMENT", "ENROLLYEAR"):
            self.assertNotIn(field, encoded)

    def test_c1_source_and_quality_validation(self):
        catalog = self.c1(quality={"dataset_label": "simulated", "books_by_key": 1})
        self.assertEqual(catalog.info()["scope"], "historical_borrow_sample")
        self.assertEqual(catalog.info()["dataset_label"], "simulated")
        for quality in ([], {"dataset_label": []}, {"dataset_label": "bad"}, {"books_by_key": 2}):
            (self.folder / "quality_report.json").write_text(json.dumps(quality), encoding="utf-8")
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    build_catalog(self.folder, self.database)
        (self.folder / "quality_report.json").unlink()
        self.assertEqual(self.c1().info()["dataset_label"], "unknown")

    def test_missing_library_title_or_id_is_counted_and_traceable(self):
        catalog = self.library([library_book(), library_book("2", ""), library_book("", "缺号虚构书")])
        info = catalog.info()
        self.assertEqual((info["input_rows"], info["book_count"], info["rejected_rows"]), (3, 1, 2))
        self.assertEqual(info["rejected_sample"], [
            {"source_row": 3, "reason": "title_missing"}, {"source_row": 4, "reason": "id_missing"},
        ])

    def test_missing_optional_export_columns_and_empty_inputs(self):
        write_csv(self.source, [{"ID": "0001", "TITLE": "虚构书"}], ["ID", "TITLE"])
        build_library_catalog(self.source, self.database)
        row = Catalog(self.database).search("虚构书")[0]
        self.assertEqual((row["isbn"], row["author"], row["call_number"]), ("", "", ""))
        self.assertEqual(row["category_code"], "UNKNOWN")
        self.assertEqual(self.library([]).response("算法")["data"], [])
        self.assertEqual(self.c1([]).info()["book_count"], 0)

    def test_snapshot_retains_provenance_and_does_not_become_live_availability(self):
        snapshot = self.folder / "snapshot.csv"
        write_csv(snapshot, [{
            "book_key": "catalog:00001", "location": "虚构楼层测试架", "available": "2", "status": "在馆",
            "checked_at": "2000-01-01T08:00:00+08:00", "source": "虚构快照测试",
        }], SNAPSHOT_FIELDS)
        row = self.library(holdings=snapshot).search("算法")[0]
        self.assertEqual(row["location"], "虚构楼层测试架")
        self.assertIsNone(row["available"])
        self.assertEqual(row["status"], "unknown")
        self.assertEqual(row["holdings_snapshot"]["available"], 2)
        self.assertEqual(row["holdings_snapshot"]["checked_at"], "2000-01-01T00:00:00+00:00")

    def test_bad_snapshots_preserve_existing_database(self):
        catalog = self.library()
        original = self.database.read_bytes()
        base = dict(zip(SNAPSHOT_FIELDS, ["catalog:00001", "", "", "", "2000-01-01T00:00:00Z", "虚构快照"]))
        invalid = [
            [{**base, "book_key": "missing"}], [base, base], [{**base, "source": ""}],
            [{**base, "checked_at": "2000-01-01"}], [{**base, "checked_at": "bad"}],
            [{**base, "checked_at": "9999-01-01T00:00:00Z"}],
            [{**base, "available": "-1"}], [{**base, "available": "1.5"}],
        ]
        snapshot = self.folder / "snapshot.csv"
        for rows in invalid:
            with self.subTest(snapshot=rows):
                write_csv(snapshot, rows, SNAPSHOT_FIELDS)
                with self.assertRaises(ValueError):
                    build_library_catalog(self.source, self.database, snapshot)
                self.assertEqual(self.database.read_bytes(), original)
                self.assertEqual(catalog.info()["book_count"], 1)

    def test_duplicate_book_ids_and_bad_c1_isbn_fail_without_replacing_database(self):
        self.library()
        original = self.database.read_bytes()
        write_csv(self.source, [library_book(), library_book()], list(library_book()))
        with self.assertRaisesRegex(ValueError, "重复"):
            build_library_catalog(self.source, self.database)
        self.assertEqual(self.database.read_bytes(), original)
        for row in (c1_book(isbn="bad"), c1_book(title="")):
            write_csv(self.folder / "books.csv", [row], BASE_FIELDS)
            with self.assertRaises(ValueError):
                build_catalog(self.folder, self.database)
        self.assertEqual(self.database.read_bytes(), original)

    def test_bad_csv_headers_and_column_counts_are_rejected(self):
        for contents in ("ID,TITLE,ID\na,b,c\n", "ID\na\n", "ID,TITLE\na,b,c\n", "ID,TITLE\na\n"):
            with self.subTest(contents=contents):
                self.source.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    build_library_catalog(self.source, self.database)

    def test_database_replace_failure_leaves_old_catalog_and_cleans_temp_file(self):
        self.library()
        original = self.database.read_bytes()
        with patch("data.catalog.os.replace", side_effect=OSError("test failure")):
            with self.assertRaises(OSError):
                build_library_catalog(self.source, self.database)
        self.assertEqual(self.database.read_bytes(), original)
        self.assertEqual(list(self.folder.glob("*.tmp")), [])

    def test_output_cannot_overwrite_input_or_snapshot(self):
        source = self.folder / "input.db"
        write_csv(source, [library_book()], list(library_book()))
        original = source.read_bytes()
        with self.assertRaises(ValueError):
            build_library_catalog(source, source)
        with self.assertRaises(ValueError):
            build_library_catalog(source, self.database, self.database)
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaises(ValueError):
            build_library_catalog(source, self.folder / "output.csv")

    def test_missing_database_does_not_create_empty_file(self):
        with self.assertRaises(FileNotFoundError):
            Catalog(self.database)
        self.assertFalse(self.database.exists())

    def test_queries_leave_database_unchanged(self):
        catalog = self.library()
        original = self.database.read_bytes()
        catalog.search("算法")
        catalog.response("unknown")
        catalog.info()
        catalog.get_book("catalog:00001")
        self.assertEqual(self.database.read_bytes(), original)
        with catalog._connect() as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM books")

    def test_invalid_query_options(self):
        catalog = self.library()
        for limit in (0, -1, 101, 1.5, True, "3"):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    catalog.search("算法", limit)
        for query in (None, 1, "x" * 201, " ".join(["a"] * 11)):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    catalog.search(query)
        for label in ("bad", []):
            with self.assertRaises(ValueError):
                build_library_catalog(self.source, self.database, dataset_label=label)

    def test_wrong_database_version_and_metadata_fail_clearly(self):
        self.library()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(ValueError, "版本"):
            Catalog(self.database)
        self.library()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE metadata SET payload = '[]'")
            connection.commit()
        with self.assertRaisesRegex(ValueError, "元数据"):
            Catalog(self.database)

    def test_standard_library_only_cli_build_and_search(self):
        write_csv(self.source, [library_book()], list(library_book()))
        common = [sys.executable, "-S", "-W", "error", "-m"]
        def run(module, *args):
            return subprocess.run(common + [module, *map(str, args)], cwd=ROOT, capture_output=True,
                                  text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
        built = run("data.scripts.build_catalog", "--input", self.source, "--database", self.database,
                    "--dataset-label", "simulated")
        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertEqual(json.loads(built.stdout)["book_count"], 1)
        searched = run("data.scripts.search_catalog", "--database", self.database, "--query", "算法")
        self.assertEqual(searched.returncode, 0, searched.stderr)
        self.assertEqual(json.loads(searched.stdout)["data"][0]["book_key"], "catalog:00001")
        failed = run("data.scripts.search_catalog", "--database", self.database, "--query", "算法", "--limit", 0)
        self.assertEqual(failed.returncode, 2)
        self.assertNotIn("Traceback", failed.stderr)
        invalid = run("data.scripts.build_catalog", "--data-dir", self.folder, "--dataset-label", "real")
        self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()

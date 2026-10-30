import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from data.datasets import FIXTURE_ROOT, REAL_MANIFEST, SOURCES_MANIFEST, digest, prepare_integration, prepare_real, prepare_sources, read_csv, validate_fixture
from data.scripts.prepare_demo import prepare as prepare_demo
from data.services import BorrowingData
from data.catalog import Catalog


class SharedDataTests(unittest.TestCase):
    def write_test_package(self, directory, files, **metadata):
        """只打包本测试生成的虚构内容，不读取团队真实资料。"""
        archive = directory/"test.zip"
        with zipfile.ZipFile(archive,"w") as package:
            for name, content in files.items():
                package.writestr(name,content)
        manifest = {
            "schema_version":1,"dataset_label":"real","archive":archive.name,
            "sha256":digest(archive),
            "files":{name:{"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()}
                     for name, content in files.items()},
            **metadata,
        }
        path = directory/"test.manifest.json"
        path.write_text(json.dumps(manifest),encoding="utf-8")
        return path

    def test_committed_manifests_are_available_without_private_packages(self):
        for path, count in ((REAL_MANIFEST,5),(SOURCES_MANIFEST,7)):
            with self.subTest(manifest=path.name):
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["schema_version"],1)
                self.assertEqual(manifest["dataset_label"],"real")
                self.assertEqual(len(manifest["files"]),count)
                self.assertRegex(manifest["sha256"],r"^[a-f0-9]{64}$")
                for name, item in manifest["files"].items():
                    self.assertEqual(Path(name).name,name)
                    self.assertGreater(item["bytes"],0)
                    self.assertRegex(item["sha256"],r"^[a-f0-9]{64}$")

    def test_committed_source_has_complete_copy_mapping_and_dates(self):
        manifest = validate_fixture()
        self.assertEqual((manifest["book_count"],manifest["copy_count"],manifest["reader_count"],manifest["loan_count"]),(20,40,12,180))
        copies = read_csv(FIXTURE_ROOT/"copies.csv")
        crosswalk = read_csv(FIXTURE_ROOT/"book_crosswalk.csv")
        self.assertEqual(len({row["book_id"] for row in copies}),40)
        self.assertEqual({row["book_id"] for row in copies},{row["book_id"] for row in crosswalk})
        self.assertTrue(all(row["location"].startswith("模拟") for row in copies))

    def test_fresh_checkout_can_prepare_search_and_recommend(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            directory = prepare_integration(Path(tmp)/"fresh")
            catalog = Catalog(directory/"catalog.sqlite3")
            for query in ("三体","物流","Python","F252.8/11"):
                self.assertTrue(catalog.search(query),query)
            service = BorrowingData(directory)
            self.assertEqual(service.summary["total_borrows"],180)
            self.assertEqual(len(service.trend()),30)
            self.assertEqual(sum(row["count"] for row in service.trend()),180)
            self.assertEqual(sum(row["count"] for row in service.trend(7)),42)
            rows = service.engine.recommend("demo-reader",limit=5)
            self.assertTrue(rows)
            self.assertFalse({row["book_key"] for row in rows}&service.engine._histories["demo-reader"])
            self.assertEqual(prepare_integration(directory),directory)

    def test_prepare_does_not_overwrite_existing_data(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            directory = Path(tmp)
            (directory/"books.csv").write_text("existing-data",encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare_integration(directory)
            self.assertEqual((directory/"books.csv").read_text(),"existing-data")
        with self.assertRaises(ValueError):
            prepare_integration(FIXTURE_ROOT)

    def test_real_archive_is_present_and_matches_manifest(self):
        manifest = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
        archive = REAL_MANIFEST.parent/manifest["archive"]
        if not archive.is_file():
            self.skipTest("真实数据包不入库；从团队共享盘取得后可在本地验证。")
        self.assertEqual(digest(archive),manifest["sha256"])
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(set(package.namelist()),set(manifest["files"]))
            for row in package.infolist():
                self.assertEqual(row.file_size,manifest["files"][row.filename]["bytes"])
        self.assertEqual(manifest["counts"]["borrow_records"],36908)
        self.assertEqual(manifest["dataset_label"],"real")

    def test_archive_corruption_is_rejected_before_import(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp)
            (path/"test.zip").write_bytes(b"invalid archive")
            manifest = {"schema_version":1,"dataset_label":"real","archive":"test.zip","sha256":"0"*64}
            (path/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"校验"):
                prepare_real(path/"output",path/"manifest.json")
            self.assertFalse((path/"output").exists())

    def test_original_sources_package_is_present(self):
        manifest=json.loads(SOURCES_MANIFEST.read_text(encoding="utf-8"))
        archive=SOURCES_MANIFEST.parent/manifest["archive"]
        if not archive.is_file():
            self.skipTest("原始资料包不入库；从团队共享盘取得后可在本地验证。")
        self.assertEqual(digest(archive),manifest["sha256"])
        with zipfile.ZipFile(archive) as source:
            self.assertEqual(len(source.namelist()),7)
            self.assertEqual(set(source.namelist()),set(manifest["files"]))

    def test_generated_originals_package_can_be_imported_and_verified(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            directory = Path(tmp)
            names = json.loads(SOURCES_MANIFEST.read_text(encoding="utf-8"))["files"]
            files = {name:b"synthetic unit-test source only\n" for name in names}
            manifest = self.write_test_package(directory,files)
            output = prepare_sources(directory/"output",manifest)
            for name, content in files.items():
                self.assertEqual((output/name).read_bytes(),content)
            self.assertEqual(prepare_sources(output,manifest),output)

    def test_generated_real_format_package_can_be_imported_and_searched(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            directory = Path(tmp)
            demo = directory/"synthetic"
            prepare_demo(demo)
            files = {name:(demo/name).read_bytes()
                     for name in ("books.csv","borrow_records.csv","quality_report.json")}
            source = io.StringIO(newline="")
            writer = csv.DictWriter(source,fieldnames=("ID","TITLE","AUTHOR","PUBLISHER","YEAR","CALLNO","LANGUAGE","DOCTYPE"))
            writer.writeheader()
            writer.writerow({"ID":"DEMO-CATALOG-001","TITLE":"虚构测试书目","CALLNO":"TP311/1"})
            files["catalog_export.csv"] = source.getvalue().encode("utf-8")
            files["usage.json"] = b'{"dataset_label":"simulated","reports":[]}'
            manifest = self.write_test_package(directory,files,counts={"catalog_accepted_rows":1})
            output = prepare_real(directory/"output",manifest)
            self.assertEqual(Catalog(output/"catalog.sqlite3").search("虚构测试")[0]["book_key"],"catalog:DEMO-CATALOG-001")
            self.assertEqual(BorrowingData(output).summary["total_borrows"],8)
            self.assertEqual(prepare_real(output,manifest),output)

    def test_real_rows_cannot_be_given_synthetic_dates(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            directory = prepare_integration(Path(tmp)/"sample")
            path = directory/"quality_report.json"
            report = json.loads(path.read_text(encoding="utf-8"))
            report["dataset_label"] = "real"
            path.write_text(json.dumps(report),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"模拟日期"):
                BorrowingData(directory)

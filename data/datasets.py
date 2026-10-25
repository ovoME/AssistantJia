"""共享数据准备：完整性验证、隔离输出和显式真实/模拟两种来源。"""
from __future__ import annotations
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from data.catalog import build_catalog, build_library_catalog, Catalog
from data.recommendation import Recommender

DATA_ROOT = Path(__file__).parent
FIXTURE_ROOT = DATA_ROOT / "fixtures" / "integration"
REAL_MANIFEST = DATA_ROOT / "shared" / "library-real-v1.manifest.json"
SOURCES_MANIFEST = DATA_ROOT / "shared" / "library-sources-v1.manifest.json"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            result.update(chunk)
    return result.hexdigest()


def validate_fixture(source=FIXTURE_ROOT):
    source = Path(source)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("dataset_label") != "simulated" or manifest.get("schema_version") != 1:
        raise ValueError("联调源必须明确标注 simulated。")
    books, loans = read_csv(source/"books.csv"), read_csv(source/"borrow_records.csv")
    engine = Recommender(books, loans, "simulated")
    copies, crosswalk = read_csv(source/"copies.csv"), read_csv(source/"book_crosswalk.csv")
    readers = {row["reader_id"] for row in read_csv(source/"readers.csv")}
    by_copy = {row["book_id"]: row for row in copies}
    if len(by_copy) != len(copies) or len(crosswalk) != len(copies):
        raise ValueError("每册财产号和对照须唯一完整。")
    for row in crosswalk:
        item = by_copy.get(row["book_id"])
        if not item or any(row[field] != item[field] for field in ("book_key", "catalog_id")):
            raise ValueError("模拟编号对照与副本清单不一致。")
    if len({row["book_id"] for row in crosswalk}) != len(copies):
        raise ValueError("模拟对照包含重复财产号。")
    from datetime import date
    for loan in loans:
        if loan["reader_id"] not in readers or loan["book_id"] not in by_copy or by_copy[loan["book_id"]]["book_key"] != loan["book_key"]:
            raise ValueError("模拟借阅外键不一致。")
        date.fromisoformat(loan["borrow_date"])
        if loan.get("dataset_label") != "simulated" or loan.get("date_source") != "simulated":
            raise ValueError("模拟借阅日期不能冒充真实日期。")
    for row in read_csv(source/"holdings.csv"):
        count = sum(copy["book_key"] == row["book_key"] and copy["status"] == "available" for copy in copies)
        if row["book_key"] not in engine._books or count != int(row["available"]):
            raise ValueError("模拟馆藏数量与副本状态不一致。")
    current = json.loads((source/"current_borrows.json").read_text(encoding="utf-8"))
    active_copies = []
    for reader, records in current.items():
        if reader not in readers:
            raise ValueError("模拟在借读者不存在。")
        for row in records:
            copy = by_copy.get(row["book_id"])
            if not copy or copy["book_key"] != row["book_key"] or copy["status"] != "on_loan":
                raise ValueError("模拟在借记录与副本状态不一致。")
            if date.fromisoformat(row["due_date"]) < date.fromisoformat(row["borrow_date"]):
                raise ValueError("模拟应还日不能早于借阅日。")
            active_copies.append(row["book_id"])
    if len(active_copies) != len(set(active_copies)) or set(active_copies) != {row["book_id"] for row in copies if row["status"] == "on_loan"}:
        raise ValueError("模拟在借副本必须唯一、完整对应当前借阅。")
    if (len(books),len(copies),len(readers),len(loans)) != tuple(manifest[key] for key in ("book_count","copy_count","reader_count","loan_count")):
        raise ValueError("模拟清单计数不一致。")
    return manifest


def fixture_fingerprint(source=FIXTURE_ROOT):
    manifest = validate_fixture(source)
    return hashlib.sha256("".join(name+digest(Path(source)/name) for name in ["manifest.json"]+manifest["files"]).encode()).hexdigest()


def _output(directory, fingerprint, catalog_required=True):
    directory = Path(directory).resolve()
    if directory == DATA_ROOT.resolve() or directory.is_relative_to((DATA_ROOT/"fixtures").resolve()) or directory.is_relative_to((DATA_ROOT/"shared").resolve()):
        raise ValueError("准备输出不能覆盖已提交的源数据。")
    marker = directory/"prepared-dataset.json"
    if directory.exists() and any(directory.iterdir()):
        if marker.exists() and json.loads(marker.read_text(encoding="utf-8")).get("fingerprint") == fingerprint and (not catalog_required or (directory/"catalog.sqlite3").is_file()):
            return directory, True
        raise ValueError("目标目录非空或来源版本已改变；请指定新的输出目录，不覆盖已有真实批次。")
    directory.mkdir(parents=True, exist_ok=True)
    return directory, False


def prepare_integration(directory, source=FIXTURE_ROOT):
    source = Path(source)
    fingerprint = fixture_fingerprint(source)
    output, ready = _output(directory, fingerprint)
    if ready:
        return output
    manifest = validate_fixture(source)
    for name in manifest["files"]:
        if Path(name).name != name:
            raise ValueError("源清单包含非法文件名。")
        shutil.copyfile(source/name, output/name)
    shutil.copyfile(source/"manifest.json", output/"manifest.json")
    build_catalog(output, output/"catalog.sqlite3", holdings=output/"holdings.csv")
    (output/"prepared-dataset.json").write_text(json.dumps({"dataset_label":"simulated","fingerprint":fingerprint})+"\n",encoding="utf-8")
    return output


def prepare_sources(directory, manifest_path=SOURCES_MANIFEST):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed = {"图书借阅数据.xlsx","座位预约.csv","门禁入馆人次.xlsx","研讨室预约.xlsx","读者数据.csv","门禁刷卡.xlsx","学者库数据.xlsx"}
    archive = manifest_path.parent/manifest["archive"]
    if Path(manifest["archive"]).name != manifest["archive"] or manifest.get("dataset_label") != "real" or digest(archive) != manifest["sha256"]:
        raise ValueError("原始资料包校验失败。")
    output, ready = _output(directory, manifest["sha256"], catalog_required=False)
    if ready:
        return output
    with zipfile.ZipFile(archive) as package:
        if set(package.namelist()) != allowed or len(package.namelist()) != len(allowed):
            raise ValueError("原始资料包清单无效。")
        for name in sorted(allowed):
            if package.getinfo(name).file_size != manifest["files"][name]["bytes"]:
                raise ValueError("原始资料包长度无效。")
            with package.open(name) as source,(output/name).open("wb") as target:
                shutil.copyfileobj(source,target)
            if digest(output/name) != manifest["files"][name]["sha256"]:
                raise ValueError("原始资料包文件指纹不符。")
    (output/"prepared-dataset.json").write_text(json.dumps({"dataset_label":"real","fingerprint":manifest["sha256"]})+"\n",encoding="utf-8")
    return output


def prepare_real(directory, manifest_path=REAL_MANIFEST):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("dataset_label") != "real":
        raise ValueError("真实数据包来源标签无效。")
    archive = manifest_path.parent / manifest["archive"]
    if Path(manifest["archive"]).name != manifest["archive"] or digest(archive) != manifest["sha256"]:
        raise ValueError("真实数据包校验失败。")
    output, ready = _output(directory, manifest["sha256"])
    if ready:
        return output
    allowed = {"books.csv", "borrow_records.csv", "quality_report.json", "catalog_export.csv", "usage.json"}
    with zipfile.ZipFile(archive) as package:
        if set(package.namelist()) != allowed or len(package.namelist()) != len(allowed):
            raise ValueError("真实数据包文件清单无效。")
        for name in sorted(allowed):
            info = package.getinfo(name)
            if info.file_size != manifest["files"][name]["bytes"]:
                raise ValueError("真实数据包文件长度不符。")
            with package.open(name) as source, (output/name).open("wb") as target:
                shutil.copyfileobj(source, target)
            if digest(output/name) != manifest["files"][name]["sha256"]:
                raise ValueError("真实数据包文件指纹不符。")
    Recommender.from_directory(output)
    build_library_catalog(output/"catalog_export.csv", output/"catalog.sqlite3", dataset_label="real")
    if Catalog(output/"catalog.sqlite3").info()["book_count"] != manifest["counts"]["catalog_accepted_rows"]:
        raise ValueError("真实目录导入计数不符。")
    (output/"prepared-dataset.json").write_text(json.dumps({"dataset_label":"real","fingerprint":manifest["sha256"]})+"\n",encoding="utf-8")
    return output

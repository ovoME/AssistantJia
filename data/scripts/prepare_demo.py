"""生成小型、明确标注的虚构服务数据；不读取或覆盖真实数据。"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from data.catalog import build_catalog
from data.scripts.generate_demo import demo_isbn


def prepare(directory):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()) and not (directory / "demo-manifest.json").exists():
        raise ValueError("目标目录非空且不是本工具生成的演示目录，请使用新目录。")
    directory.mkdir(parents=True, exist_ok=True)
    titles = ["虚构图书：海风与星光", "虚构图书：潮汐与远航", "虚构图书：Python程序设计",
              "虚构图书：Python实践", "虚构图书：经济入门", "虚构图书：历史漫步"]
    categories = [("I", "文学"), ("I", "文学"), ("T", "工业技术"), ("T", "工业技术"), ("F", "经济"), ("K", "历史")]
    pairs = [("demo-reader", 0), ("demo-reader", 2), ("demo-peer", 0), ("demo-peer", 1),
             ("demo-peer", 3), ("demo-other", 4), ("demo-other", 5), ("demo-other", 0)]
    counts = Counter(index for _, index in pairs)
    books = [{"book_key": "isbn:" + demo_isbn(i + 1), "title": title, "author": "虚构作者" + str(i),
              "isbn": demo_isbn(i + 1), "call_number": ("TP311" if i in (2, 3) else categories[i][0] + "247") + "/" + str(i + 1),
              "publisher": "虚构出版社", "category_code": categories[i][0], "category_name": categories[i][1],
              "borrow_count": str(counts[i])} for i, title in enumerate(titles)]
    loans = [{**{key: value for key, value in books[i].items() if key != "borrow_count"},
              "reader_id": reader, "book_id": "DEMO-COPY-" + str(i), "source_row": str(row + 2)}
             for row, (reader, i) in enumerate(pairs)]
    for name, rows in (("books.csv", books), ("borrow_records.csv", loans)):
        with (directory / name).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    report = {"dataset_label": "simulated", "accepted_rows": len(loans), "description": "全部为虚构演示数据。"}
    for name in ("quality_report.json", "demo-manifest.json"):
        (directory / name).write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
    build_catalog(directory, directory / "catalog.sqlite3")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/processed/service-demo"))
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.output), ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"演示初始化失败：{exc}\n")


if __name__ == "__main__":
    main()

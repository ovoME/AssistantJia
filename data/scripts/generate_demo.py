"""生成完全虚构的测试借阅 CSV。编号、书名、作者及出版社均非馆方数据。"""
import argparse
import csv
import json
import random
from pathlib import Path

HEADERS = ["证件号", "索书号", "财产号", "题名", "责任者", "IISSBN", "出版社"]
CATEGORY_CODES = ["I", "T", "F", "B", "H", "J", "C", "K", "G", "Z"]


def demo_isbn(index):
    base = f"9787000{index:05d}"
    check = (-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))) % 10
    return base + str(check)


def demo_rows(count=36908, seed=20261023):
    if count < 0:
        raise ValueError("行数不能为负数。")
    rng = random.Random(seed)
    rows = []
    for i in range(count):
        reader = i % 358 if i < 358 else rng.randrange(358)
        book = i % 200 if i < 200 else (rng.randrange(30) if rng.random() < 0.65 else rng.randrange(200))
        category = CATEGORY_CODES[book % len(CATEGORY_CODES)]
        row = [f"{reader + 1:06d}", f"{category}{100 + book}/M{book:03d}",
               f"{book * 3 + rng.randrange(3) + 1:08d}", f"模拟图书{book + 1:04d}",
               f"模拟作者{book % 40 + 1:02d}", demo_isbn(book), f"模拟出版社{book % 12 + 1:02d}"]
        # 注入缺失、错号、空白、未知分类及重复导出，用于验证质量报告。
        if i % 997 == 0:
            row[0] = ""
        if i % 1237 == 0:
            row[3] = ""
        elif i % 17 == 0:
            row[3] = "  " + row[3] + "　 "
        if i % 71 == 0:
            row[6] = ""
        if i % 97 == 0:
            row[5] = ""
        elif i % 131 == 0:
            row[5] = "9780000000000"
        elif i % 11 == 0:
            row[5] = row[5][:3] + "-" + row[5][3:]
        if i % 149 == 0:
            row[1] = "???"
        elif i % 13 == 0:
            row[1] = " " + row[1].lower() + " "
        rows.append(row)
    if count >= 20:
        rows[-8:] = [r.copy() for r in rows[1:9]]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=36908)
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--output", type=Path, default=Path("data/demo/borrow_records_demo.csv"))
    args = parser.parse_args()
    if args.rows < 0:
        parser.error("--rows 不能为负数。")
    rows = demo_rows(args.rows, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADERS)
        writer.writerows(rows)
    metadata = {"dataset_label": "simulated", "input_rows": len(rows), "seed": args.seed,
                "description": "全部为虚构测试数据，不能用于馆方业务结论。",
                "reader_pool": 358, "book_pool": 200,
                "injected_cases": ["缺失证件号", "缺失题名", "空白出版社", "ISBN错号和缺失", "未知分类", "相同流水"]}
    args.output.with_suffix(".metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {len(rows):,} 条模拟数据：{args.output}")


if __name__ == "__main__":
    main()

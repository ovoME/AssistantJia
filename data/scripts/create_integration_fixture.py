"""维护用：生成提交到 Git 的虚构联调源文件，不读取真实借阅表。"""
import csv
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from data.scripts.generate_demo import demo_isbn

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "integration"


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(directory=ROOT):
    directory.mkdir(parents=True, exist_ok=True)
    names = ["三体", "平凡的世界", "Python编程：从入门到实践", "深入理解计算机系统", "物流管理",
             "供应链管理", "高等数学", "大学英语", "算法导论", "人工智能导论", "数据库系统",
             "经济学原理", "微观经济学", "中国历史", "嘉庚文化读本", "海洋科学入门",
             "线性代数", "机器学习基础", "现代汉语", "阅读与写作"]
    classes = ["I247.55", "I247.57", "TP311.56", "TP3", "F252.8", "F252", "O13", "H31", "TP301.6", "TP18",
               "TP311.13", "F0", "F016", "K20", "K825", "P7", "O151.2", "TP181", "H109", "I04"]
    category_names = {"I": "文学", "T": "工业技术", "F": "经济", "O": "数理科学", "H": "语言文字", "K": "历史", "P": "天文学地球科学"}
    books = [{"book_key": "isbn:" + demo_isbn(i+1), "title": name, "author": f"模拟作者{i+1:02d}",
              "isbn": demo_isbn(i+1), "call_number": classes[i] + "/" + str(i+7), "publisher": "模拟联调出版社",
              "category_code": classes[i][0], "category_name": category_names[classes[i][0]], "borrow_count": "0"}
             for i, name in enumerate(names)]
    reader_ids = ["demo-reader", "demo-peer"] + [f"demo-reader-{i:03d}" for i in range(3, 13)]
    readers = [{"reader_id": key, "name": f"模拟读者{i+1:02d}", "department": "模拟院系"+str(i%3+1),
                "dataset_label": "simulated"} for i, key in enumerate(reader_ids)]
    copies = [{"book_id": f"DEMO-JGG-{i+1:06d}", "catalog_id": f"DEMO-CAT-{i//2+1:04d}",
               "book_key": books[i//2]["book_key"], "call_number": books[i//2]["call_number"],
               "location": f"模拟主楼{2+i//14}层 · 模拟书架{i//4+1:02d}",
               "status": "available", "updated_at": "2026-09-30T23:00:00+08:00", "dataset_label": "simulated"}
              for i in range(40)]
    loans, current = [], defaultdict(list)
    for day in range(30):
        borrowed = date(2026, 9, 1) + timedelta(days=day)
        for offset in range(6):
            copy_index = (day*7+offset) % 40 if day < 29 else offset
            item = copies[copy_index]
            book = books[copy_index//2]
            reader = reader_ids[(day+offset*2) % 12] if not (day == 29 and offset == 0) else "demo-reader"
            loans.append({**{key: value for key, value in book.items() if key != "borrow_count"},
                          "reader_id": reader, "book_id": item["book_id"], "source_row": str(len(loans)+2),
                          "borrow_date": borrowed.isoformat(), "return_date": (borrowed+timedelta(days=1)).isoformat() if day < 29 else "",
                          "date_source": "simulated", "dataset_label": "simulated"})
            if day == 29:
                item["status"] = "on_loan"
                current[reader].append({"book_id": item["book_id"], "book_key": item["book_key"], "title": book["title"],
                                        "borrow_date": borrowed.isoformat(), "due_date": (borrowed+timedelta(days=60)).isoformat(),
                                        "renew_count": 3 if offset == 1 else 0, "is_overdue": False,
                                        "dataset_label": "simulated", "is_live": False})
    counts = Counter(row["book_key"] for row in loans)
    for book in books:
        book["borrow_count"] = str(counts[book["book_key"]])
    holdings = [{"book_key": book["book_key"], "location": copies[i*2]["location"],
                 "available": sum(row["status"] == "available" for row in copies[i*2:i*2+2]),
                 "status": "模拟在馆" if any(row["status"] == "available" for row in copies[i*2:i*2+2]) else "模拟借出",
                 "checked_at": "2026-09-30T23:00:00+08:00", "source": "synthetic_integration_v1"}
                for i, book in enumerate(books)]
    crosswalk = [{key: row[key] for key in ("book_id", "catalog_id", "book_key", "dataset_label")} for row in copies]
    for filename, rows in (("books.csv", books), ("borrow_records.csv", loans), ("readers.csv", readers),
                           ("copies.csv", copies), ("holdings.csv", holdings), ("book_crosswalk.csv", crosswalk)):
        write_csv(directory / filename, rows)
    quality = {"dataset_label": "simulated", "accepted_rows": len(loans), "date_source": "simulated"}
    manifest = {"schema_version": 1, "dataset_label": "simulated", "as_of": "2026-09-30T23:00:00+08:00",
                "book_count": len(books), "copy_count": len(copies), "reader_count": len(readers), "loan_count": len(loans),
                "date_range": ["2026-09-01", "2026-09-30"], "description": "全部为虚构联调数据；不代表真实读者、书目元数据、日期、架位或库存。",
                "files": ["books.csv", "borrow_records.csv", "readers.csv", "copies.csv", "holdings.csv", "book_crosswalk.csv", "current_borrows.json", "quality_report.json", "usage.json"],
                "example_queries": ["三体", "物流", "Python", "F252.8/11"]}
    for name, value in (("quality_report.json", quality), ("manifest.json", manifest), ("current_borrows.json", dict(current))):
        (directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    usage = {"dataset_label":"simulated","is_live":False,"datasets":{},"limitations":["全部为独立虚构的资源统计汇总，仅供联调。"]}
    for key, filename, count, distinct in [("seats","模拟座位预约.csv",120,10),("rooms","模拟研讨室预约.csv",30,8),
                                          ("gate_events","模拟门禁刷卡.csv",300,12),("gate_counts","模拟门禁汇总.csv",12,12),
                                          ("readers","模拟读者.csv",12,12),("scholars","模拟学者库.csv",20,None)]:
        usage["datasets"][key] = {"source_file":filename,"rows":count,"distinct_source_readers":distinct,
                                   "observed_date_min":"2026-09-01","observed_date_max":"2026-09-30"}
    (directory/"usage.json").write_text(json.dumps(usage,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    generate()

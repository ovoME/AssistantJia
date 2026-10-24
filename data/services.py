"""C5 只读借阅服务；复用标准库推荐索引计算统计，避免多个 JSON 批次混用。"""
from collections import Counter
from data.recommendation import Recommender, _read_csv, LOAN_FIELDS


class BorrowingData:
    def __init__(self, directory):
        self.engine = Recommender.from_directory(directory)
        self.loans = _read_csv(directory / "borrow_records.csv", LOAN_FIELDS | {"title", "category_code", "category_name", "publisher"})
        titles = {row["title"] for row in self.loans}
        self.summary = {"total_borrows": len(self.loans), "total_readers": len(self.engine._histories),
                        "total_titles": len(titles),
                        "avg_borrow_per_reader": round(len(self.loans) / len(self.engine._histories), 4)
                        if self.engine._histories else None}
        categories = Counter((row["category_code"], row["category_name"]) for row in self.loans)
        total = len(self.loans)
        self.categories = [{"category": code, "category_name": name, "count": count,
                            "share": count / total if total else 0}
                           for (code, name), count in sorted(categories.items(), key=lambda item: (-item[1], item[0]))]
        publishers = Counter(row["publisher"] for row in self.loans)
        self.publishers = [{"publisher": name, "count": count, "publisher_missing": not bool(name)}
                           for name, count in sorted(publishers.items(), key=lambda item: (-item[1], item[0]))]

    def metadata(self):
        return {"dataset_label": self.engine.dataset_label, "scope": "historical_borrow_records", "is_live": False,
                "limitations": ["数据仅代表历史借阅样本，不代表馆藏全量或当前在借状态。",
                                "借阅源没有日期，不提供借阅趋势或近期结论。"]}

    def purchase_advice(self, category=None):
        books = self.engine.hot_books(category, 5)
        lines = ["历史借阅需求参考", f"本批包含 {self.summary['total_borrows']} 条借阅流水。"]
        lines += [f"《{book['title']}》：历史借阅 {book['count']} 次。" for book in books]
        lines += ["以上仅用于馆员核查需求，不等同于增购结论。",
                  "缺少统计时间、馆藏复本、利用率与预约排队数据，不能计算复购率或判断长期零借阅。"]
        return {"report": "\n".join(lines), "generated_by": "historical_statistics_template", "is_ai_generated": False}

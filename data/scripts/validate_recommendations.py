"""本地验证 C2，报告仅含汇总；不导出读者 ID、逐人书单或借阅记录。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from data.recommendation import Recommender, STRATEGIES


def _metadata(book):
    return tuple(" ".join(unicodedata.normalize("NFKC", book[c]).split()).casefold()
                 for c in ("title", "author", "publisher"))


def _read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate(directory: Path, limit: int = 20, holdout_readers: int = 200, progress=None) -> dict:
    if not 1 <= limit <= 100 or holdout_readers < 0:
        raise ValueError("limit 需为 1 到 100，holdout_readers 不能为负数。")
    started = time.perf_counter()
    engine = Recommender.from_directory(directory)
    books = _read(directory / "books.csv")
    loans = _read(directory / "borrow_records.csv")
    catalog = {book["book_key"]: book for book in books}
    histories = defaultdict(set)
    metadata_isbns = defaultdict(set)
    for key, book in catalog.items():
        metadata = _metadata(book)
        if key.startswith("isbn:"):
            metadata_isbns[metadata].add(key)
    for loan in loans:
        histories[loan["reader_id"]].add(loan["book_key"])
    strategies = {}
    for strategy in STRATEGIES:
        latencies, returned, empty = [], 0, 0
        methods = Counter()
        for index, (reader, history) in enumerate(sorted(histories.items()), start=1):
            excluded_metadata = {_metadata(catalog[key]) for key in history
                                 if all(_metadata(catalog[key])) and len(metadata_isbns[_metadata(catalog[key])]) <= 1}
            start = time.perf_counter()
            payload = engine.response(reader, limit=limit, strategy=strategy)
            latencies.append(time.perf_counter() - start)
            rows = payload["data"]
            keys = [row["book_key"] for row in rows]
            if len(keys) > limit or len(set(keys)) != len(keys) or set(keys) & history:
                raise ValueError("推荐存在已读重叠、重复候选或超出 limit。")
            if payload["dataset_label"] != engine.dataset_label or '"reader_id"' in json.dumps(payload):
                raise ValueError("响应来源标识或隐私字段检查失败。")
            for row in rows:
                if row["book_key"] not in catalog or _metadata(row) in excluded_metadata:
                    raise ValueError("推荐出现不在源书目中的候选，或推荐了可精确确认的同一本已读书。")
                if not math.isfinite(row["score"]) or not 0 <= row["score"] <= 1:
                    raise ValueError("推荐分数无效。")
                if not {"title", "author", "isbn", "call_number", "reason"}.issubset(row):
                    raise ValueError("推荐缺少接口约定字段。")
                methods[row["strategy"]] += 1
            returned += len(rows)
            empty += int(not rows)
            if progress and (index % 500 == 0 or index == len(histories)):
                progress(f"{strategy}: {index}/{len(histories)} readers checked")
        strategies[strategy] = {
            "queries": len(histories), "returned": returned, "empty_queries": empty,
            "history_overlap": 0, "duplicate_candidates": 0, "methods": dict(methods),
            "latency_p50_seconds": round(statistics.median(latencies), 6) if latencies else None,
            "latency_p95_seconds": round(sorted(latencies)[max(0, math.ceil(len(latencies) * 0.95) - 1)], 6) if latencies else None,
        }
    for strategy in STRATEGIES:
        if engine.recommend(None, limit, strategy=strategy) != engine.recommend(
            "__unseen_reader_validation_1a08__", limit, strategy=strategy
        ):
            raise ValueError("冷启动兜底与未知读者结果不一致。")
    report = {
        "dataset_label": engine.dataset_label, "accepted_rows": len(loans),
        "source_book_keys": len(catalog), "recommendation_book_keys": len(engine._books),
        "reader_count": len(histories), "limit": limit, "strategies": strategies,
        "cold_start_checks": len(STRATEGIES),
        "holdout": evaluate_holdout(engine, catalog, loans, min(limit, 10), holdout_readers),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    return report


def evaluate_holdout(engine, catalog, loans, limit=10, max_readers=200):
    """固定哈希抽样留一法；移除被留出书种的所有复借流水，重新计算训练次数。"""
    selected = sorted((reader for reader, history in engine._histories.items() if len(history) >= 2),
                      key=lambda reader: _digest("c2-eval-20261024/" + reader))[:max_readers]
    heldout = {reader: min(engine._histories[reader], key=lambda key: _digest(reader + "/" + key))
               for reader in selected}
    training, removed = build_holdout(engine, catalog, loans, heldout)
    metrics = {}
    for strategy in STRATEGIES:
        hits, reciprocal_rank, ndcg = 0, 0.0, 0.0
        for reader, target in heldout.items():
            keys = [row["book_key"] for row in training.recommend(reader, limit=limit, strategy=strategy)]
            if target in keys:
                rank = keys.index(target) + 1
                hits += 1
                reciprocal_rank += 1 / rank
                ndcg += 1 / math.log2(rank + 1)
        n = len(heldout)
        metrics[strategy] = {"hits": hits, "hit_rate": round(hits / n, 6) if n else None,
                             "mrr": round(reciprocal_rank / n, 6) if n else None,
                             "ndcg": round(ndcg / n, 6) if n else None}
    return {
        "method": "deterministic_leave_one_distinct_book_out", "limit": limit,
        "evaluated_readers": len(heldout), "removed_loan_rows": removed,
        "heldout_books_with_training_borrows": sum(bool(training._counts[key]) for key in heldout.values()),
        "training_rows": len(loans) - removed, "metrics": metrics,
        "limitations": "没有借阅日期；这是固定哈希抽样的离线回放，不代表未来借阅、用户满意度或线上效果。",
    }


def build_holdout(engine, catalog, loans, heldout):
    """训练前移除所有目标及其别名的复借；保留静态书目，包括零训练次数书。"""
    canonical_by_metadata = defaultdict(list)
    for key, book in engine._books.items():
        canonical_by_metadata[_metadata(book)].append(key)
    aliases = {}
    for key, book in catalog.items():
        if key in engine._books:
            aliases[key] = key
        else:
            matches = canonical_by_metadata[_metadata(book)]
            if len(matches) != 1:
                raise ValueError("留出评估无法确认归并后的书目关系。")
            aliases[key] = matches[0]
    training_loans = []
    counts = Counter()
    removed = 0
    for loan in loans:
        reader, key = loan["reader_id"], aliases[loan["book_key"]]
        if heldout.get(reader) == key:
            removed += 1
            continue
        training_loans.append({"reader_id": reader, "book_key": key})
        counts[key] += 1
    training_books = [{**book, "borrow_count": str(counts[key])} for key, book in engine._books.items()]
    training = Recommender(training_books, training_loans, engine.dataset_label)
    if any(target in training._histories.get(reader, set()) for reader, target in heldout.items()):
        raise ValueError("留出书种仍在训练历史中，存在数据泄漏。")
    return training, removed


def main():
    parser = argparse.ArgumentParser(description="验证 C2 全部读者四种策略，并输出无个人明细的汇总报告。")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--holdout-readers", type=int, default=200)
    parser.add_argument("--output", type=Path, default=Path("data/processed/recommendation_validation.json"))
    args = parser.parse_args()
    try:
        report = validate(args.data_dir, args.limit, args.holdout_readers,
                          progress=lambda message: print(message, file=sys.stderr, flush=True))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        args.output.write_text(encoded, encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"推荐验证失败：{exc}\n")
    print(encoded, end="")


if __name__ == "__main__":
    main()

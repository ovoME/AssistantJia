"""在互斥留出读者上对比探索推荐与旧方案，只输出汇总，不输出个人数据。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from data.recommendation import Recommender
from data.scripts.compare_recommendations import SPLIT_VERSION, split_readers
from data.scripts.validate_recommendations import _read, build_holdout


def evaluate(directory: Path, validation_size=1200, test_size=100, legacy_size=200, limit=5, progress=None):
    engine = Recommender.from_directory(directory)
    books = _read(directory / "books.csv")
    loans = _read(directory / "borrow_records.csv")
    groups = split_readers(engine, validation_size, test_size, legacy_size)
    training, removed = build_holdout(engine, {row["book_key"]: row for row in books}, loans,
                                     {**groups["validation"], **groups["test"]})
    hits = {"previous_hybrid": 0, "discovery_first": 0, "discovery_second": 0}
    overlaps, latencies = [], []
    for index, (reader, target) in enumerate(groups["test"].items(), 1):
        seed = int.from_bytes(hashlib.sha256(("discovery-eval/" + reader).encode()).digest()[:8], "big")
        baseline = training.recommend(reader, limit=limit)
        started = time.perf_counter()
        first = training.discover(reader, limit=limit, rng=random.Random(seed))
        latencies.append(time.perf_counter() - started)
        first_keys = [row["book_key"] for row in first]
        second = training.discover(reader, limit=limit, avoid=first_keys, rng=random.Random(seed + 1))
        second_keys = [row["book_key"] for row in second]
        for keys in (first_keys, second_keys):
            if len(keys) > limit or len(keys) != len(set(keys)) or set(keys) & training._histories[reader]:
                raise ValueError("探索推荐包含重复或已读图书。")
        hits["previous_hybrid"] += target in {row["book_key"] for row in baseline}
        hits["discovery_first"] += target in first_keys
        hits["discovery_second"] += target in second_keys
        overlaps.append(len(set(first_keys) & set(second_keys)))
        if progress and index % 25 == 0:
            progress(f"独立测试：{index}/{len(groups['test'])}")
    size = len(groups["test"])
    return {
        "dataset_label": engine.dataset_label,
        "split_version": SPLIT_VERSION,
        "validation_readers": len(groups["validation"]),
        "test_readers": size,
        "excluded_legacy_readers": legacy_size,
        "removed_loan_rows": removed,
        "limit": limit,
        "hits_at_limit": hits,
        "hit_rate_at_limit": {name: round(count / size, 4) for name, count in hits.items()},
        "mean_repeated_books": round(statistics.mean(overlaps), 3),
        "max_repeated_books": max(overlaps),
        "first_batch_latency_median_seconds": round(statistics.median(latencies), 4),
        "first_batch_latency_p95_seconds": round(sorted(latencies)[math.ceil(size * 0.95) - 1], 4),
        "limitations": "无借阅日期；固定种子和互斥读者的留一回放，不能代表未来借阅、满意度或线上效果。",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    # 原有 C2 报告已查看 600 名验证读者与 600 名测试读者；新测试排除这 1200 人。
    parser.add_argument("--validation-size", type=int, default=1200)
    parser.add_argument("--test-size", type=int, default=100)
    parser.add_argument("--legacy-size", type=int, default=200)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        if not 1 <= args.limit <= 100:
            raise ValueError("limit 必须是 1 到 100 的整数。")
        report = evaluate(args.data_dir, args.validation_size, args.test_size, args.legacy_size, args.limit,
                          lambda message: print(message, file=sys.stderr, flush=True))
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"探索推荐评估失败：{exc}\n")


if __name__ == "__main__":
    main()

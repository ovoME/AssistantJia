"""C2 优化对照：验证集选权重，独立测试集只评估冻结方案；只导出汇总。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from data.recommendation import Recommender
from data.scripts.validate_recommendations import _digest, _read, build_holdout

WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
SPLIT_VERSION = "c2-content-v1-20261024"


def split_readers(engine, validation_size=600, test_size=600, legacy_size=200):
    if min(validation_size, test_size) < 1 or legacy_size < 0:
        raise ValueError("验证和测试人数须为正数，旧样本排除人数不能为负数。")
    eligible = [reader for reader, history in engine._histories.items() if len(history) >= 2]
    legacy = set(sorted(eligible, key=lambda reader: _digest("c2-eval-20261024/" + reader))[:legacy_size])
    fresh = sorted(set(eligible) - legacy, key=lambda reader: _digest(SPLIT_VERSION + "/reader/" + reader))
    if len(fresh) < validation_size + test_size:
        raise ValueError("至少借过两个不同书种的读者不足以完成指定的互斥拆分。")
    groups = {"validation": fresh[:validation_size], "test": fresh[validation_size:validation_size + test_size]}
    return {group: {reader: min(engine._histories[reader],
                               key=lambda key: _digest(SPLIT_VERSION + "/target/" + reader + "/" + key))
                    for reader in readers} for group, readers in groups.items()}


def metrics(ranks):
    size = len(ranks)
    hits = sum(rank > 0 for rank in ranks)
    return {"readers": size, "hits": hits, "hit_rate": round(hits / size, 6) if size else None,
            "mrr": round(sum(1 / rank for rank in ranks if rank) / size, 6) if size else None,
            "ndcg": round(sum(1 / math.log2(rank + 1) for rank in ranks if rank) / size, 6) if size else None}


def compare(directory, phase, selection=None, validation_size=600, test_size=600, legacy_size=200, progress=None):
    if phase not in {"validation", "test"}:
        raise ValueError("phase 必须是 validation 或 test。")
    engine = Recommender.from_directory(directory)
    books, loans = _read(directory / "books.csv"), _read(directory / "borrow_records.csv")
    groups = split_readers(engine, validation_size, test_size, legacy_size)
    settings = {"split_version": SPLIT_VERSION, "validation_size": validation_size,
                "test_size": test_size, "excluded_legacy_readers": legacy_size, "limit": 10,
                "source_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                  for name in ("books.csv", "borrow_records.csv")}}
    if phase == "test":
        if not isinstance(selection, dict) or selection.get("phase") != "validation" or selection.get("settings") != settings:
            raise ValueError("测试需要同一数据、同一拆分的验证报告。")
        selected_weight = selection.get("selected_weight")
        if selected_weight not in WEIGHTS or selected_weight != Recommender.CONTENT_WEIGHT:
            raise ValueError("须先将生产默认权重冻结为验证集选择的权重，再运行独立测试。")
        weights = tuple(dict.fromkeys((0.0, selected_weight)))
    else:
        weights = WEIGHTS
    training, removed = build_holdout(engine, {book["book_key"]: book for book in books}, loans,
                                     {**groups["validation"], **groups["test"]})
    targets = groups[phase]
    results, hit_flags = {}, {}
    for weight in weights:
        training.CONTENT_WEIGHT = weight
        ranks, warm, cold = [], [], []
        for reader, target in targets.items():
            keys = [row["book_key"] for row in training.recommend(reader, limit=10)]
            rank = keys.index(target) + 1 if target in keys else 0
            ranks.append(rank)
            (warm if training._counts[target] else cold).append(rank)
        results[str(weight)] = {**metrics(ranks), "with_training_borrows": metrics(warm),
                                "without_training_borrows": metrics(cold)}
        hit_flags[weight] = [bool(rank) for rank in ranks]
        if progress:
            progress(f"{phase}: content_weight={weight}, readers={len(ranks)}, hits={sum(hit_flags[weight])}")
    if phase == "validation":
        # 先命中人数，再 MRR，最后较低权重；测试集不参与选择。
        selected_weight = max(weights, key=lambda weight: (results[str(weight)]["hits"],
                                                          results[str(weight)]["mrr"], -weight))
    baseline, chosen = hit_flags[0.0], hit_flags[selected_weight]
    return {"phase": phase, "dataset_label": engine.dataset_label, "settings": settings,
            "removed_loan_rows": removed, "training_rows": len(loans) - removed,
            "selected_weight": selected_weight, "results": results,
            "paired_hits": {"improved_only": sum(b and not a for a, b in zip(baseline, chosen)),
                            "baseline_only": sum(a and not b for a, b in zip(baseline, chosen)),
                            "both": sum(a and b for a, b in zip(baseline, chosen))},
            "limitations": "无日期的离线留出；共享训练集已移除验证和测试目标全部复借。静态书目可见，不能推断未来或线上效果。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--phase", choices=("validation", "test"), required=True)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--validation-size", type=int, default=600)
    parser.add_argument("--test-size", type=int, default=600)
    parser.add_argument("--legacy-size", type=int, default=200)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        selection = json.loads(args.selection.read_text(encoding="utf-8")) if args.selection else None
        report = compare(args.data_dir, args.phase, selection, args.validation_size, args.test_size,
                         args.legacy_size, lambda message: print(message, file=sys.stderr, flush=True))
        encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"推荐对照失败：{exc}\n")


if __name__ == "__main__":
    main()

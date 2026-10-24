"""C3 建库：python -m data.scripts.build_catalog --data-dir data/processed"""

import argparse
import json
import sqlite3
from pathlib import Path

from data.catalog import build_catalog, build_library_catalog


def main():
    parser = argparse.ArgumentParser(description="从馆藏导出 CSV 或 C1 books.csv 构建 C3 本地书目检索库。")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--data-dir", type=Path, help="C1 清洗输出目录，默认为 data/processed。")
    inputs.add_argument("--input", type=Path, help="馆藏导出 CSV，包含 ID/TITLE 等列。")
    parser.add_argument("--dataset-label", choices=("real", "simulated", "unknown"), help="仅用于 --input，默认 unknown。")
    parser.add_argument("--database", type=Path, default=Path("data/processed/catalog.sqlite3"))
    parser.add_argument("--holdings", type=Path, help="可选的馆藏快照 CSV，必须提供来源与时间。")
    args = parser.parse_args()
    if args.dataset_label is not None and args.input is None:
        parser.error("--dataset-label 仅用于 --input；C1 模式从质量报告读取来源。")
    try:
        if args.input is not None:
            metadata = build_library_catalog(args.input, args.database, args.holdings, args.dataset_label or "unknown")
        else:
            metadata = build_catalog(args.data_dir or Path("data/processed"), args.database, args.holdings)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"书目建库失败：{exc}\n")
    print(json.dumps(metadata, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

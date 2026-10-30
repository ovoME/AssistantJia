"""运行示例：python -m data.scripts.clean_data --input data/demo/borrow_records_demo.csv --dataset-label simulated"""
import argparse
import json
from pathlib import Path

from data.pipeline import clean_file


def main():
    parser = argparse.ArgumentParser(description="清洗小嘉借阅流水，保留疑似重复并生成质量报告。")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--dataset-label", choices=["simulated", "real", "unknown"], default="unknown")
    parser.add_argument("--sheet", help="XLSX 工作表名称，省略为第一个工作表。")
    args = parser.parse_args()
    try:
        report = clean_file(args.input, args.output_dir, args.dataset_label, args.sheet if args.sheet else 0)
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"清洗失败：{exc}\n")
    print(json.dumps({k: report[k] for k in ("dataset_label", "input_rows", "accepted_rows", "rejected_rows", "invalid_isbn_rows")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

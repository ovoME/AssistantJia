"""运行示例：python -m data.scripts.analyze"""
import argparse
import json
from pathlib import Path

from data.pipeline import analyze_file


def main():
    parser = argparse.ArgumentParser(description="从清洗后的借阅流水导出榜单、分类和读者偏好。")
    parser.add_argument("--input", type=Path, default=Path("data/processed/borrow_records.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    try:
        summary = analyze_file(args.input, args.output_dir)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"统计失败：{exc}\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

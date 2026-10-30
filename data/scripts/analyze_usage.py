import argparse
import json
import sys
from pathlib import Path
from data.usage import analyze_usage


def main():
    parser = argparse.ArgumentParser(description="逐表生成座位、研讨室、门禁、读者、学者库的聚合统计，不导出身份明细。")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--dataset-label", choices=("real", "simulated", "unknown"), default="unknown")
    parser.add_argument("--output", type=Path, default=Path("data/processed/usage.json"))
    args = parser.parse_args()
    try:
        if args.output.resolve().is_relative_to(args.input_dir.resolve()):
            raise ValueError("报告应写入独立输出目录，不能写到原始资料目录。")
        report = analyze_usage(args.input_dir, args.dataset_label,
                               lambda message: print(message, file=sys.stderr, flush=True))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"dataset_label": report["dataset_label"], "datasets": len(report["datasets"])}, ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"聚合失败：{exc}\n")


if __name__ == "__main__":
    main()

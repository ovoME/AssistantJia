"""运行 C2：python -m data.scripts.recommend --reader-id 000001 --limit 5"""

import argparse
import json
from pathlib import Path

from data.recommendation import Recommender, STRATEGIES


def main():
    parser = argparse.ArgumentParser(description="从本地 C1 完整流水生成 C2 推荐，不联网。")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--reader-id", help="仅用于本地测试；服务端应使用已认证身份。")
    parser.add_argument("--category", help="中图大类或字母前缀，如 I、T、TP、UNKNOWN。")
    parser.add_argument("--strategy", choices=("discovery", *STRATEGIES), default="discovery")
    parser.add_argument("--query", help="可选书名、作者或主题；仅 discovery 策略支持。")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path, help="可选 JSON 文件路径，建议保存在 data/processed/ 内。")
    args = parser.parse_args()
    try:
        engine = Recommender.from_directory(args.data_dir)
        response = engine.response(args.reader_id, args.limit, args.category, args.strategy, args.query)
        encoded = json.dumps(response, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"推荐失败：{exc}\n")
    print(encoded, end="")


if __name__ == "__main__":
    main()

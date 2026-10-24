"""C3 检索：python -m data.scripts.search_catalog --query 模拟图书"""

import argparse
import json
import sqlite3
from pathlib import Path

from data.catalog import Catalog


def main():
    parser = argparse.ArgumentParser(description="查询本地书目；无结果返回空列表，不生成馆藏状态。")
    parser.add_argument("--database", type=Path, default=Path("data/processed/catalog.sqlite3"))
    parser.add_argument("--query", required=True, help="书名、作者、出版社、ISBN 或索书号；空白分隔词均需匹配。")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        payload = Catalog(args.database).response(args.query, args.limit)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(2, f"书目检索失败：{exc}\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

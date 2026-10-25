"""从核对后的馆方规则摘要生成可审计向量索引。"""
import argparse
import json
from pathlib import Path
from data.knowledge import KnowledgeBase, DEFAULT_SOURCE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=Path("data/processed/knowledge-index.json"))
    parser.add_argument("--question")
    args = parser.parse_args()
    try:
        if args.output.resolve() == args.source.resolve():
            raise ValueError("索引不能覆盖来源清单。")
        kb = KnowledgeBase(args.source)
        report = kb.export(args.output)
        if args.question:
            report["result"] = kb.answer(args.question)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"规则索引失败：{exc}\n")
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()

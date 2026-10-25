import argparse
import json
from pathlib import Path
from data.datasets import prepare_integration, prepare_real, prepare_sources


def main():
    parser = argparse.ArgumentParser(description="准备仓库内模拟联调数据，或校验并导入从团队共享盘取得的真实数据包。")
    parser.add_argument("--dataset", choices=("integration", "real", "originals"), default="integration")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path("data/processed/shared-"+args.dataset+("-v1" if args.dataset == "integration" else ""))
    try:
        directory = {"real":prepare_real,"integration":prepare_integration,"originals":prepare_sources}[args.dataset](output)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"数据准备失败：{exc}\n")
    print(json.dumps({"dataset":args.dataset,"directory":str(directory)},ensure_ascii=False))


if __name__ == "__main__":
    main()

"""显式选择独立虚构数据启动本机联调服务；保持原有管理/读者鉴权。"""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    environment = {**os.environ,"DATA_PROFILE":"integration",
                   "PYTHONPATH":os.pathsep.join([str(root),str(root/"backend"),os.environ.get("PYTHONPATH","")])}
    print("启动独立模拟联调数据；管理与个人接口仍须配置有效凭证。",flush=True)
    result = subprocess.run([sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port",str(args.port)],
                            cwd=root,env=environment)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

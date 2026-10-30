"""供可信运维/登录端签发短期凭证；没有公开的按任意读者号签发 HTTP 接口。"""
import argparse
import time
from app.auth import sign_reader_token
from app.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reader-id", required=True)
    parser.add_argument("--minutes", type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.minutes <= 1440:
        parser.error("凭证有效期应为 1 到 1440 分钟。")
    try:
        print(sign_reader_token(args.reader_id, settings.READER_TOKEN_SECRET or "", time.time() + args.minutes * 60))
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()

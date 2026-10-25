"""C1 清洗与 C3 检索共用的 ISBN 校验；仅依赖标准库。"""

import re


def canonical_isbn(value: str) -> str:
    """合法 ISBN 返回 ISBN13；错误号码返回空串，不把错号当图书主键。"""
    if re.fullmatch(r"\d{9}[\dX]", value):
        digits = [int(c) if c != "X" else 10 for c in value]
        if sum((10 - i) * d for i, d in enumerate(digits)) % 11:
            return ""
        base = "978" + value[:9]
        check = (-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(base))) % 10
        return base + str(check)
    if re.fullmatch(r"97[89]\d{10}", value):
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value))
        return value if total % 10 == 0 else ""
    return ""

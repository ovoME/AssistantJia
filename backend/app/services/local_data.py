"""按配置缓存已加载实例，文件变更触发重载；失败时不回退到模拟结果。"""
from functools import lru_cache
from functools import wraps
from pathlib import Path
import json
import sqlite3

from app.config import settings
from app.services.provider import DemoProvider, DisabledProvider
from data.catalog import Catalog
from data.knowledge import KnowledgeBase
from data.services import BorrowingData


class DataUnavailable(RuntimeError):
    pass


def checked_loader(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (OSError, ValueError, KeyError, sqlite3.DatabaseError) as exc:
            raise DataUnavailable("数据文件缺失、格式无效或批次不一致，请初始化或重新发布完整数据批次。") from exc
    return wrapped


def signature(paths):
    return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)


@lru_cache(maxsize=2)
def _borrowing(captured):
    return BorrowingData(Path(captured[0][0]).parent)


@checked_loader
def borrowing():
    directory = Path(settings.DATA_DIRECTORY)
    paths = [directory / name for name in ("books.csv", "borrow_records.csv", "quality_report.json")]
    before = signature(paths)
    result = _borrowing(before)
    if signature(paths) != before:
        _borrowing.cache_clear()
        raise ValueError("数据加载期间发生变更，请发布完整批次后重试。")
    return result


@lru_cache(maxsize=2)
def _catalog(captured):
    return Catalog(captured[0][0])


@checked_loader
def catalog():
    return _catalog(signature([Path(settings.CATALOG_DATABASE)]))


@lru_cache(maxsize=2)
def _knowledge(captured):
    return KnowledgeBase(captured[0][0])


@checked_loader
def knowledge():
    return _knowledge(signature([Path(settings.KNOWLEDGE_SOURCE)]))


@lru_cache(maxsize=2)
def _provider(mode):
    return DemoProvider() if mode == "demo" else DisabledProvider()


def provider():
    return _provider(settings.OPAC_PROVIDER)


@checked_loader
def usage():
    path = Path(settings.USAGE_REPORT)
    if not path.exists():
        return {"dataset_label": "unknown", "datasets": {}, "is_live": False,
                "limitations": ["资源使用统计尚未导入。"]}
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("dataset_label") not in {"real", "simulated", "unknown"} or not isinstance(report.get("datasets"), dict):
        raise ValueError("资源统计格式无效。")
    return report

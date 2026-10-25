"""馆方业务适配契约；demo 只操作虚构数据，未实现真实 OPAC 请求。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Protocol
from data.isbn import canonical_isbn


class LibraryProvider(Protocol):
    def current_borrows(self, reader_id: str) -> list[dict]: ...
    def renew(self, reader_id: str, book_id: str) -> dict: ...
    def reserve(self, reader_id: str, isbn: str) -> dict: ...
    def holdings(self, book_key: str) -> dict: ...


class ProviderUnavailable(RuntimeError):
    pass


class DisabledProvider:
    def current_borrows(self, reader_id):
        raise ProviderUnavailable("尚未接入馆方当前借阅接口；历史借阅数据不能当作当前在借记录。")

    def renew(self, reader_id, book_id):
        return {"success": False, "code": 4002, "message": "尚未接入馆方续借接口，请在官方系统办理。"}

    def reserve(self, reader_id, isbn):
        return {"success": False, "code": 4002, "message": "尚未接入馆方预约接口，请在官方系统核对服务权限。"}

    def holdings(self, book_key):
        raise ProviderUnavailable("尚未接入馆方实时馆藏接口。")


class DemoProvider:
    """演示流程固定为虚构记录；3 次/30 天只演示普通图书，不推断真实业务资格。"""
    def __init__(self):
        self._records = {}
        self._lock = Lock()

    def current_borrows(self, reader_id):
        with self._lock:
            today = datetime.now(timezone(timedelta(hours=8))).date()
            records = self._records.setdefault(reader_id, [{"book_id": "DEMO-COPY-001", "title": "虚构图书：海风与星光",
                        "borrow_date": (today - timedelta(days=10)).isoformat(),
                        "due_date": (today + timedelta(days=50)).isoformat(), "renew_count": 0,
                        "is_overdue": False, "dataset_label": "simulated", "is_live": False}])
            return [{**record, "can_renew": record["renew_count"] < 3} for record in records]

    def renew(self, reader_id, book_id):
        self.current_borrows(reader_id)
        with self._lock:
            record = next((row for row in self._records[reader_id] if row["book_id"] == book_id), None)
            if not record:
                return {"success": False, "code": 4001, "message": "模拟借阅中未找到该财产号。"}
            if record["renew_count"] >= 3:
                return {"success": False, "code": 4001, "message": "模拟普通图书已达到 3 次续借上限。"}
            record["due_date"] = (date.fromisoformat(record["due_date"]) + timedelta(days=30)).isoformat()
            record["renew_count"] += 1
            return {"success": True, "new_due_date": record["due_date"], "renew_count": record["renew_count"],
                    "can_renew": record["renew_count"] < 3,
                    "dataset_label": "simulated", "is_live": False, "message": "模拟续借完成，未向馆方提交任何操作。"}

    def reserve(self, reader_id, isbn):
        if not canonical_isbn(isbn):
            return {"success": False, "code": 4001, "message": "模拟预约需要合法 ISBN；没有 ISBN 的书目请去馆方系统查询。"}
        return {"success": True, "queue_position": 1, "notify_channel": "模拟通知",
                "dataset_label": "simulated", "is_live": False, "message": "模拟预约完成，未产生真实排队或借阅。"}

    def holdings(self, book_key):
        return {"book_key": book_key, "location": "虚构示范书库 A 架", "available": 2,
                "status": "模拟在馆", "dataset_label": "simulated", "is_live": False}

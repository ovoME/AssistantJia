"""可追溯的模拟库存与当前借阅，全部来自已提交联调夹具，不拼接真实数据。"""
import json
from datetime import date, timedelta
from threading import Lock
from data.datasets import read_csv
from data.isbn import canonical_isbn


class IntegrationProvider:
    def __init__(self, directory):
        self.manifest = json.loads((directory/"manifest.json").read_text(encoding="utf-8"))
        self._records = json.loads((directory/"current_borrows.json").read_text(encoding="utf-8"))
        self._books = {row["book_key"]: row for row in read_csv(directory/"books.csv")}
        self._copies = read_csv(directory/"copies.csv")
        self._readers = {row["reader_id"] for row in read_csv(directory/"readers.csv")}
        self._holdings = {row["book_key"]: row for row in read_csv(directory/"holdings.csv")}
        self._queues = {}
        self._lock = Lock()

    def metadata(self):
        return {"dataset_label":"simulated", "is_live":False, "as_of":self.manifest["as_of"], "source":"synthetic_integration_v1"}

    def current_borrows(self, reader_id):
        if reader_id not in self._readers:
            raise ValueError("未找到该模拟读者。")
        with self._lock:
            return [{**row, "can_renew": row["renew_count"] < 3 and not row["is_overdue"]}
                    for row in self._records.get(reader_id, [])]

    def holdings(self, book_key):
        matches = [row for row in self._copies if row["book_id"] == book_key or row["catalog_id"] == book_key]
        if matches:
            book_key = matches[0]["book_key"]
        row = self._holdings.get(book_key)
        if row is None:
            raise ValueError("未找到该模拟馆藏编号。")
        return {"book_key":book_key, "location":row["location"], "available":int(row["available"]),
                "status":row["status"], "updated_at":row["checked_at"], "reservation_supported":True,
                "copies":[dict(copy) for copy in self._copies if copy["book_key"] == book_key], **self.metadata()}

    def renew(self, reader_id, book_id):
        if reader_id not in self._readers:
            return {"success":False,"code":4001,"message":"未找到该模拟读者。"}
        with self._lock:
            row = next((row for row in self._records.get(reader_id, []) if row["book_id"] == book_id), None)
            if row is None or row["is_overdue"] or row["renew_count"] >= 3:
                return {"success":False,"code":4001,"message":"模拟记录不存在、逾期或已达续借上限。"}
            row["due_date"] = (date.fromisoformat(row["due_date"])+timedelta(days=30)).isoformat()
            row["renew_count"] += 1
            return {"success":True,"new_due_date":row["due_date"],"renew_count":row["renew_count"],
                    "can_renew":row["renew_count"] < 3,"message":"模拟续借完成，未向馆方提交任何操作。",**self.metadata()}

    def reserve(self, reader_id, isbn):
        isbn = canonical_isbn(isbn)
        if reader_id not in self._readers or not isbn or "isbn:"+isbn not in self._books:
            return {"success":False,"code":4001,"message":"模拟读者或 ISBN 不在联调夹具中。"}
        with self._lock:
            queue = self._queues.setdefault(isbn, [])
            if reader_id not in queue:
                queue.append(reader_id)
            return {"success":True,"queue_position":queue.index(reader_id)+1,"notify_channel":"模拟通知",
                    "message":"模拟预约完成，未产生真实借阅业务。",**self.metadata()}

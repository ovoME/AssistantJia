"""C3 本地只读书目检索。历史样本与外部快照均不作为实时 OPAC 状态。"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from data.isbn import canonical_isbn


BASE_FIELDS = ("book_key", "title", "author", "isbn", "call_number", "publisher",
               "category_code", "category_name")
BOOK_FIELDS = BASE_FIELDS + ("publication_year", "language", "document_type")
LIBRARY_FIELDS = ("ID", "TITLE", "AUTHOR", "PUBLISHER", "YEAR", "CALLNO", "LANGUAGE", "DOCTYPE")
SNAPSHOT_FIELDS = ("book_key", "location", "available", "status", "checked_at", "source")
SEARCH_FIELDS = ("title_search", "author_search", "call_search", "publisher_search")
SCHEMA_VERSION = 1


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _normalized(value: str) -> str:
    return _text(value).casefold()


def _isbn(value: str) -> str:
    value = re.sub(r"^ISBN(?:-1[03])?\s*[:：]?\s*", "", _text(value), flags=re.I)
    return canonical_isbn(re.sub(r"[\s\-‐‑–—]", "", value).upper())


def _rows(path: Path, fields: tuple[str, ...], required: tuple[str, ...] | None = None):
    """流式读取，保留文本 ID；忽略不在字段约定中的额外列。"""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not set(required if required is not None else fields).issubset(headers):
            raise ValueError(f"{path.name} 表头缺失或重复。")
        for line, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name} 第 {line} 行列数不一致。")
            yield line, {field: _text(row.get(field, "")) for field in fields}


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("limit 必须是 1 到 100 的整数。")
    return value


def _query(value: str) -> str:
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError("query 必须是最多 200 字符的文本。")
    value = _normalized(value)
    if len(value.split()) > 10:
        raise ValueError("query 最多包含 10 个空白分隔的关键词。")
    return value


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _snapshots(path: Path | None):
    if path is None:
        return
    for _, row in _rows(path, SNAPSHOT_FIELDS):
        key = row.pop("book_key")
        if not key:
            raise ValueError("馆藏快照 book_key 不能为空。")
        if not row["source"] or not row["checked_at"]:
            raise ValueError("馆藏快照必须提供 source 和含时区的 checked_at。")
        try:
            checked = datetime.fromisoformat(row["checked_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("checked_at 必须是含时区的 ISO 8601 时间。") from exc
        if checked.tzinfo is None or checked > datetime.now(timezone.utc):
            raise ValueError("checked_at 不能缺少时区或晚于当前时间。")
        if row["available"] and not re.fullmatch(r"[0-9]+", row["available"]):
            raise ValueError("快照 available 必须为空或非负整数。")
        row["available"] = int(row["available"]) if row["available"] else None
        row["location"] = row["location"] or None
        row["status"] = row["status"] or "unknown"
        row["checked_at"] = checked.astimezone(timezone.utc).isoformat()
        yield key, row


def build_catalog(data_dir: str | Path, database: str | Path,
                  holdings: str | Path | None = None) -> dict:
    """从 C1 books.csv 构建 SQLite；不读取读者流水。"""
    data_dir = Path(data_dir)
    quality_path = data_dir / "quality_report.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
    if not isinstance(quality, dict):
        raise ValueError("quality_report.json 必须是 JSON 对象。")
    label = quality.get("dataset_label", "unknown")
    if not isinstance(label, str) or label not in {"simulated", "real", "unknown"}:
        raise ValueError("dataset_label 必须为 simulated、real 或 unknown。")
    books = (dict(book, publication_year="", language="", document_type="")
             for _, book in _rows(data_dir / "books.csv", BASE_FIELDS))
    return _build(data_dir / "books.csv", database, books, label, "historical_borrow_sample",
                  holdings, expected_count=quality.get("books_by_key"))


def build_library_catalog(source: str | Path, database: str | Path,
                          holdings: str | Path | None = None, dataset_label: str = "unknown") -> dict:
    """从馆藏书目 CSV 导出构建目录，ID 仅作为 catalog: 命名空间中的书目 ID。"""
    source = Path(source)
    def books():
        roots = frozenset("ABCDEFGHIJKNOPQRSTUVXZ")
        for line, raw in _rows(source, LIBRARY_FIELDS, required=("ID", "TITLE")):
            call_number = re.sub(r"\s+", "", raw["CALLNO"]).upper()
            match = re.match(r"([A-Z])(?=[\dA-Z.(]|$)", call_number)
            category = match[1] if match and match[1] in roots else "UNKNOWN"
            yield {
                "book_key": "catalog:" + raw["ID"] if raw["ID"] else "",
                "title": raw["TITLE"], "author": raw["AUTHOR"], "isbn": "",
                "call_number": call_number, "publisher": raw["PUBLISHER"],
                "category_code": category, "category_name": "",
                "publication_year": raw["YEAR"], "language": raw["LANGUAGE"], "document_type": raw["DOCTYPE"],
                "source_row": line,
            }
    return _build(source, database, books(), dataset_label, "catalog_export", holdings)


def _build(source: Path, database: str | Path, books, label: str, scope: str,
           holdings: str | Path | None, expected_count=None) -> dict:
    database = Path(database).resolve()
    if database.suffix.lower() not in {".db", ".sqlite3"}:
        raise ValueError("数据库输出必须使用 .db 或 .sqlite3 后缀。")
    if database == source.resolve() or (holdings is not None and database == Path(holdings).resolve()):
        raise ValueError("输出数据库不能覆盖输入文件。")
    if not isinstance(label, str) or label not in {"simulated", "real", "unknown"}:
        raise ValueError("dataset_label 必须为 simulated、real 或 unknown。")
    source_stat = source.stat()
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    metadata = {
        "schema_version": SCHEMA_VERSION, "dataset_label": label,
        "scope": scope, "source_file": source.name, "source_sha256": digest,
        "input_rows": 0, "book_count": 0, "rejected_rows": 0, "rejected_sample": [], "snapshot_count": 0,
        "built_at": datetime.now(timezone.utc).isoformat(), "is_live": False,
    }
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=database.stem + ".", suffix=".tmp", dir=database.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
        with closing(sqlite3.connect(temporary)) as connection:
            connection.executescript("""
                PRAGMA user_version = 1;
                CREATE TABLE metadata (id INTEGER PRIMARY KEY CHECK(id = 1), payload TEXT NOT NULL);
                CREATE TABLE books (
                    book_key TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
                    isbn TEXT NOT NULL, call_number TEXT NOT NULL, publisher TEXT NOT NULL,
                    category_code TEXT NOT NULL, category_name TEXT NOT NULL,
                    publication_year TEXT NOT NULL, language TEXT NOT NULL, document_type TEXT NOT NULL,
                    title_search TEXT NOT NULL, author_search TEXT NOT NULL,
                    call_search TEXT NOT NULL, publisher_search TEXT NOT NULL, snapshot TEXT
                );
                CREATE INDEX books_isbn ON books(isbn);
                CREATE INDEX books_title ON books(title_search);
                CREATE INDEX books_call_number ON books(call_search);
            """)
            for book in books:
                metadata["input_rows"] += 1
                if not book["book_key"] or not book["title"]:
                    if scope != "catalog_export":
                        raise ValueError("books.csv 的 book_key 和题名不能为空。")
                    metadata["rejected_rows"] += 1
                    if len(metadata["rejected_sample"]) < 20:
                        metadata["rejected_sample"].append({
                            "source_row": book["source_row"],
                            "reason": "id_missing" if not book["book_key"] else "title_missing",
                        })
                    continue
                if book["isbn"]:
                    normalized = _isbn(book["isbn"])
                    if not normalized:
                        raise ValueError("books.csv 含无效 ISBN，请先运行 C1 清洗。")
                    book["isbn"] = normalized
                values = tuple(book[field] for field in BOOK_FIELDS) + (
                    _normalized(book["title"]), _normalized(book["author"]),
                    re.sub(r"\s+", "", _normalized(book["call_number"])),
                    _normalized(book["publisher"]),
                    None,
                )
                try:
                    connection.execute("INSERT INTO books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
                except sqlite3.IntegrityError as exc:
                    raise ValueError("图书 book_key/ID 重复，请确认源数据。") from exc
                metadata["book_count"] += 1
            if expected_count is not None and expected_count != metadata["book_count"]:
                raise ValueError("质量报告与 books.csv 图书数不一致，请一起重跑 C1。")
            for key, snapshot in _snapshots(Path(holdings) if holdings is not None else None):
                updated = connection.execute(
                    "UPDATE books SET snapshot = ? WHERE book_key = ? AND snapshot IS NULL",
                    (json.dumps(snapshot, ensure_ascii=False), key),
                )
                if updated.rowcount != 1:
                    raise ValueError("馆藏快照 book_key 必须唯一且存在于书目中。")
                metadata["snapshot_count"] += 1
            final_stat = source.stat()
            if (source_stat.st_size, source_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
                raise ValueError("建库期间源文件发生变化，请待导出完成后重试。")
            connection.execute("INSERT INTO metadata VALUES (1, ?)", (json.dumps(metadata, ensure_ascii=False),))
            connection.commit()
        os.replace(temporary, database)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return metadata


class Catalog:
    """每次查询打开只读连接；不会在查询时创建缺失数据库或回退 mock 书目。"""

    def __init__(self, database: str | Path):
        self.database = Path(database).resolve()
        self.database.stat()
        self.info()

    def _connect(self):
        return closing(sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True))

    @staticmethod
    def _metadata(connection) -> dict:
        if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            raise ValueError("书目数据库版本不支持，请重新构建。")
        row = connection.execute("SELECT payload FROM metadata WHERE id = 1").fetchone()
        if row is None:
            raise ValueError("书目数据库缺少来源元数据，请重新构建。")
        metadata = json.loads(row[0])
        if not isinstance(metadata, dict) or metadata.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("书目数据库元数据无效，请重新构建。")
        if metadata.get("dataset_label") not in ("real", "simulated", "unknown") or metadata.get("scope") not in (
            "catalog_export", "historical_borrow_sample"
        ):
            raise ValueError("书目数据库来源元数据无效，请重新构建。")
        return metadata

    def info(self) -> dict:
        with self._connect() as connection:
            return self._metadata(connection)

    @staticmethod
    def _item(row) -> dict:
        snapshot = json.loads(row[-1]) if row[-1] is not None else None
        return {
            **dict(zip(BOOK_FIELDS, row[:len(BOOK_FIELDS)])),
            "location": snapshot["location"] if snapshot else None,
            "available": None, "status": "unknown", "is_live": False,
            "holdings_snapshot": snapshot,
        }

    @staticmethod
    def _search(connection, query: str, limit: int) -> list[dict]:
        if not query:
            return []
        isbn = _isbn(query)
        if isbn:
            rows = connection.execute("SELECT * FROM books WHERE isbn = ? ORDER BY book_key LIMIT ?", (isbn, limit))
        else:
            terms = query.split()
            conditions = []
            parameters = []
            for term in terms:
                conditions.append("(" + " OR ".join(f"{field} LIKE ? ESCAPE '\\'" for field in SEARCH_FIELDS) + ")")
                parameters.extend([_like(term)] * len(SEARCH_FIELDS))
            sql = "SELECT * FROM books WHERE " + " AND ".join(conditions) + """
                ORDER BY CASE WHEN title_search = ? THEN 0 WHEN call_search = ? THEN 1
                              WHEN author_search = ? THEN 2 ELSE 3 END, book_key LIMIT ?
            """
            rows = connection.execute(sql, parameters + [query, re.sub(r"\s+", "", query), query, limit])
        return [Catalog._item(row) for row in rows]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query, limit = _query(query), _limit(limit)
        with self._connect() as connection:
            self._metadata(connection)
            return self._search(connection, query, limit)

    def get_book(self, book_key: str) -> dict | None:
        if not isinstance(book_key, str) or not book_key:
            raise ValueError("book_key 必须是非空文本。")
        with self._connect() as connection:
            self._metadata(connection)
            row = connection.execute("SELECT * FROM books WHERE book_key = ?", (book_key,)).fetchone()
            return self._item(row) if row is not None else None

    def lookup_isbn(self, value: str, limit: int = 5) -> list[dict]:
        value, limit = _query(value), _limit(limit)
        canonical = _isbn(value)
        if not canonical:
            return []
        return self.search(canonical, limit)

    def response(self, query: str, limit: int = 5) -> dict:
        query, limit = _query(query), _limit(limit)
        with self._connect() as connection:
            metadata = self._metadata(connection)
            return {
                "code": 0, "message": "success", "data": self._search(connection, query, limit),
                "dataset_label": metadata["dataset_label"], "scope": metadata["scope"],
                "built_at": metadata["built_at"], "is_live": False,
                "limitations": [
                    "本地目录覆盖导入书目，并非全馆 OPAC 实时查询。",
                    "available 为 null；馆藏快照如有提供，其数量和状态仅表示 checked_at 时刻。",
                    "架位仅来自显式导入的快照；未导入时为 null，不能从索书号推断。",
                ],
            }

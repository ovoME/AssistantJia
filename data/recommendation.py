"""C2 历史借阅推荐。仅依赖标准库，不推断实时馆藏、架位或可借状态。"""

from __future__ import annotations

import csv
import heapq
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from data.content import ContentIndex


STRATEGIES = ("hybrid", "popular", "category", "collaborative")
CATEGORY_ROOTS = frozenset("ABCDEFGHIJKNOPQRSTUVXZ")
BOOK_FIELDS = {
    "book_key", "title", "author", "isbn", "call_number", "publisher",
    "category_code", "category_name", "borrow_count",
}
LOAN_FIELDS = {"reader_id", "book_key"}

# 只剥离常见提问套话；剩余词必须匹配书目信息或明确的中图分类。
_QUESTION_WORDS = re.compile(
    r"小嘉|能不能|可不可以|有没有|有哪些|有什么|有啥|给我|帮我|为我|麻烦|请问|请|我想看|我想读|想看|想读|我想|想要|我喜欢|喜欢|"
    r"推荐点|来点|一点|推荐|介绍|最近|大家|都在|看什么|什么|热门|榜单|好看的|好看|好书|"
    r"书籍|书本|几本|一本|这本|那本|一些|一批|换一批|再来|关于|有关|相关|方面|"
    r"按我的兴趣|我的兴趣|适合我|适合|看看|吗|呢|吧|一下"
)
_TOPIC_CATEGORIES = {"计算机": ("call", "TP3"), "编程": ("call", "TP31"),
                     "文学": ("category", "I"), "经济": ("category", "F"),
                     "历史": ("category", "K")}


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def recommendation_topic(query: str | None) -> str:
    """从常见自然语言问法提取检索词，无法匹配时不伪造其他主题的推荐。"""
    if query is None:
        return ""
    if not isinstance(query, str) or len(query) > 2000:
        raise ValueError("推荐问题必须为不超过 2000 字的文本。")
    quoted = re.search(r"《([^》]+)》", query)
    if quoted:
        return _text(quoted.group(1)).casefold()
    topic = re.sub(r"图书馆(?=(?:里|内|的)?(?:有|推荐|热门))", "", _text(query).casefold())
    topic = re.sub(r"^你(?:能|可以)?", "", topic)
    topic = re.sub(r"(?:\d{1,3}|[一二两三四五六七八九十百]+)\s*(?:本|册|部)", "", topic)
    topic = _QUESTION_WORDS.sub("", topic)
    topic = re.sub(r"[^\w\u4e00-\u9fff+#.\-]+", "", topic)
    while True:
        reduced = re.sub(r"^的|(?:的?(?:类书|类型|类|图书|书)|的)$", "", topic)
        if reduced == topic:
            break
        topic = reduced
    return topic


def _limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 100:
        raise ValueError("limit 必须是 1 到 100 的整数。")
    return value


def _category(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("category 必须为中图分类字母，如 I、T、TP 或 UNKNOWN。")
    value = _text(value).upper()
    if value == "UNKNOWN":
        return value
    if not re.fullmatch(r"[A-Z]{1,2}", value) or value[0] not in CATEGORY_ROOTS:
        raise ValueError("category 必须为中图分类字母，如 I、T、TP 或 UNKNOWN。")
    return value


def _read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not required.issubset(fields):
            raise ValueError(f"{path.name} 表头无效；请使用 C1 清洗输出。")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"{path.name} 存在列数不一致的行。")
    return rows


class Recommender:
    """从完整 books/borrow_records 建索引，复用实例即可重复查询。

    协同过滤使用二元读者-书种集合与余弦相似度，最多取 30 位邻居。
    热门度保留 C1 流水计数；偏好与相似度不受同一读者重复借同书影响。
    """

    # 600 人独立验证集在预设五个权重中选出；测试集不参与调参。
    CONTENT_WEIGHT = 0.75

    def __init__(
        self,
        books: Iterable[Mapping[str, str]],
        loans: Iterable[Mapping[str, str]],
        dataset_label: str = "unknown",
    ):
        if not isinstance(dataset_label, str) or dataset_label not in {"simulated", "real", "unknown"}:
            raise ValueError("dataset_label 只能为 simulated、real 或 unknown。")
        self.dataset_label = dataset_label
        catalog: dict[str, dict[str, str]] = {}
        expected_counts = {}
        for book in books:
            if not BOOK_FIELDS.issubset(book) or any(not isinstance(book[c], str) for c in BOOK_FIELDS):
                raise ValueError("图书记录缺少 C1 字段或字段不是文本。")
            book = {c: _text(book[c]) for c in BOOK_FIELDS}
            key = book["book_key"]
            if not key or not book["title"] or key in catalog:
                raise ValueError("图书 book_key 必须唯一且非空，题名不能为空。")
            if not re.fullmatch(r"[0-9]+", book["borrow_count"]):
                raise ValueError("图书 borrow_count 必须是非负整数。")
            catalog[key] = book
            expected_counts[key] = int(book["borrow_count"])

        # ISBN 缺失且不同副本可精确对应同一完整元数据时，合并为一个候选。
        # 多个合法 ISBN 共用元数据的歧义组不合并；残缺元数据也不跨副本猜测。
        entities = {key: key for key in catalog}
        metadata_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for key, book in catalog.items():
            metadata = tuple(book[c].casefold() for c in ("title", "author", "publisher"))
            if all(metadata):
                metadata_groups[metadata].append(key)
        for keys in metadata_groups.values():
            isbn_keys = {key for key in keys if key.startswith("isbn:")}
            if len(isbn_keys) <= 1:
                representative = min(isbn_keys or keys)
                for key in keys:
                    entities[key] = representative

        self._books = {}
        self._histories: dict[str, set[str]] = defaultdict(set)
        self._book_readers: dict[str, set[str]] = defaultdict(set)
        self._counts: Counter[str] = Counter()
        actual_counts: Counter[str] = Counter()
        for loan in loans:
            if not LOAN_FIELDS.issubset(loan) or any(not isinstance(loan[c], str) for c in LOAN_FIELDS):
                raise ValueError("借阅记录缺少 reader_id/book_key 文本字段。")
            reader, key = (_text(loan[c]) for c in ("reader_id", "book_key"))
            if not reader or key not in catalog:
                raise ValueError("借阅记录含空读者或图书不在 books.csv；请一起重跑 C1 清洗。")
            entity = entities[key]
            self._histories[reader].add(entity)
            self._book_readers[entity].add(reader)
            self._counts[entity] += 1
            actual_counts[key] += 1
        if any(actual_counts[key] != expected for key, expected in expected_counts.items()):
            raise ValueError("books.csv 与 borrow_records.csv 次数不一致；请一起重跑 C1 清洗。")
        for entity in sorted(set(entities.values())):
            # ISBN 代表项优先；否则使用最稳定的原始 book_key。
            self._books[entity] = catalog[entity].copy()
        self._content = ContentIndex(self._books)

    @classmethod
    def from_directory(cls, directory: str | Path) -> Recommender:
        """只读取本地 C1 输出；缺少质量报告时数据标识为 unknown。"""
        directory = Path(directory)
        books = _read_csv(directory / "books.csv", BOOK_FIELDS)
        loans = _read_csv(directory / "borrow_records.csv", LOAN_FIELDS)
        quality_path = directory / "quality_report.json"
        quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.exists() else {}
        if not isinstance(quality, dict):
            raise ValueError("quality_report.json 必须是 JSON 对象。")
        if "accepted_rows" in quality and quality["accepted_rows"] != len(loans):
            raise ValueError("quality_report.json 与借阅流水行数不一致；请重跑 C1 清洗。")
        return cls(books, loans, quality.get("dataset_label", "unknown"))

    def _candidates(self, category: str | None, history: set[str]) -> list[str]:
        def matches(book):
            if category is None:
                return True
            if len(category) == 1 or category == "UNKNOWN":
                return book["category_code"] == category
            return book["category_code"] == category[0] and book["call_number"].startswith(category)

        return [key for key, book in self._books.items() if key not in history and matches(book)]

    def _item(self, key: str) -> dict:
        book = self._books[key]
        return {
            "book_key": key, "title": book["title"], "author": book["author"],
            "isbn": book["isbn"], "call_number": book["call_number"],
            "publisher": book["publisher"], "category": book["category_code"],
            "category_name": book["category_name"], "count": self._counts[key],
        }

    def hot_books(self, category: str | None = None, limit: int = 10) -> list[dict]:
        """历史借阅热门榜；先过滤分类再截取，读取完整书目而非 TOP100。"""
        limit, category = _limit(limit), _category(category)
        candidates = self._candidates(category, set())
        candidates.sort(key=lambda key: (-self._counts[key], key))
        return [self._item(key) for key in candidates[:limit]]

    def _collaborative_scores(self, reader: str, history: set[str]) -> dict[str, float]:
        overlaps = Counter(peer for key in history for peer in self._book_readers[key] if peer != reader)
        neighbors = [(peer, overlap / math.sqrt(len(history) * len(self._histories[peer])))
                     for peer, overlap in overlaps.items()]
        neighbors.sort(key=lambda pair: (-pair[1], pair[0]))
        neighbors = neighbors[:30]
        denominator = sum(similarity for _, similarity in neighbors)
        scores: Counter[str] = Counter()
        if denominator:
            for peer, similarity in neighbors:
                for key in sorted(self._histories[peer] - history):
                    scores[key] += similarity / denominator
        return scores

    def recommend(
        self,
        reader_id: str | None = None,
        limit: int = 5,
        category: str | None = None,
        strategy: str = "hybrid",
    ) -> list[dict]:
        """生成已读过滤后的推荐；不足 limit 时只返回剩余候选，不补回已读书。"""
        limit, category = _limit(limit), _category(category)
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy 必须是 {', '.join(STRATEGIES)} 之一。")
        if reader_id is not None and not isinstance(reader_id, str):
            raise ValueError("reader_id 必须为文本，以保留前导零。")
        reader = _text(reader_id or "")
        history = self._histories.get(reader, set())
        candidates = self._candidates(category, history)
        if not candidates:
            return []
        collaborative = self._collaborative_scores(reader, history) if history and strategy in {
            "hybrid", "collaborative"
        } else {}
        preferences = Counter(self._books[key]["category_code"] for key in sorted(history)
                              if self._books[key]["category_code"] != "UNKNOWN") if strategy in {
            "hybrid", "category"
        } else Counter()
        total_preferences = sum(preferences.values())
        max_count = max(self._counts[key] for key in candidates) or 1
        has_collaborative = any(collaborative.get(key, 0) for key in candidates)
        has_preferences = any(preferences[self._books[key]["category_code"]] for key in candidates)
        content = self._content.scores(history) if history and strategy == "hybrid" and self.CONTENT_WEIGHT else {}
        max_content = max((content.get(key, 0) for key in candidates), default=0)
        ranked = []
        for key in candidates:
            book = self._books[key]
            popularity = self._counts[key] / max_count
            cf_score = collaborative.get(key, 0)
            preference = preferences[book["category_code"]] / total_preferences if total_preferences else 0
            if has_collaborative and has_preferences:
                score = 0.6 * cf_score + 0.3 * preference + 0.1 * popularity
            elif has_collaborative:
                score = 0.9 * cf_score + 0.1 * popularity
            elif has_preferences:
                score = 0.8 * preference + 0.2 * popularity
            else:
                score = popularity
            if cf_score:
                reason, method = "根据相似借阅兴趣推荐", "collaborative"
            elif preference:
                reason, method = f"根据你借过的{book['category_name']}类图书推荐", "category"
            else:
                reason, method = "根据历史借阅次数推荐", "popular"
            ranked.append((score, key, reason, method))
        if max_content:
            max_base = max(row[0] for row in ranked) or 1
            combined = []
            for score, key, reason, method in ranked:
                content_part = self.CONTENT_WEIGHT * content.get(key, 0) / max_content
                base_part = (1 - self.CONTENT_WEIGHT) * score / max_base
                if content_part > base_part:
                    reason, method = "根据你借过图书的题名、作者或细分分类相似度推荐", "content"
                combined.append((content_part + base_part, key, reason, method))
            ranked = combined
        ranked = heapq.nsmallest(limit, ranked, key=lambda row: (-row[0], -self._counts[row[1]], row[1]))
        return [{**self._item(key), "score": round(score, 8), "reason": reason, "strategy": method}
                for score, key, reason, method in ranked[:limit]]

    def discover(self, reader_id: str | None = None, limit: int = 5, query: str | None = None,
                 avoid: Iterable[str] = (), rng=None, category: str | None = None) -> list[dict]:
        """依据问题和可用的个人兴趣抽取多样候选；不使用借阅次数排序。"""
        limit, category = _limit(limit), _category(category)
        if reader_id is not None and not isinstance(reader_id, str):
            raise ValueError("reader_id 必须为文本，以保留前导零。")
        topic = recommendation_topic(query)
        history = self._histories.get(_text(reader_id or ""), set())
        candidates = self._candidates(category, history)
        if topic:
            spec = _TOPIC_CATEGORIES.get(topic)
            def matches(key):
                book = self._books[key]
                fields = (book["title"], book["author"], book["publisher"],
                          book["category_name"], book["call_number"])
                if any(topic in _text(field).casefold() for field in fields):
                    return True
                if spec and spec[0] == "category":
                    return book["category_code"] == spec[1]
                return bool(spec and spec[0] == "call" and book["call_number"].upper().startswith(spec[1]))
            candidates = [key for key in candidates if matches(key)]
        if not candidates:
            return []

        content = self._content.scores(history) if history else {}
        collaborative = self._collaborative_scores(_text(reader_id or ""), history) if history else {}
        preferences = Counter(self._books[key]["category_code"] for key in history
                              if self._books[key]["category_code"] != "UNKNOWN")
        total_preferences = sum(preferences.values())
        max_content = max((content.get(key, 0) for key in candidates), default=0)
        max_cf = max((collaborative.get(key, 0) for key in candidates), default=0)
        scored = []
        for key in candidates:
            content_score = content.get(key, 0) / max_content if max_content else 0
            cf_score = collaborative.get(key, 0) / max_cf if max_cf else 0
            preference = preferences[self._books[key]["category_code"]] / total_preferences if total_preferences else 0
            score = 0.65 * content_score + 0.25 * cf_score + 0.10 * preference
            if topic:
                reason, method = f"根据提问中的“{topic}”匹配书目", "topic"
            elif content_score:
                reason, method = "根据你借过图书的内容相似度推荐", "content"
            elif cf_score:
                reason, method = "根据相似借阅兴趣推荐", "collaborative"
            elif preference:
                reason, method = "根据你的借阅分类偏好推荐", "category"
            else:
                reason, method = "从历史借阅样本书目中探索推荐", "discovery"
            scored.append((key, score, reason, method))

        # 优先避开上一批，在新旧候选内优先选有兴趣证据的书。
        # 在组内按兴趣相关度加权抽样，匿名用户均匀抽样，不使用借阅量。
        rng = rng if rng is not None else random.Random()
        excluded = set(avoid)
        result = []
        relevant_rows = [row for row in scored if row[1] > 0]
        # 把抽样限制在较相关的候选池内，避免大量微弱匹配稀释个人兴趣。
        relevant_rows = heapq.nlargest(max(limit * 3, 15), relevant_rows,
                                        key=lambda row: (row[1], rng.random()))
        groups = ((True, relevant_rows), (False, [row for row in scored if row[1] <= 0]))
        for fresh in (True, False):
            for relevant, group in groups:
                pool = [row for row in group if (row[0] not in excluded) == fresh]
                needed = limit - len(result)
                if not needed:
                    break
                def draw_key(row):
                    weight = (0.05 + row[1]) ** 2 if relevant else 1.0
                    return math.log(max(rng.random(), 1e-300)) / weight
                result.extend(heapq.nlargest(needed, pool, key=draw_key))
            if len(result) == limit:
                break
        return [{**self._item(key), "score": round(score, 8), "reason": reason, "strategy": method}
                for key, score, reason, method in result]

    def response(self, reader_id: str | None = None, limit: int = 5,
                 category: str | None = None, strategy: str = "hybrid", query: str | None = None) -> dict:
        """现有 /api/recommend 响应字段；服务端须先确认目标读者身份。"""
        if strategy == "discovery":
            rows = self.discover(reader_id, limit, query, category=category)
        else:
            if query is not None:
                raise ValueError("query 仅支持 discovery 策略。")
            rows = self.recommend(reader_id, limit, category, strategy)
        return {
            "code": 0, "message": "success",
            "data": rows,
            "dataset_label": self.dataset_label,
            "limitations": [
                "推荐依据历史借阅样本，未验证实时可借状态或架位。",
                "没有借阅日期，未使用近期、时效或时间衰减特征。",
            ],
        }

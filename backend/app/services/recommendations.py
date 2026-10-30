"""推荐批次轮换：只在当前进程保存有限的上一批书目，不保存借阅记录。"""
from collections import OrderedDict
from contextlib import nullcontext
import random
from threading import Lock
import unicodedata

from data.recommendation import recommendation_topic, wants_popular


_RECENT = OrderedDict()
_LOCK = Lock()
_SCOPE_LOCKS = [Lock() for _ in range(64)]
_MAX_SCOPES = 500


def catalog_queries(query, search_terms=None):
    """保留主题和模型给出的相关短词；拆词时不把“考研”等用途当作专业。"""
    if not isinstance(query, str) or not query.strip():
        return []
    generic = {"考研", "研究生", "备考", "考试", "教材", "资料", "图书", "书籍", "真题", "辅导"}
    candidates = [query]
    if isinstance(search_terms, list):
        candidates.extend(search_terms[:4])
    candidates.extend(word for word in query.split() if word not in generic)
    result = []
    for value in candidates:
        if not isinstance(value, str):
            continue
        value = " ".join(value.split())
        if not value or len(value) > 100 or len(value.split()) > 10:
            continue
        if value in generic and query.strip() != value:
            continue
        if value.casefold() not in {item.casefold() for item in result}:
            result.append(value)
    return result[:6]


def discover(engine, reader_id=None, limit=5, query=None, session_id=None, popular=None):
    """基于当前会话和主题尽量换一批；无会话时独立抽样。"""
    popular_intent = wants_popular(query) if popular is None else popular
    scope = (session_id, id(engine), recommendation_topic(query), popular_intent) if session_id else None
    # 同一会话同一主题的并发请求串行轮换，不阻塞其他大多数会话。
    guard = _SCOPE_LOCKS[hash(scope) % len(_SCOPE_LOCKS)] if scope else nullcontext()
    with guard:
        with _LOCK:
            previous = _RECENT.get(scope, ()) if scope else ()
        rows = engine.discover(reader_id, limit, query, avoid=previous, popular=popular)
        if scope:
            with _LOCK:
                _RECENT[scope] = tuple(row["book_key"] for row in rows)
                _RECENT.move_to_end(scope)
                while len(_RECENT) > _MAX_SCOPES:
                    _RECENT.popitem(last=False)
        return rows


def catalog_candidates(catalog, queries, limit=5, session_id=None):
    """从书目快照抽取匹配候选；这是检索结果，不推断借阅热度或个人偏好。"""
    scope = (session_id, id(catalog), "catalog", tuple(queries)) if session_id else None
    guard = _SCOPE_LOCKS[hash(scope) % len(_SCOPE_LOCKS)] if scope else nullcontext()
    with guard:
        with _LOCK:
            previous = set(_RECENT.get(scope, ())) if scope else set()
        groups = []
        for query in queries:
            words = [unicodedata.normalize("NFKC", word).casefold() for word in query.split()]
            group = []
            for row in catalog.search(query, limit=min(100, max(40, limit * 10))):
                title = unicodedata.normalize("NFKC", row["title"]).casefold()
                author = unicodedata.normalize("NFKC", row["author"]).casefold()
                # 多词须同时出现在题名中，避免仅因出版社、作者介绍命中无关书。
                if not (all(word in title for word in words) if len(words) > 1
                        else words and (words[0] in title or words[0] in author)):
                    continue
                group.append({**row, "reason": f"书目匹配“{query}”；请核对用途及版本。",
                              "strategy": "catalog_match"})
            random.SystemRandom().shuffle(group)
            groups.append(group)

        selected, titles = [], set()
        # 每个检索词轮流提供候选；先避开上一批，不足时才允许重复。
        for allow_previous in (False, True):
            pending = [list(group) for group in groups]
            while any(pending) and len(selected) < limit:
                for group in pending:
                    while group:
                        row = group.pop()
                        title_key = unicodedata.normalize("NFKC", row["title"]).casefold().strip()
                        if title_key in titles or (not allow_previous and title_key in previous):
                            continue
                        titles.add(title_key)
                        selected.append(row)
                        break
                    if len(selected) >= limit:
                        break
        if scope:
            with _LOCK:
                _RECENT[scope] = tuple(unicodedata.normalize("NFKC", row["title"]).casefold().strip()
                                       for row in selected)
                _RECENT.move_to_end(scope)
                while len(_RECENT) > _MAX_SCOPES:
                    _RECENT.popitem(last=False)
        return selected

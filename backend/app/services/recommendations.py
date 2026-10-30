"""推荐批次轮换：只在当前进程保存有限的上一批书目，不保存借阅记录。"""
from collections import OrderedDict
from contextlib import nullcontext
from threading import Lock

from data.recommendation import recommendation_topic, wants_popular


_RECENT = OrderedDict()
_LOCK = Lock()
_SCOPE_LOCKS = [Lock() for _ in range(64)]
_MAX_SCOPES = 500


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

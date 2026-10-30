from app.agent.tools.search_books import search_books
from app.agent.tools.renew_book import renew_book
from app.agent.tools.reserve_book import reserve_book
from app.agent.tools.get_borrows import get_user_borrows
from app.agent.tools.recommend import recommend_books
from app.agent.tools.search_knowledge import search_knowledge

ALL_TOOLS = [
    search_books,
    renew_book,
    reserve_book,
    get_user_borrows,
    recommend_books,
    search_knowledge,
]

# 交给模型自主选择时只开放只读工具：续借、预约属于写操作，
# 在 OPAC 未接入真实业务系统的前提下不能由模型自行触发。
READ_TOOLS = [
    search_books,
    recommend_books,
    search_knowledge,
    get_user_borrows,
]

__all__ = [
    "ALL_TOOLS",
    "READ_TOOLS",
    "search_books",
    "renew_book",
    "reserve_book",
    "get_user_borrows",
    "recommend_books",
    "search_knowledge",
]

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

__all__ = [
    "ALL_TOOLS",
    "search_books",
    "renew_book",
    "reserve_book",
    "get_user_borrows",
    "recommend_books",
    "search_knowledge",
]

"""只读接口复用 C1-C4；当前业务只允许显式模拟 provider 或明确未接入。"""
from app.services import local_data
from app.services.recommendations import discover
from app.auth import ensure_reader


class DataClient:
    @staticmethod
    def search_books_opac(query, limit=5):
        return local_data.search_books_response(query, limit)["data"]

    @staticmethod
    def get_user_borrows(reader_id):
        ensure_reader(reader_id, allow_demo=True)
        return local_data.provider().current_borrows(reader_id)

    @staticmethod
    def renew_book(reader_id, book_id):
        ensure_reader(reader_id, allow_demo=True)
        return local_data.provider().renew(reader_id, book_id)

    @staticmethod
    def reserve_book(reader_id, isbn):
        ensure_reader(reader_id, allow_demo=True)
        return local_data.provider().reserve(reader_id, isbn)

    @staticmethod
    def get_recommendations(reader_id=None, limit=5, query=None, session_id=None):
        if reader_id:
            ensure_reader(reader_id)
        return discover(local_data.borrowing().engine, reader_id, limit, query, session_id)

    @staticmethod
    def get_hot_books(category=None, limit=10):
        return local_data.borrowing().engine.hot_books(category, limit)

    @staticmethod
    def search_rules_knowledge(question):
        return local_data.knowledge().answer(question)


data_client = DataClient()

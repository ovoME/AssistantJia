"""只读接口复用 C1-C4；当前业务只允许显式模拟 provider 或明确未接入。"""
from app.services import local_data
from app.services.recommendations import catalog_candidates, catalog_queries, discover
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
    def get_recommendations(reader_id=None, limit=5, query=None, session_id=None, popular=None):
        if reader_id:
            ensure_reader(reader_id)
        return discover(local_data.borrowing().engine, reader_id, limit, query, session_id, popular)

    @staticmethod
    def get_recommendation_bundle(reader_id=None, limit=5, query=None, session_id=None,
                                  popular=None, search_terms=None):
        """历史推荐和书目候选分开标注；书目候选不声称按个人历史过滤。"""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit 必须是 1 到 100 的整数。")
        if reader_id:
            ensure_reader(reader_id)
        queries = catalog_queries(query, search_terms)
        catalog = None
        catalog_attempted = False
        rows = []
        if queries and isinstance(search_terms, list) and search_terms and not reader_id and not popular:
            catalog = local_data.catalog()
            catalog_attempted = True
            rows = catalog_candidates(catalog, queries, limit, session_id)
        if not rows:
            service = local_data.borrowing()
            rows = discover(service.engine, reader_id, limit, query, session_id, popular)
            if rows or not queries or popular:
                return {"recommendations": rows, **service.metadata(), "search_terms": queries}
            if not catalog_attempted:
                catalog = local_data.catalog()
                rows = catalog_candidates(catalog, queries, limit, session_id)
        if rows:
            return {"recommendations": rows, "dataset_label": catalog.info()["dataset_label"],
                    "scope": "catalog_recommendation_candidates", "is_live": False, "search_terms": queries}
        return {"recommendations": [], **service.metadata(), "search_terms": queries}

    @staticmethod
    def get_hot_books(category=None, limit=10):
        return local_data.borrowing().engine.hot_books(category, limit)

    @staticmethod
    def search_rules_knowledge(question):
        return local_data.knowledge().answer(question)


data_client = DataClient()

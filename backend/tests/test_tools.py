import json
import pytest
from app.agent.tools.search_books import search_books
from app.agent.tools.renew_book import renew_book
from app.agent.tools.reserve_book import reserve_book
from app.agent.tools.get_borrows import get_user_borrows
from app.agent.tools.recommend import recommend_books
from app.agent.tools.search_knowledge import search_knowledge

def test_search_books():
    """测试查馆藏工具"""
    res_str = search_books.invoke({"query": "三体", "limit": 3})
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert len(data["books"]) > 0
    assert "索书号" not in data["books"][0]  # 英文键
    assert "call_number" in data["books"][0]
    assert "location" in data["books"][0]

def test_get_user_borrows():
    """测试查读者借阅"""
    res_str = get_user_borrows.invoke({"reader_id": "2023001"})
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert len(data["borrows"]) > 0

def test_renew_book_normal():
    """测试正常续借"""
    res_str = renew_book.invoke({"reader_id": "2023001", "book_id": "B20230911001"})
    data = json.loads(res_str)
    assert data["success"] is True
    assert "new_due_date" in data

def test_renew_book_limit():
    """测试超过续借次数上限"""
    # B20230911002 初始 renew_count=1
    res_str = renew_book.invoke({"reader_id": "2023001", "book_id": "B20230911002"})
    data = json.loads(res_str)
    assert data["success"] is False
    assert "最大续借上限" in data["message"]

def test_reserve_book():
    """测试在线预约"""
    res_str = reserve_book.invoke({"reader_id": "2023001", "isbn": "9787536692930"})
    data = json.loads(res_str)
    assert data["success"] is True
    assert data["queue_position"] >= 1

def test_recommend_books():
    """测试个性化推荐"""
    res_str = recommend_books.invoke({"reader_id": "2023001", "limit": 2})
    data = json.loads(res_str)
    assert data["status"] == "success"
    assert len(data["recommendations"]) == 2

def test_search_knowledge():
    """测试规则知识库"""
    res_str = search_knowledge.invoke({"question": "图书能借几天"})
    data = json.loads(res_str)
    assert data["found"] is True
    assert "30" in data["answer"]

import json
from app.agent.tools.search_books import search_books
from app.agent.tools.renew_book import renew_book
from app.agent.tools.reserve_book import reserve_book
from app.agent.tools.get_borrows import get_user_borrows
from app.agent.tools.recommend import recommend_books
from app.agent.tools.search_knowledge import search_knowledge


def test_search_books():
    data = json.loads(search_books.invoke({'query':'Python','limit':3}))
    assert data['status'] == 'success'
    assert len(data['books']) == 2
    assert data['books'][0]['available'] is None


def test_get_user_borrows():
    data = json.loads(get_user_borrows.invoke({'reader_id':'demo-reader'}))
    assert data['borrows'][0]['dataset_label'] == 'simulated'


def test_renew_book_normal():
    data = json.loads(renew_book.invoke({'reader_id':'demo-reader','book_id':'DEMO-COPY-001'}))
    assert data['success'] is True
    assert data['is_live'] is False
    assert '模拟' in data['message']


def test_renew_book_limit():
    for _ in range(3):
        assert json.loads(renew_book.invoke({'reader_id':'demo-reader','book_id':'DEMO-COPY-001'}))['success']
    data = json.loads(renew_book.invoke({'reader_id':'demo-reader','book_id':'DEMO-COPY-001'}))
    assert data['success'] is False


def test_reserve_book():
    data = json.loads(reserve_book.invoke({'reader_id':'demo-reader','isbn':'9780306406157'}))
    assert data['success'] is True
    assert data['dataset_label'] == 'simulated'


def test_recommend_books():
    data = json.loads(recommend_books.invoke({'limit':2}))
    assert data['status'] == 'success'
    assert len(data['recommendations']) == 2


def test_search_knowledge():
    data = json.loads(search_knowledge.invoke({'question':'图书能借几天'}))
    assert data['found'] is True
    assert '60' in data['answer']
    assert data['sources'][0]['url'] == 'https://library.xujc.com/jyqx/list.htm'


def test_tool_cannot_impersonate_reader():
    data = json.loads(recommend_books.invoke({'reader_id':'someone-else','limit':2}))
    assert data['status'] == 'error'
    assert 'recommendations' not in data

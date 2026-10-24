import time
from app.auth import sign_reader_token
from app.config import settings


def test_health(client):
    assert client.get('/health').json()['data']['status'] == 'healthy'


def test_api_books_search(client):
    response = client.get('/api/books/search', params={'query':'Python'})
    assert response.status_code == 200
    body = response.json()
    assert len(body['data']) == 2
    assert body['dataset_label'] == 'simulated'
    assert body['is_live'] is False
    assert all(row['available'] is None and row['location'] is None for row in body['data'])


def test_api_reader_borrows(client):
    body = client.get('/api/reader/demo-reader/borrows').json()
    assert body['dataset_label'] == 'simulated'
    assert body['data'][0]['book_id'] == 'DEMO-COPY-001'
    assert body['data'][0]['is_live'] is False


def test_api_admin_stats(client):
    assert client.get('/api/admin/stats/summary').status_code == 401
    response = client.get('/api/admin/stats/summary', headers={'X-Admin-Token':settings.ADMIN_TOKEN})
    assert response.status_code == 200
    data = response.json()['data']
    assert data['total_borrows'] == 8
    assert data['total_readers'] == 3
    assert data['total_titles'] == 6


def test_recommend_uses_verified_identity(client):
    assert client.get('/api/recommend?reader_id=demo-reader').status_code == 401
    token = sign_reader_token('demo-reader', settings.READER_TOKEN_SECRET, time.time()+3600)
    response = client.get('/api/recommend', headers={'Authorization':'Bearer '+token})
    assert response.status_code == 200
    from data.scripts.generate_demo import demo_isbn
    keys = {row['book_key'] for row in response.json()['data']}
    assert not keys & {'isbn:'+demo_isbn(1), 'isbn:'+demo_isbn(3)}
    assert client.get('/api/recommend?reader_id=someone-else', headers={'Authorization':'Bearer '+token}).status_code == 403


def test_api_book_review(client):
    headers = {'X-Admin-Token': settings.ADMIN_TOKEN}
    # 测试空书名报错
    res_empty = client.post('/api/admin/book-review', json={'title': ''}, headers=headers)
    assert res_empty.status_code == 200
    assert res_empty.json()['code'] == 4000

    # 测试正常生成导读
    res = client.post('/api/admin/book-review', json={'title': '三体', 'author': '刘慈欣'}, headers=headers)
    assert res.status_code == 200
    data = res.json()['data']
    assert data['title'] == '三体'
    assert '三体' in data['review']
    assert len(data['review']) > 20

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "healthy"

def test_api_books_search():
    response = client.get("/api/books/search?query=三体")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert len(data["data"]) > 0
    assert data["data"][0]["title"] == "三体"

def test_api_reader_borrows():
    response = client.get("/api/reader/2023001/borrows")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert len(data["data"]) > 0

def test_api_admin_stats():
    response = client.get("/api/admin/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["total_borrows"] == 36908

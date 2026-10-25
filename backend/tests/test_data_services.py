import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.auth import sign_reader_token
from app.config import settings
from app.main import app
from app.services import local_data
from data.scripts.prepare_demo import prepare
from data.scripts.generate_demo import demo_isbn


def admin():
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.mark.parametrize("query", ["不存在的书xyz", "%' OR 1=1 --", "_"])
def test_no_matches_never_fall_back_to_sample_books(client, query):
    response = client.get("/api/books/search", params={"query": query})
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_exact_isbn_only(client):
    found = client.get("/api/books/" + demo_isbn(1)).json()
    assert found["data"]["title"] == "虚构图书:海风与星光"
    assert client.get("/api/books/not-an-isbn").json()["code"] == 4004


def test_missing_files_do_not_serve_stale_or_fake_results(client, monkeypatch, fixture_data):
    assert client.get("/api/recommend").status_code == 200
    monkeypatch.setattr(settings, "DATA_DIRECTORY", str(fixture_data / "missing"))
    response = client.get("/api/recommend")
    assert response.status_code == 503
    assert response.json()["data"] is None
    assert str(fixture_data) not in response.text
    monkeypatch.setattr(settings, "CATALOG_DATABASE", str(fixture_data / "missing.db"))
    assert client.get("/api/books/search?query=Python").status_code == 503


def test_data_mismatch_is_explicit_error(client, fixture_data):
    path = fixture_data / "quality_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["accepted_rows"] = 999
    path.write_text(json.dumps(report), encoding="utf-8")
    assert client.get("/api/recommend").status_code == 503


def test_missing_admin_configuration_fails_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_TOKEN", None)
    assert client.get("/api/admin/stats/summary").status_code == 503


@pytest.mark.parametrize("token", ["bad", "a.b", "Bearer wrong"])
def test_invalid_tokens_cannot_read_private_recommendations(client, token):
    assert client.get("/api/recommend", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_expired_or_wrong_key_credentials_rejected(client):
    for token in (sign_reader_token("demo-reader", settings.READER_TOKEN_SECRET, time.time()-1),
                  sign_reader_token("demo-reader", "different-secret-which-is-long-enough", time.time()+3600)):
        assert client.get("/api/recommend", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_categories_publishers_and_trend_are_data_driven(client):
    categories = client.get("/api/admin/stats/categories", headers=admin()).json()["data"]
    assert sum(row["count"] for row in categories) == 8
    assert sum(row["share"] for row in categories) == pytest.approx(1)
    publishers = client.get("/api/admin/stats/publishers", headers=admin()).json()["data"]
    assert publishers == [{"publisher": "虚构出版社", "count": 8}]
    trend = client.get("/api/admin/stats/trend", headers=admin()).json()
    assert trend["data"] == [] and "没有日期" in trend["message"]


def test_purchase_reference_never_claims_unknown_capacity(client):
    body = client.post("/api/admin/purchase-advice", headers=admin(), json={}).json()
    assert body["data"]["is_ai_generated"] is False
    assert "8 条" in body["data"]["report"]
    assert "缺少" in body["data"]["report"]


def test_rules_http_and_rag_have_sources_and_scope(client):
    body = client.get("/api/knowledge/search", params={"question": "本科生能借几天"}).json()
    assert body["data"]["found"] and body["data"]["sources"]
    assert "60 天" in body["data"]["answer"]
    from app.rag.retriever import retriever
    assert retriever.retrieve("普通图书续借")[0]["chunk_id"] == "borrowing/ordinary"
    unsupported = client.get("/api/knowledge/search", params={"question": "研讨室必须几个人签到"}).json()
    assert not unsupported["data"]["found"]


def test_disabled_provider_does_not_fake_success(client, monkeypatch):
    monkeypatch.setattr(settings, "OPAC_PROVIDER", "disabled")
    token = sign_reader_token("demo-reader", settings.READER_TOKEN_SECRET, time.time()+3600)
    headers = {"Authorization": "Bearer " + token}
    for route, body in (("/api/renew", {"reader_id": "me", "book_id": "any"}),
                        ("/api/reserve", {"reader_id": "me", "isbn": demo_isbn(1)})):
        result = client.post(route, json=body, headers=headers).json()
        assert result["code"] == 4002
        assert result["data"] is None
    assert client.get("/api/reader/me/borrows", headers=headers).status_code == 503
    assert client.get("/api/books/holdings/any").status_code == 503


def test_demo_provider_separate_state_and_thirty_day_extension(client):
    from datetime import date
    before = client.get("/api/reader/demo-reader/borrows").json()["data"][0]
    result = client.post("/api/renew", json={"reader_id": "demo-reader", "book_id": before["book_id"]}).json()
    assert result["dataset_label"] == "simulated" and result["is_live"] is False
    assert (date.fromisoformat(result["data"]["new_due_date"]) - date.fromisoformat(before["due_date"])).days == 30
    assert client.get("/api/reader/some-real-reader/borrows").status_code == 401
    holdings = client.get("/api/books/holdings/fictional").json()
    assert holdings["dataset_label"] == "simulated" and holdings["is_live"] is False


def test_sse_answers_real_rules_without_claiming_business_success(client):
    response = client.post("/api/chat", json={"message": "普通图书能借几天怎么续借", "session_id": "rules"})
    stream = events(response)
    assert stream[-1] == {"type": "done"}
    text = "".join(row.get("token", "") for row in stream)
    assert "60 天" in text and "3 次" in text
    assert "https://library.xujc.com/jyqx/list.htm" in text
    assert "续借成功" not in text


def test_sse_search_extracts_title_and_keeps_unknown_status(client):
    stream = events(client.post("/api/chat", json={"message": "帮我找《Python程序设计》", "session_id": "books"}))
    cards = [row["data"] for row in stream if row["type"] == "card"]
    assert cards and all(row["available"] is None and row["location"] is None for row in cards)
    assert all(row["is_live"] is False for row in cards)


def test_anonymous_chat_cannot_select_reader_or_read_other_cookie_history(client):
    assert client.post("/api/chat", json={"message": "推荐图书", "reader_id": "someone"}).status_code == 401
    client.post("/api/chat", json={"message": "普通图书续借规则", "session_id": "shared-name"})
    assert client.get("/api/chat/history/shared-name").json()["data"]
    with TestClient(app) as other:
        assert other.get("/api/chat/history/shared-name").json()["data"] == []


def test_usage_report_optional_and_protected(client, fixture_data):
    assert client.get("/api/admin/stats/usage").status_code == 401
    empty = client.get("/api/admin/stats/usage", headers=admin()).json()["data"]
    assert empty["datasets"] == {}
    report = {"dataset_label": "simulated", "datasets": {"seats": {"rows": 9}}, "is_live": False, "limitations": []}
    (fixture_data / "usage.json").write_text(json.dumps(report), encoding="utf-8")
    assert client.get("/api/admin/stats/usage", headers=admin()).json()["data"] == report

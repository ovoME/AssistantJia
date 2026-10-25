import json
import time
import pytest
from app.config import settings
from app.auth import sign_reader_token
from app.services import local_data


@pytest.fixture
def integration(monkeypatch, fixture_data):
    monkeypatch.setattr(settings,"DATA_PROFILE","integration")
    monkeypatch.setattr(settings,"INTEGRATION_DATA_DIRECTORY",str(fixture_data/"integration"))
    monkeypatch.setattr(settings,"OPAC_PROVIDER","disabled")
    yield
    local_data._integration_provider.cache_clear()
    local_data._integration_directory.cache_clear()


def reader_headers():
    return {"Authorization":"Bearer "+sign_reader_token("demo-reader",settings.READER_TOKEN_SECRET,time.time()+3600)}


@pytest.mark.parametrize("query",["三体","物流","Python","F252.8/11"])
def test_integration_queries_work_without_author_local_data(client,integration,query):
    response=client.get("/api/books/search",params={"query":query})
    assert response.status_code==200
    body=response.json()
    assert body["data"] and body["dataset_label"]=="simulated" and body["is_live"] is False
    assert all(row["location"].startswith("模拟") and isinstance(row["available"],int) and row["updated_at"] for row in body["data"])
    assert all(row["reservation_supported"] for row in body["data"])


def test_integration_still_requires_existing_authentication(client,integration):
    assert client.get("/api/admin/stats/summary").status_code==401
    assert client.get("/api/recommend?reader_id=demo-reader").status_code==401
    assert client.get("/api/reader/demo-reader/borrows").status_code==401
    result=client.get("/api/recommend?reader_id=demo-reader",headers=reader_headers())
    assert result.status_code==200 and result.json()["data"]


def test_trend_uses_only_simulation_dates(client,integration):
    body=client.get("/api/admin/stats/trend",headers={"X-Admin-Token":settings.ADMIN_TOKEN}).json()
    assert body["dataset_label"]=="simulated"
    assert len(body["data"])==30 and sum(row["count"] for row in body["data"])==180
    assert body["data"][0]["date"]=="2026-09-01"
    assert body["data"][-1]["date"]=="2026-09-30"


def test_current_copy_renew_and_reserve_are_linked(client,integration):
    headers=reader_headers()
    current=client.get("/api/reader/me/borrows",headers=headers).json()["data"][0]
    holdings=client.get("/api/books/holdings/"+current["book_id"]).json()["data"]
    assert any(row["book_id"]==current["book_id"] and row["status"]=="on_loan" for row in holdings["copies"])
    renewed=client.post("/api/renew",json={"reader_id":"me","book_id":current["book_id"]},headers=headers).json()
    assert renewed["dataset_label"]=="simulated" and renewed["data"]["renew_count"]==1
    isbn=holdings["book_key"].split(":",1)[1]
    reserved=client.post("/api/reserve",json={"reader_id":"me","isbn":isbn},headers=headers).json()
    assert reserved["code"]==0 and reserved["dataset_label"]=="simulated"
    assert client.get("/api/books/holdings/DEMO-CAT-0001").json()["data"]["book_key"]==holdings["book_key"]


def test_ds_tool_and_model_receive_actual_shared_fixture(client,integration,monkeypatch):
    from app.agent.tools.search_books import search_books
    result=json.loads(search_books.invoke({"query":"物流","limit":3}))
    assert result["books"] and result["dataset_label"]=="simulated"
    assert result["books"][0]["available"]==2
    import langchain_openai
    captured=[]
    class FakeDS:
        def __init__(self,**kwargs): pass
        async def ainvoke(self,messages):
            captured.extend(messages)
            from types import SimpleNamespace
            return SimpleNamespace(content="模拟查询完成。")
    monkeypatch.setattr(langchain_openai,"ChatOpenAI",FakeDS)
    monkeypatch.setattr(settings,"LLM_API_KEY","unit-test-no-network")
    response=client.post("/api/chat",json={"message":"帮我找《物流管理》"})
    evidence=[message for message in captured if message.type=="tool"]
    assert evidence and '"available": 2' in evidence[0].content and "模拟主楼" in evidence[0].content
    assert '"type": "done"' in response.text


def test_switching_to_local_never_infers_physical_shelves(client,integration,monkeypatch,fixture_data):
    assert client.get("/api/books/search?query=Python").json()["data"][0]["available"] is not None
    monkeypatch.setattr(settings,"DATA_PROFILE","local")
    rows=client.get("/api/books/search?query=Python").json()["data"]
    assert rows and all(row["available"] is None and row["location"] is None for row in rows)

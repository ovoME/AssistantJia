"""检查聊天、HTTP 与工具对同一模拟书目使用多样推荐。"""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import local_data
from app.services.recommendations import discover


@pytest.fixture
def integration(monkeypatch, fixture_data):
    monkeypatch.setattr(settings, "DATA_PROFILE", "integration")
    monkeypatch.setattr(settings, "INTEGRATION_DATA_DIRECTORY", str(fixture_data / "integration"))
    yield
    local_data._integration_directory.cache_clear()


def cards(response):
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    return [event["data"] for event in events if event["type"] == "card"], "".join(
        event.get("token", "") for event in events if event["type"] == "content"
    )


def test_repeated_chat_question_rotates_results_and_reports_actual_titles(client, integration):
    first, first_text = cards(client.post("/api/chat", json={"message": "推荐几本书", "session_id": "variety"}))
    second, second_text = cards(client.post("/api/chat", json={"message": "推荐几本书", "session_id": "variety"}))
    assert len(first) == len(second) == 5
    assert {row["book_key"] for row in first}.isdisjoint(row["book_key"] for row in second)
    assert first[0]["title"] in first_text and second[0]["title"] in second_text
    assert first_text != second_text


@pytest.mark.parametrize("message,expected", [("推荐3本书", 3), ("请推荐十本图书", 10)])
def test_chat_respects_common_requested_counts(client, integration, message, expected):
    rows, _ = cards(client.post("/api/chat", json={"message": message}))
    assert len(rows) == expected


def test_topic_flows_through_chat_http_and_tool(client, integration):
    from app.agent.tools.recommend import recommend_books
    message = "给我推荐3本关于Python的书"
    rows, _ = cards(client.post("/api/chat", json={"message": message}))
    assert rows and all("python" in row["title"].lower() for row in rows)
    response = client.get("/api/recommend", params={"query": message})
    assert response.status_code == 200
    assert response.json()["data"] and all("python" in row["title"].lower() for row in response.json()["data"])
    result = json.loads(recommend_books.invoke({"query": "Python", "limit": 3}))
    assert result["recommendations"] and all("python" in row["title"].lower() for row in result["recommendations"])
    missing, text = cards(client.post("/api/chat", json={"message": "推荐不存在的xyz主题的书"}))
    assert not missing and "没有找到" in text


def test_recommend_api_rotates_and_hot_books_still_reports_actual_counts(client, integration):
    first = client.get("/api/recommend").json()["data"]
    second = client.get("/api/recommend").json()["data"]
    assert len(first) == len(second) == 5
    assert {row["book_key"] for row in first}.isdisjoint(row["book_key"] for row in second)
    hot = client.get("/api/hot-books").json()["data"]
    assert [row["count"] for row in hot] == sorted((row["count"] for row in hot), reverse=True)


def test_simultaneous_same_session_requests_do_not_repeat_a_batch(integration):
    engine = local_data.borrowing().engine
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(discover, engine, None, 5, "推荐几本书", "concurrent-test") for _ in range(2)]
        first, second = [future.result() for future in futures]
    assert {row["book_key"] for row in first}.isdisjoint(row["book_key"] for row in second)


def test_another_session_does_not_change_the_previous_batch(integration):
    engine = local_data.borrowing().engine
    first = discover(engine, None, 5, "推荐几本书", "visitor-a")
    discover(engine, None, 5, "推荐几本书", "visitor-b")
    second = discover(engine, None, 5, "推荐几本书", "visitor-a")
    assert {row["book_key"] for row in first}.isdisjoint(row["book_key"] for row in second)


def test_model_receives_the_actual_recommended_books(client, integration, monkeypatch):
    import langchain_openai
    captured = []

    class Model:
        def __init__(self, **kwargs):
            pass

        async def ainvoke(self, messages):
            captured.append(next(message.content for message in messages if message.type == "tool"))
            return SimpleNamespace(content="这些是推荐的书。")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", Model)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-only")
    first, first_text = cards(client.post("/api/chat", json={"message": "推荐几本书", "session_id": "model"}))
    second, second_text = cards(client.post("/api/chat", json={"message": "推荐几本书", "session_id": "model"}))
    assert len(captured) == 2
    assert [row["book_key"] for row in json.loads(captured[0])["recommendations"]] == [row["book_key"] for row in first]
    assert [row["book_key"] for row in json.loads(captured[1])["recommendations"]] == [row["book_key"] for row in second]
    assert {row["book_key"] for row in first}.isdisjoint(row["book_key"] for row in second)
    assert first[0]["title"] in first_text and second[0]["title"] in second_text
    assert first_text != second_text


def test_model_cannot_invent_books_when_no_topic_matches(client, integration, monkeypatch):
    import langchain_openai
    calls = []

    class InventingModel:
        def __init__(self, **kwargs):
            calls.append(True)

        async def ainvoke(self, messages):
            return SimpleNamespace(content="我给你推荐一本虚构的书。")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", InventingModel)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-only")
    rows, text = cards(client.post("/api/chat", json={"message": "推荐不存在的xyz主题的书"}))
    assert not rows and "没有找到" in text
    assert not calls

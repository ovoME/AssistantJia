"""验证先由模型理解意图，再使用实际数据；测试不调用外部模型。"""
import json
import time
from types import SimpleNamespace

import pytest

from app.auth import sign_reader_token
from app.config import settings
from app.services import local_data


@pytest.fixture
def integration(monkeypatch, fixture_data):
    monkeypatch.setattr(settings, "DATA_PROFILE", "integration")
    monkeypatch.setattr(settings, "INTEGRATION_DATA_DIRECTORY", str(fixture_data / "integration"))
    yield
    local_data._integration_directory.cache_clear()


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def install_model(monkeypatch, selector):
    import langchain_openai
    calls = []

    class Model:
        def __init__(self, **kwargs):
            self.router = False

        def bind_tools(self, tools):
            self.router = True
            calls.append(("bind", {tool.name for tool in tools}))
            return self

        async def ainvoke(self, messages):
            if self.router:
                calls.append(("route", messages))
                selected = selector(messages)
                return SimpleNamespace(content="", tool_calls=[] if selected is None else [selected])
            calls.append(("reply", messages))
            return SimpleNamespace(content="好的，我来帮你看看。")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", Model)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-no-network")
    return calls


def tool_call(name, **args):
    return {"name": name, "args": args, "id": "routing-test", "type": "tool_call"}


def test_model_analyzes_popular_request_before_keyword_fallback(client, integration, monkeypatch):
    calls = install_model(monkeypatch, lambda messages: tool_call("recommend_books", popular=True, limit=5))
    question = "你给我推荐一点热门的书籍把"
    results = []
    for _ in range(2):
        items = events(client.post("/api/chat", json={"message": question, "session_id": "model-first"}))
        cards = [row["data"] for row in items if row["type"] == "card"]
        assert len(cards) == 5 and all(row["strategy"] == "popular" for row in cards)
        results.append({row["book_key"] for row in cards})
    assert results[0].isdisjoint(results[1])
    assert [kind for kind, _ in calls].count("route") == 2
    assert [kind for kind, _ in calls].count("reply") == 2
    assert all("renew_book" not in value and "reserve_book" not in value for kind, value in calls if kind == "bind")


def test_model_extracted_topic_and_quantity_reach_the_algorithm(client, integration, monkeypatch):
    calls = install_model(monkeypatch, lambda messages: tool_call("recommend_books", query="计算机", limit=2))
    question = "刚入门写程序，有适合初学者的材料吗"
    items = events(client.post("/api/chat", json={"message": question}))
    cards = [row["data"] for row in items if row["type"] == "card"]
    assert len(cards) == 2 and all(row["call_number"].startswith("TP3") for row in cards)
    assert any(kind == "route" and messages[-1].content == question for kind, messages in calls)
    tool_args = next(row["args"] for row in items if row["type"] == "tool_call")
    assert tool_args["query"] == "计算机" and tool_args["limit"] == 2


def test_model_can_infer_popular_intent_without_the_keyword(client, integration, monkeypatch):
    install_model(monkeypatch, lambda messages: tool_call("recommend_books", popular=True))
    items = events(client.post("/api/chat", json={"message": "大家平时都爱看的有哪些"}))
    cards = [row["data"] for row in items if row["type"] == "card"]
    assert len(cards) == 5 and all(row["strategy"] == "popular" for row in cards)


def test_model_uses_the_prior_conversation_for_followup(client, integration, monkeypatch):
    calls = install_model(monkeypatch, lambda messages: tool_call("recommend_books", query="Python", limit=1))
    for question in ("我想学 Python", "再推荐一本"):
        items = events(client.post("/api/chat", json={"message": question, "session_id": "followup"}))
        cards = [row["data"] for row in items if row["type"] == "card"]
        assert cards and all("python" in row["title"].lower() for row in cards)
    routes = [messages for kind, messages in calls if kind == "route"]
    assert len(routes) == 2
    assert any(message.type == "human" and message.content == "我想学 Python" for message in routes[1])
    assert routes[1][-1].content == "再推荐一本"


def test_model_intent_is_respected_when_keywords_would_match(client, integration, monkeypatch):
    calls = install_model(monkeypatch, lambda messages: None)
    items = events(client.post("/api/chat", json={"message": "今天不要给我推荐图书，只想打个招呼"}))
    assert not any(row["type"] in {"tool_call", "card"} for row in items)
    assert any(kind == "route" for kind, _ in calls)


def test_model_without_tool_uses_grounded_data_for_clear_recommendation(client, integration, monkeypatch):
    calls = install_model(monkeypatch, lambda messages: None)
    items = events(client.post("/api/chat", json={"message": "推荐几本热门的书"}))
    cards = [row["data"] for row in items if row["type"] == "card"]
    assert len(cards) == 5 and all(row["strategy"] == "popular" for row in cards)
    assert any(kind == "route" for kind, _ in calls)
    assert "本地规则" in "".join(row.get("token", "") for row in items if row["type"] == "content")


def test_model_unavailable_uses_local_recommendation_fallback(client, integration, monkeypatch):
    import langchain_openai

    class BrokenModel:
        def __init__(self, **kwargs):
            raise RuntimeError("test-model-failure")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", BrokenModel)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-no-network")
    items = events(client.post("/api/chat", json={"message": "你给我推荐一点热门的书籍把"}))
    cards = [row["data"] for row in items if row["type"] == "card"]
    assert len(cards) == 5 and all(row["strategy"] == "popular" for row in cards)
    assert "test-model-failure" not in json.dumps(items, ensure_ascii=False)
    assert "本地规则" in "".join(row.get("token", "") for row in items if row["type"] == "content")


def test_model_cannot_select_another_reader_or_write_tool(client, integration, monkeypatch):
    install_model(monkeypatch, lambda messages: tool_call("recommend_books", reader_id="demo-peer"))
    token = sign_reader_token("demo-reader", settings.READER_TOKEN_SECRET, time.time() + 3600)
    items = events(client.post("/api/chat", json={"message": "按我的兴趣推荐", "session_id": "identity"},
                               headers={"Authorization": "Bearer " + token}))
    cards = [row["data"] for row in items if row["type"] == "card"]
    assert cards and not {row["book_key"] for row in cards} & local_data.borrowing().engine._histories["demo-reader"]
    assert "demo-peer" not in json.dumps(items, ensure_ascii=False)
    install_model(monkeypatch, lambda messages: tool_call("renew_book", reader_id="demo-reader", book_id="fake"))
    items = events(client.post("/api/chat", json={"message": "如何续借"}))
    assert all(row.get("tool") != "renew_book" for row in items if row["type"] == "tool_call")


def test_model_can_request_own_borrows_without_inventing_reader_identity(client, integration, monkeypatch):
    install_model(monkeypatch, lambda messages: tool_call("get_user_borrows"))
    items = events(client.post("/api/chat", json={"message": "我借了哪些书"}))
    text = "".join(row.get("token", "") for row in items if row["type"] == "content")
    assert any(row.get("tool") == "get_user_borrows" for row in items)
    assert "登录" in text


def test_explicit_rejection_of_popular_overrides_incorrect_model_flag(client, integration, monkeypatch):
    install_model(monkeypatch, lambda messages: tool_call("recommend_books", popular=True))
    items = events(client.post("/api/chat", json={"message": "不要推荐热门的书"}))
    cards = [row["data"] for row in items if row["type"] == "card"]
    assert cards and all(row["strategy"] != "popular" for row in cards)


def test_no_tool_result_preserves_local_multisource_evidence(client, integration, monkeypatch):
    calls = install_model(monkeypatch, lambda messages: None)
    items = events(client.post("/api/chat", json={"message": "图书馆现在人多吗"}))
    assert any(row.get("tool") == "query_multimodal_data" for row in items)
    text = "".join(row.get("token", "") for row in items if row["type"] == "content")
    assert "实时" in text and "没有已导入" in text
    assert not any(kind == "reply" for kind, _ in calls)

"""验证可选 LLM 收到实际工具结果；不调用外部付费模型。"""
from types import SimpleNamespace
import json
from app.config import settings


def test_model_receives_tool_evidence_and_unknown_status(client, monkeypatch):
    import langchain_openai
    captured = []

    class FakeModel:
        def __init__(self, **kwargs):
            pass

        async def ainvoke(self, messages):
            captured.extend(messages)
            return SimpleNamespace(content="找到本地书目。")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", FakeModel)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-no-network-key")
    response = client.post("/api/chat", json={"message": "帮我找《Python程序设计》"})
    evidence = [message for message in captured if message.type == "tool"]
    assert evidence and '"available": null' in evidence[0].content
    assert '"dataset_label": "simulated"' in evidence[0].content
    reply = "".join(json.loads(line[6:]).get("token", "") for line in response.text.splitlines() if line.startswith("data: "))
    assert "实时可借状态" in reply


def test_model_outage_preserves_grounded_local_answer(client, monkeypatch):
    import langchain_openai

    class BrokenModel:
        def __init__(self, **kwargs):
            raise RuntimeError("test-only-model-outage")

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", BrokenModel)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-no-network-key")
    response = client.post("/api/chat", json={"message": "推荐图书"})
    assert '"type": "done"' in response.text
    assert "未核实" in response.text
    assert "test-only-model-outage" not in response.text


def test_router_decides_intent_when_keyword_table_misses(client, monkeypatch):
    """关键词表漏掉的问法（如"在不在馆"）应由模型判定该调哪个工具，而不是落到闲聊瞎答。"""
    import langchain_openai
    bound = []

    class RouterModel:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, tools):
            bound.extend(tools)
            return self

        async def ainvoke(self, messages):
            return SimpleNamespace(content="", tool_calls=[
                {"name": "search_books", "args": {"query": "三体"}, "id": "r1", "type": "tool_call"}
            ])

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", RouterModel)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-no-network-key")
    response = client.post("/api/chat", json={"message": "三体在不在馆"})
    assert bound, "路由时必须把只读工具交给模型"
    assert '"tool": "search_books"' in response.text
    assert '"type": "done"' in response.text


def test_router_never_exposes_write_tools(client, monkeypatch):
    """续借、预约属写操作，不能被模型自行触发。"""
    import langchain_openai
    bound = []

    class RouterModel:
        def __init__(self, **kwargs):
            pass

        def bind_tools(self, tools):
            bound.extend(tools)
            return self

        async def ainvoke(self, messages):
            return SimpleNamespace(content="", tool_calls=[])

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", RouterModel)
    monkeypatch.setattr(settings, "LLM_API_KEY", "unit-test-no-network-key")
    client.post("/api/chat", json={"message": "三体在不在馆"})
    names = {getattr(tool, "name", "") for tool in bound}
    assert "search_books" in names
    assert "renew_book" not in names and "reserve_book" not in names

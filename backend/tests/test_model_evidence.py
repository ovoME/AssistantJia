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

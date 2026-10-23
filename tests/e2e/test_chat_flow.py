"""E2E 集成测试：按 docs/api-contract.md 契约模拟核心业务闭环。

覆盖场景（对齐方案验收标准）：
1. 健康检查
2. 图书检索（OPAC）→ 返回书名/索书号/架位/在馆状态
3. 读者当前借阅查询
4. 续借 / 预约（业务失败必须返回明确错误码与话术，不编造）
5. 个性化推荐 / 热门榜单
6. 管理端借阅概览（36,908 条口径）
7. 对话 SSE 流式输出（含 done 结束事件）
"""
import pytest

from conftest import HEALTH_URL, assert_ok


# ---- 场景1：健康检查 ----
@pytest.mark.e2e
def test_health():
    import httpx
    r = httpx.get(HEALTH_URL, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json().get("code") == 0


# ---- 场景2：图书检索（OPAC） ----
@pytest.mark.e2e
def test_book_search(client):
    body = assert_ok(client.get("/books/search", params={"query": "三体", "limit": 5}))
    books = body.get("data") or []
    assert len(books) > 0, "应返回检索结果"
    first = books[0]
    assert first.get("title"), f"缺少题名: {first}"
    assert first.get("call_number"), f"缺少索书号: {first}"
    # 架位 / 在馆状态（契约字段，二者至少其一）
    assert ("location" in first) or ("status" in first), f"缺少架位或在馆状态: {first}"


# ---- 场景3：读者当前借阅 ----
@pytest.mark.e2e
def test_reader_borrows(client):
    body = assert_ok(client.get("/reader/2023001/borrows"))
    data = body.get("data")
    assert data is not None, "应返回借阅列表（可为空数组）"


# ---- 场景4a：续借（失败须明确话术） ----
@pytest.mark.e2e
def test_renew(client):
    r = client.post("/renew", json={"reader_id": "2023001", "book_id": "B20230911001"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "code" in body and "message" in body, f"契约字段缺失: {body}"
    # 成功返回 new_due_date；失败返回明确业务码与原因，不允许编造
    if body.get("code") != 0:
        assert body.get("message"), "失败时必须返回明确话术"
        assert body.get("code") in (4001, 4002, 4003, 5001), f"未知错误码: {body}"


# ---- 场景4b：预约（失败须明确话术） ----
@pytest.mark.e2e
def test_reserve(client):
    r = client.post("/reserve", json={"reader_id": "2023001", "isbn": "9787111544937"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "code" in body and "message" in body, f"契约字段缺失: {body}"
    if body.get("code") != 0:
        assert body.get("message"), "失败时必须返回明确话术"
        assert body.get("code") in (4001, 4002, 5001), f"未知错误码: {body}"


# ---- 场景5a：个性化推荐 ----
@pytest.mark.e2e
def test_recommend(client):
    body = assert_ok(client.get("/recommend", params={"reader_id": "2023001", "limit": 5}))
    books = body.get("data") or []
    assert len(books) > 0, "应返回推荐书单"
    assert books[0].get("title"), "推荐条目缺少题名"


# ---- 场景5b：热门榜单 ----
@pytest.mark.e2e
def test_hot_books(client):
    body = assert_ok(client.get("/hot-books", params={"category": "I", "limit": 10}))
    assert body.get("data") is not None, "应返回热门榜单"


# ---- 场景6：管理端借阅概览 ----
@pytest.mark.e2e
def test_admin_summary(client):
    body = assert_ok(client.get("/admin/stats/summary"))
    data = body.get("data") or {}
    assert data.get("total_borrows") == 36908, f"借阅总条数口径不符: {data}"


# ---- 场景7：对话 SSE 流式输出 ----
@pytest.mark.e2e
def test_chat_sse(client):
    with client.stream(
        "POST",
        "/chat",
        json={"message": "帮我找一下《三体》在哪个架位", "session_id": "e2e-sse-001"},
    ) as r:
        assert r.status_code == 200, r.text
        chunks = list(r.iter_text())
    stream_text = "".join(chunks)
    assert "done" in stream_text, f"SSE 缺少 done 结束事件: {stream_text[:300]}"
    # 契约事件类型：thought / tool_call / content / card / done
    for evt in ("thought", "tool_call", "content", "card"):
        if evt in stream_text:
            break
    else:
        pytest.fail(f"SSE 未出现任何契约事件类型: {stream_text[:300]}")

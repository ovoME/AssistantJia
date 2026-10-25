"""性能测试：locust 并发压测。

启动：
    locust -f tests/e2e/locustfile.py --host http://localhost
浏览器打开 http://localhost:8090 设置并发并启动压测。
验收目标（方案标准）：普通问答 P95 ≤ 3s，工具调用类 P95 ≤ 8s。
"""
import random

from locust import HttpUser, between, task

READER_IDS = [f"20230{i:02d}" for i in range(1, 101)]
QUERIES = ["三体", "深入理解计算机系统", "算法导论", "Python编程"]


class ReaderUser(HttpUser):
    """模拟读者：混合对话、检索、推荐与榜单请求。"""

    wait_time = between(1, 3)

    @task(3)
    def chat_sse(self):
        with self.client.post(
            "/api/chat",
            json={
                "message": f"帮我找一下《{random.choice(QUERIES)}》在哪个架位",
                "session_id": f"perf-{random.randint(1, 1000)}",
            },
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"对话接口异常: {resp.status_code}")

    @task(2)
    def book_search(self):
        with self.client.get(
            "/api/books/search",
            params={"query": random.choice(QUERIES), "limit": 5},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200 or resp.json().get("code") != 0:
                resp.failure(f"检索接口异常: {resp.status_code}")

    @task(1)
    def recommend(self):
        with self.client.get(
            "/api/recommend",
            params={"reader_id": random.choice(READER_IDS), "limit": 5},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200 or resp.json().get("code") != 0:
                resp.failure(f"推荐接口异常: {resp.status_code}")

    @task(1)
    def hot_books(self):
        with self.client.get(
            "/api/hot-books",
            params={"limit": 10},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"榜单接口异常: {resp.status_code}")

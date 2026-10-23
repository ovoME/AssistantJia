"""E2E 集成测试基架。

接口契约：docs/api-contract.md（统一响应 {code, message, data}）。
默认目标：http://localhost/api（docker compose 一键启动后经 Nginx 进入后端）。
CI 中通过 BASE_URL 环境变量注入。
"""
import os
import time

import httpx
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://localhost/api")
# 健康检查为后端根路径（不在 /api 前缀下）
HEALTH_URL = os.environ.get("HEALTH_URL", "http://localhost:8000/health")
TIMEOUT = float(os.environ.get("E2E_TIMEOUT", "30"))


def _wait_ready(url: str, retries: int = 30, interval: float = 5.0) -> None:
    """等待服务就绪（健康检查）。"""
    last_error = None
    for _ in range(retries):
        try:
            r = httpx.get(url, timeout=5)
            if r.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(interval)
    raise RuntimeError(f"服务 {url} 未就绪，最后错误: {last_error}")


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    _wait_ready(HEALTH_URL)
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        yield c


def assert_ok(resp: httpx.Response) -> dict:
    """契约校验：HTTP 200 且业务码 code==0。"""
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:300]}"
    body = resp.json()
    assert body.get("code") == 0, f"业务错误: {body}"
    return body

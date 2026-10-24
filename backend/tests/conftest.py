"""所有接口测试使用独立的虚构数据，不读取开发者的真实借阅表。"""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
from app.services import local_data
from data.scripts.prepare_demo import prepare


@pytest.fixture(autouse=True)
def fixture_data(monkeypatch):
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT / "data" / "processed") as tmp:
        directory = Path(tmp)
        prepare(directory)
        monkeypatch.setattr(settings, "DATA_DIRECTORY", str(directory))
        monkeypatch.setattr(settings, "CATALOG_DATABASE", str(directory / "catalog.sqlite3"))
        monkeypatch.setattr(settings, "KNOWLEDGE_SOURCE", str(ROOT / "data" / "knowledge" / "rules.json"))
        monkeypatch.setattr(settings, "OPAC_PROVIDER", "demo")
        monkeypatch.setattr(settings, "ADMIN_TOKEN", "unit-test-admin-token-only")
        monkeypatch.setattr(settings, "READER_TOKEN_SECRET", "unit-test-reader-secret-at-least-32-characters")
        monkeypatch.setattr(settings, "LLM_API_KEY", None)
        monkeypatch.setattr(settings, "USAGE_REPORT", str(directory / "usage.json"))
        local_data._provider.cache_clear()
        yield directory
        local_data._catalog.cache_clear()
        local_data._borrowing.cache_clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as session:
        yield session

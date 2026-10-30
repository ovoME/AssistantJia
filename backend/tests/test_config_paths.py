from pathlib import Path

import pytest

import app.config as config
from app.services import data_manager


@pytest.mark.parametrize(
    ("config_file", "expected_root"),
    [
        (Path("/opt/assistant/backend/app/config.py"), Path("/opt/assistant")),
        (Path("/app/app/config.py"), Path("/app")),
    ],
)
def test_project_root_supports_source_and_container_layouts(config_file, expected_root):
    assert config._project_root_for(config_file) == expected_root


def test_relative_data_directory_resolves_under_container_root(monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", config._project_root_for(Path("/app/app/config.py")))
    assert config._resolve_path("./data/processed/service-demo") == "/app/data/processed/service-demo"


def test_data_manager_import_directory_uses_shared_project_root():
    assert data_manager.PROJECT_ROOT == config.PROJECT_ROOT

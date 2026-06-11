"""Fixtures compartilhadas dos testes.

Os testes padrão não tocam GPU, rede nem modelos reais: os geradores pesados
são substituídos por fakes via monkeypatch nos próprios testes. O import de
``main`` é pesado (torch + fork vendored do transformers) e por isso é feito
uma única vez por sessão.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def main_module():
    import main
    return main


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    """Redireciona o histórico de jobs para um arquivo temporário, evitando
    que os testes escrevam no data/history.jsonl real do projeto."""
    from services.jobs import job_manager

    history_path = tmp_path / "history.jsonl"
    monkeypatch.setattr(job_manager, "_history_path", history_path)
    return history_path


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redireciona settings/perfis para pastas temporárias e restaura a
    política de VRAM do árbitro após cada teste."""
    from services import config_store
    from services.resource_arbiter import arbiter

    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_store, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_store, "SETTINGS_PATH", config_dir / "settings.json")
    monkeypatch.setattr(config_store, "PROFILES_DIR", config_dir / "profiles")
    monkeypatch.setattr(config_store, "_settings_cache", {"settings": None, "mtime": None})
    yield config_dir
    if arbiter.policy != "exclusive":
        arbiter.set_policy("exclusive")


@pytest.fixture(autouse=True)
def isolated_retention(tmp_path, monkeypatch):
    """Redireciona a pasta de uploads retidos para um diretório temporário isolado por teste."""
    from services import input_retention
    retained_dir = tmp_path / "temp_uploads" / "retained"
    monkeypatch.setattr(input_retention, "RETAINED_DIR", retained_dir)
    monkeypatch.setattr(input_retention, "UPLOAD_DIR", tmp_path / "temp_uploads")
    return retained_dir


@pytest.fixture()
def client(main_module):
    from fastapi.testclient import TestClient

    with TestClient(main_module.app) as test_client:
        yield test_client


def parse_sse_payloads(body_text: str) -> list:
    """Converte um corpo text/event-stream nos dicts JSON dos eventos."""
    import json

    payloads = []
    for line in body_text.splitlines():
        if line.startswith("data: "):
            payloads.append(json.loads(line[len("data: "):]))
    return payloads

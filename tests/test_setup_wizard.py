import pytest
from services import config_store, env_check

def test_setup_status_reflects_first_run(client):
    settings = config_store.get_settings()
    settings.first_run_completed = False
    config_store.save_settings(settings)

    response = client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["first_run_completed"] is False
    assert "environment_ok" in data
    assert "suggested_preset" in data
    assert "retention" in data

def test_setup_complete_endpoint(client):
    settings = config_store.get_settings()
    settings.first_run_completed = False
    config_store.save_settings(settings)

    response = client.post("/api/setup/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["first_run_completed"] is True

    # Verifica se persistiu
    assert config_store.get_settings().first_run_completed is True

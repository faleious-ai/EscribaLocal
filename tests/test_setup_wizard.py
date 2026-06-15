import pytest
from pathlib import Path

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
    assert data["tts"]["status"] == "pending_voice"
    assert data["tts"]["ready"] is False
    assert data["setup_ready"] is False


def test_setup_status_marks_tts_ready_with_real_voice(client, monkeypatch):
    from services import voice_profiles

    monkeypatch.setattr(voice_profiles, "list_voices", lambda: {
        "presets": [],
        "custom": [{"id": "11111111-2222-3333-4444-555555555555", "is_default": True}],
        "total_disk_bytes": 123,
    })

    response = client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["tts"]["status"] == "ready"
    assert data["tts"]["ready"] is True
    assert data["tts"]["custom_voice_count"] == 1


def test_setup_wizard_has_voice_step_with_consent_and_library_cta():
    source = Path("static/js/setup_wizard.js").read_text(encoding="utf-8")

    assert "Criar sua voz" in source
    assert "consentimento" in source.lower()
    assert "wizard-open-voices" in source
    assert "openVoiceLibrary" in source

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

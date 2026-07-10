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
    monkeypatch.setattr(
        voice_profiles,
        "get_default_voice_id",
        lambda: "11111111-2222-3333-4444-555555555555",
    )

    response = client.get("/api/setup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["tts"]["status"] == "ready"
    assert data["tts"]["ready"] is True
    assert data["tts"]["custom_voice_count"] == 1


def test_setup_status_keeps_tts_pending_without_a_default_voice(client, monkeypatch):
    from services import voice_profiles

    monkeypatch.setattr(voice_profiles, "list_voices", lambda: {
        "presets": [],
        "custom": [{"id": "11111111-2222-3333-4444-555555555555", "is_default": False}],
        "total_disk_bytes": 123,
    })
    monkeypatch.setattr(voice_profiles, "get_default_voice_id", lambda: None)

    response = client.get("/api/setup/status")

    assert response.status_code == 200
    data = response.json()["tts"]
    assert data["custom_voice_count"] == 1
    assert data["ready"] is False
    assert data["status"] == "pending_voice"


def test_setup_status_marks_chatterbox_pending_without_real_voice(client):
    settings = config_store.get_settings()
    settings.defaults.tts.tts_model = "chatterbox-tts-pt-br"
    config_store.save_settings(settings)

    response = client.get("/api/setup/status")

    assert response.status_code == 200
    data = response.json()["tts"]
    assert data["requires_voice"] is True
    assert data["ready"] is False
    assert data["status"] == "pending_voice"


def test_setup_wizard_embeds_real_voice_capture_controls():
    source = Path("static/js/setup_wizard.js").read_text(encoding="utf-8")

    assert "Criar sua voz" in source
    assert "consentimento" in source.lower()
    assert "wizard-voice-file" in source
    assert "wizard-voice-record-start" in source
    assert "wizard-voice-preview" in source
    assert "wizard-voice-discard" in source
    assert "wizard-voice-approve" in source
    assert "MediaRecorder" in source
    assert "/api/tts/voices/upload" in source
    assert "/api/tts/voices/record" in source
    assert "/set-default" in source
    assert "consentInput.checked" in source
    assert "clearVoiceDraft();" in source
    assert "stopVoiceStream();" in source
    assert "Falha ao criar a voz" in source
    assert "wizard-open-voices" not in source


def test_setup_wizard_shows_capture_text_without_submitting_it():
    source = Path("static/js/setup_wizard.js").read_text(encoding="utf-8")

    assert "Hoje, João trouxe café quente, pão de queijo, milho e chá." in source
    assert "leia este texto em voz alta durante a gravação" in source.lower()
    assert 'formData.append("text"' not in source


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


def test_setup_completion_preserves_pending_tts_without_voice(client):
    settings = config_store.get_settings()
    settings.first_run_completed = False
    settings.defaults.tts.tts_model = "chatterbox-tts-pt-br"
    config_store.save_settings(settings)

    completed = client.post("/api/setup/complete")
    status = client.get("/api/setup/status")

    assert completed.status_code == 200
    assert status.status_code == 200
    assert status.json()["first_run_completed"] is True
    assert status.json()["tts"]["status"] == "pending_voice"
    assert status.json()["tts"]["ready"] is False
    assert status.json()["setup_ready"] is False

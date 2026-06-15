from pathlib import Path

import pytest

from services import vibevoice_tts_1_5b as tts


def test_large_without_upstream_dependency_fails_before_loading(monkeypatch):
    def fake_find_spec(name):
        return None if name == "vibevoice" else object()

    def fail_if_loaded(model_key):
        raise AssertionError("Large loader should not run without the upstream dependency")

    monkeypatch.setattr(tts.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(tts, "_get_direct_vibevoice_model", fail_if_loaded)

    with pytest.raises(tts.LargeModelUnavailableError) as excinfo:
        tts.generate_voice_1_5b_with_metadata(
            text="Ola.",
            speaker_id="speaker_1",
            model_key="tts_large",
        )

    message = str(excinfo.value).lower()
    assert "dependencia upstream" in message
    assert "vibevoice" in message
    assert "fallback" not in message


def test_large_rejects_known_insufficient_vram_before_loading(monkeypatch):
    class FakeCuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def get_device_properties(_index):
            return type("Props", (), {"total_memory": 6_000_000_000})()

    def fake_find_spec(name):
        return object()

    def fail_if_loaded(model_key):
        raise AssertionError("Large loader should not run on known insufficient VRAM")

    monkeypatch.setattr(tts.importlib.util, "find_spec", fake_find_spec)
    monkeypatch.setattr(tts, "torch", type("FakeTorch", (), {"cuda": FakeCuda})())
    monkeypatch.setattr(tts, "_get_direct_vibevoice_model", fail_if_loaded)

    with pytest.raises(tts.LargeModelUnavailableError) as excinfo:
        tts.generate_voice_1_5b_with_metadata(
            text="Ola.",
            speaker_id="speaker_1",
            model_key="tts_large",
        )

    message = str(excinfo.value).lower()
    assert "hardware insuficiente" in message
    assert "6gb" in message
    assert "estrategia explicita" in message


def test_tts_generate_maps_large_preflight_error_to_clear_422(client, main_module, monkeypatch):
    def fake_generate(**_kwargs):
        raise tts.LargeModelUnavailableError(
            "VibeVoice-Large indisponivel: dependencia upstream 'vibevoice' ausente."
        )

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", fake_generate)

    response = client.post(
        "/api/tts/generate",
        data={
            "text": "Ola.",
            "tts_model": "tts_large",
            "voice_id": "11111111-2222-3333-4444-555555555555",
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"].lower()
    assert "dependencia upstream" in detail
    assert "vibevoice" in detail


def test_large_catalog_and_ui_explain_statuses(client):
    models = client.get("/api/models").json()["models"]
    large = next(model for model in models if model["id"] == "vibevoice-tts-large")
    notes = large["notes"].lower()

    assert large["recommended_for_6gb"] is False
    assert "6gb" in notes
    assert "biblioteca upstream" in notes
    assert "estrategia explicita" in notes

    help_text = Path("static/app.js").read_text(encoding="utf-8").lower()
    assert "nao instalado" in help_text
    assert "dependencia ausente" in help_text
    assert "hardware insuficiente" in help_text
    assert "erro de carga" in help_text

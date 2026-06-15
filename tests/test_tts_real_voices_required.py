import io
from pathlib import Path

import numpy as np
import pytest
import scipy.io.wavfile as wavfile


def make_speech_wav(seconds=4.0, sr=48000) -> bytes:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    audio = 0.3 * np.sin(2 * np.pi * 220 * t) * (np.sin(2 * np.pi * 2.0 * t) > -0.3)
    audio[: int(0.3 * sr)] = 0.0
    audio[-int(0.3 * sr):] = 0.0
    buffer = io.BytesIO()
    wavfile.write(buffer, sr, (audio * 32767).astype(np.int16))
    return buffer.getvalue()


def test_voice_library_lists_only_real_custom_voices(client, monkeypatch):
    from services import voice_profiles

    def fake_builder(reference_path):
        import torch
        return torch.ones(6, 1536, dtype=torch.float32), "rev-teste"

    monkeypatch.setattr(voice_profiles, "_embedding_builder", fake_builder)
    monkeypatch.setattr(voice_profiles, "_revision_getter", lambda: "rev-teste")

    response = client.post(
        "/api/tts/voices/upload",
        files={"file": ("voz.wav", make_speech_wav(), "audio/wav")},
        data={"name": "Minha voz", "consent_confirmed": "true"},
    )
    assert response.status_code == 200

    data = client.get("/api/tts/voices").json()
    assert data["presets"] == []
    assert [voice["name"] for voice in data["custom"]] == ["Minha voz"]


def test_tts_generate_requires_real_voice(client, main_module, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("gerador TTS nao deve rodar sem voz real")

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", fail_if_called)

    response = client.post(
        "/api/tts/generate",
        data={"text": "Ola.", "tts_model": "tts_1_5b"},
    )

    assert response.status_code == 422
    assert "voz" in response.json()["detail"].lower()


def test_tts_generate_rejects_windows_preset_voice(client, main_module, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("gerador TTS nao deve rodar com preset Windows")

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", fail_if_called)

    response = client.post(
        "/api/tts/generate",
        data={
            "text": "Ola.",
            "tts_model": "tts_1_5b",
            "voice_id": "preset_windows_1",
        },
    )

    assert response.status_code == 422
    assert "voz real" in response.json()["detail"].lower()


def test_tts_service_requires_real_voice_before_loading_model(monkeypatch):
    from services import vibevoice_tts_1_5b as tts
    from services import voice_profiles

    monkeypatch.setattr(voice_profiles, "get_default_voice_id", lambda: None)

    def fail_if_model_loads(*args, **kwargs):
        raise AssertionError("modelo nao deve carregar sem voz real")

    monkeypatch.setattr(tts, "_load_native_model", fail_if_model_loads)

    with pytest.raises(tts.VoiceUnavailableError) as excinfo:
        tts.generate_voice_1_5b_with_metadata(text="Ola.")

    assert "voz real" in str(excinfo.value).lower()


def test_tts_ui_does_not_present_windows_presets_as_voice_options():
    ui_sources = (
        Path("static/index.html").read_text(encoding="utf-8"),
        Path("static/js/voice_library.js").read_text(encoding="utf-8"),
    )

    for source in ui_sources:
        assert "Preset local" not in source
        assert "voz Windows" not in source


def test_tts_parameter_metadata_does_not_present_windows_presets(client):
    response = client.get("/api/parameters/tts")

    assert response.status_code == 200
    serialized = str(response.json())
    assert "preset local" not in serialized.lower()
    assert "voz do windows" not in serialized.lower()

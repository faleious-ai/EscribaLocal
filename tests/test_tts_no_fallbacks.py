import pytest
from pathlib import Path


@pytest.mark.parametrize(
    ("requested", "executed", "fallback", "allowed"),
    [
        ("tts_1_5b", "tts_1_5b", False, True),
        ("tts_1_5b", "chatterbox-tts-pt-br", False, False),
        ("chatterbox-tts-pt-br", "tts_1_5b", False, False),
        ("tts_1_5b", "tts_1_5b", True, False),
        ("chatterbox-tts-pt-br", "chatterbox-tts-pt-br", True, False),
        ("tts_1_5b", None, False, False),
    ],
)
def test_tts_engine_result_validation_matrix(main_module, requested, executed, fallback, allowed):
    result = {"wav_bytes": b"RIFFfake", "fallback": fallback}
    if executed is not None:
        result["engine_key"] = executed

    if allowed:
        assert main_module.validate_tts_engine_result(requested, result) == executed
    else:
        with pytest.raises(main_module.TtsEngineResultError):
            main_module.validate_tts_engine_result(requested, result)


def test_realtime_stream_fails_when_native_engine_unavailable(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    statuses = []
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    with pytest.raises(realtime.RealtimeUnavailableError) as excinfo:
        list(realtime.generate_voice_stream_0_5b(
            text="Ola, mundo.",
            status_callback=statuses.append,
        ))

    assert "Realtime 0.5B" in str(excinfo.value)
    assert statuses == []


def test_tts_generate_rejects_sapi5_failure_policy(client, main_module, monkeypatch):
    def fail_if_called(**kwargs):
        raise AssertionError("gerador TTS nao deve rodar com failure_policy=sapi5")

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", fail_if_called)

    response = client.post(
        "/api/tts/generate",
        data={
            "text": "Ola.",
            "tts_model": "tts_1_5b",
            "failure_policy": "sapi5",
        },
    )

    assert response.status_code == 400
    assert "failure_policy" in response.json()["detail"]


def test_tts_parameters_do_not_offer_sapi5_failure_policy(client):
    response = client.get("/api/parameters/tts")

    assert response.status_code == 200
    params = {param["name"]: param for param in response.json()["parameters"]}
    assert params["failure_policy"]["choices"] == ["fail", "cpu"]


def test_tts_service_rejects_sapi5_failure_policy_before_generation(monkeypatch):
    from services import vibevoice_tts_1_5b as tts

    def fail_if_native_runs(**kwargs):
        raise AssertionError("geracao nativa nao deve rodar com failure_policy=sapi5")

    def fail_if_fallback_runs(**kwargs):
        raise AssertionError("fallback SAPI5/tom nao deve ser chamado")

    monkeypatch.setattr(tts, "_run_native_vibevoice", fail_if_native_runs)
    monkeypatch.setattr(tts, "_fallback_sapi_or_sine", fail_if_fallback_runs, raising=False)

    with pytest.raises(ValueError) as excinfo:
        tts.generate_voice_1_5b_with_metadata(
            text="Ola.",
            failure_policy="sapi5",
        )

    assert "failure_policy" in str(excinfo.value)


def test_tts_generate_rejects_audio_from_unrequested_engine(client, main_module, monkeypatch):
    def wrong_engine(**kwargs):
        return {
            "wav_bytes": b"RIFFfake",
            "engine_key": "sapi5",
            "engine_label": "SAPI5",
            "fallback": True,
        }

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", wrong_engine)

    response = client.post(
        "/api/tts/generate",
        data={
            "text": "Ola.",
            "tts_model": "tts_1_5b",
            "voice_id": "11111111-2222-3333-4444-555555555555",
        },
    )

    assert response.status_code == 502
    assert "engine" in response.json()["detail"].lower()


def test_tts_generate_rejects_audio_without_explicit_engine_key(client, main_module, monkeypatch):
    def missing_engine_key(**kwargs):
        return {
            "wav_bytes": b"RIFFfake",
            "engine_label": "Legacy adapter without metadata",
            "fallback": False,
        }

    monkeypatch.setattr(main_module, "generate_voice_1_5b_with_metadata", missing_engine_key)

    response = client.post(
        "/api/tts/generate",
        data={
            "text": "Ola.",
            "tts_model": "tts_1_5b",
            "voice_id": "11111111-2222-3333-4444-555555555555",
        },
    )

    assert response.status_code == 502
    assert "engine" in response.json()["detail"].lower()


def test_voice_library_ui_does_not_offer_sapi5_failure_policy():
    source = Path("static/js/voice_library.js").read_text(encoding="utf-8")

    assert 'value="sapi5"' not in source
    assert "permitir SAPI5" not in source

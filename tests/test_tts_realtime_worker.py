import json
import sys


def test_realtime_worker_client_accepts_fake_success(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    captured = {}
    command = [
        sys.executable,
        "-c",
        (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            "captured = {"
            "'op': req.get('op'),"
            "'protocol_version': req.get('protocol_version'),"
            "'request_id_present': bool(req.get('request_id')),"
            "'worker_transport': req.get('transport')"
            "};"
            "json.dump({"
            "'ok': True,"
            "'engine': {'engine_key': 'realtime_0_5b', 'engine_label': 'Fake Realtime Worker', 'fallback': False},"
            "'audio': {'format': 'pcm_s16le', 'sample_rate': 24000, 'data_hex': '01000200'},"
            "'worker': {'transport': 'subprocess', 'protocol_version': 1, 'status': 'fake-success', 'echo': captured},"
            "'request_id': req.get('request_id')"
            "}, sys.stdout)"
        ),
    ]
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: command)

    result = realtime.generate_voice_realtime_wav_with_metadata("Ola.")

    assert result["engine_key"] == "realtime_0_5b"
    assert result["worker"] == {
        "transport": "subprocess",
        "protocol_version": 1,
        "status": "fake-success",
        "echo": {
            "op": "synthesize_stream",
            "protocol_version": 1,
            "request_id_present": True,
            "worker_transport": "subprocess",
        },
    }
    assert result["wav_bytes"].startswith(b"RIFF")


def test_realtime_worker_missing_returns_structured_unavailable(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    try:
        list(realtime.generate_voice_stream_0_5b("Ola."))
    except realtime.RealtimeUnavailableError as exc:
        payload = exc.to_payload()
    else:
        raise AssertionError("expected RealtimeUnavailableError")

    assert payload == {
        "type": "error",
        "code": "tts_realtime_unavailable",
        "engine_key": "realtime_0_5b",
        "message": (
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ),
    }


def test_tts_stream_reports_worker_unavailable_without_audio(client, monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    with client.websocket_connect("/api/tts/stream") as websocket:
        websocket.send_text(json.dumps({"text": "Ola.", "speaker_id": "speaker_1"}))
        message = json.loads(websocket.receive_text())

    assert message == {
        "type": "error",
        "code": "tts_realtime_unavailable",
        "engine_key": "realtime_0_5b",
        "message": (
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ),
    }


def test_tts_generate_returns_structured_worker_unavailable(client, monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    response = client.post(
        "/api/tts/generate",
        data={"text": "Ola.", "tts_model": "realtime_0_5b"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "type": "error",
        "code": "tts_realtime_unavailable",
        "engine_key": "realtime_0_5b",
        "message": (
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ),
    }


def test_realtime_module_does_not_load_transformers_pipeline_directly():
    from pathlib import Path

    source = Path("services/vibevoice_realtime_0_5b.py").read_text(encoding="utf-8")

    assert "from transformers import pipeline" not in source
    assert "vibevoice_streaming" not in source


def test_realtime_worker_healthcheck_returns_environment_metadata(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    command = [
        sys.executable,
        "-c",
        (
            "import json,sys,platform;"
            "req=json.load(sys.stdin);"
            "json.dump({"
            "'ok': True,"
            "'worker': {"
            "'transport': 'subprocess',"
            "'protocol_version': req.get('protocol_version'),"
            "'status': 'healthy',"
            "'environment': {"
            "'python_version': platform.python_version(),"
            "'platform': platform.system(),"
            "'supports_native_realtime': False"
            "}"
            "},"
            "'request_id': req.get('request_id')"
            "}, sys.stdout)"
        ),
    ]
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: command)

    status = realtime.get_realtime_worker_status()

    assert status["ok"] is True
    assert status["worker"]["transport"] == "subprocess"
    assert status["worker"]["protocol_version"] == 1
    assert status["worker"]["status"] == "healthy"
    assert status["worker"]["environment"]["supports_native_realtime"] is False


def test_realtime_worker_healthcheck_reports_missing_worker(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    status = realtime.get_realtime_worker_status()

    assert status["ok"] is False
    assert status["worker"]["status"] == "unavailable"
    assert status["error"]["code"] == "tts_realtime_unavailable"


def test_realtime_worker_status_endpoint(client, monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "get_realtime_worker_status", lambda: {
        "ok": True,
        "worker": {
            "transport": "subprocess",
            "protocol_version": 1,
            "status": "healthy",
            "environment": {
                "python_version": "3.12.0",
                "platform": "Windows",
                "supports_native_realtime": False,
            },
        },
    })

    response = client.get("/api/tts/realtime-worker/status")

    assert response.status_code == 200
    assert response.json()["worker"]["status"] == "healthy"

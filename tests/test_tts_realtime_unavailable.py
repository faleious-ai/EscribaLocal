import json
from pathlib import Path


def test_tts_stream_reports_realtime_unavailable_without_audio(client, monkeypatch):
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


def test_tts_generate_rejects_realtime_with_worker_limitation(client, monkeypatch):
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


def test_realtime_ui_and_catalog_describe_unavailable_limitation(client):
    models = client.get("/api/models").json()["models"]
    realtime = next(model for model in models if model["id"] == "vibevoice-tts-rt-0.5b")
    notes = realtime["notes"].lower()

    assert "indispon" in notes
    assert "vibevoice_streaming" in notes
    assert "clonagem" not in notes
    assert "feedback imediato" not in notes

    html = Path("static/index.html").read_text(encoding="utf-8").lower()
    assert "assistente de voz" not in html
    assert "feedback imediato" not in html

"""Lote 1 — testes de inicialização e contratos básicos da API."""
import pytest

from tests.conftest import parse_sse_payloads


def test_app_imports_without_pwa_dir(main_module):
    # A pasta escriba-pwa-standalone não existe neste repositório; o app deve
    # subir mesmo assim (regressão do RuntimeError do StaticFiles).
    import os
    pwa_dir = os.path.join(os.path.dirname(main_module.__file__), "escriba-pwa-standalone")
    assert not os.path.isdir(pwa_dir), "pré-condição do teste: pasta pwa ausente"
    mounted_paths = [getattr(route, "path", None) for route in main_module.app.routes]
    assert "/pwa" not in mounted_paths


def test_index_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_system_status_contract(client):
    response = client.get("/api/system-status")
    assert response.status_code == 200
    status = response.json()

    assert {"cpu", "ram", "gpu"} <= set(status.keys())
    assert {"percent", "cores", "physical_cores"} <= set(status["cpu"].keys())
    assert {"total_gb", "used_percent", "free_gb"} <= set(status["ram"].keys())
    assert {"available", "name", "vram_total_mb", "vram_allocated_mb", "vram_cached_mb"} <= set(status["gpu"].keys())


def test_logs_recent(client):
    response = client.get("/api/logs/recent")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "events"
    assert isinstance(payload["lines"], list)


def test_runtime_patches_idempotent():
    from services.runtime_patches import apply_runtime_patches
    import torch

    apply_runtime_patches()
    apply_runtime_patches()
    assert hasattr(torch, "float8_e8m0fnu")


def _fake_whisper_generator(**kwargs):
    yield {"type": "status", "message": "Carregando modelo (fake)"}
    yield {
        "type": "model_status",
        "caption": "Modelo em uso",
        "engine_key": "tiny",
        "engine_label": "Whisper tiny (faster-whisper)",
        "device": "cpu",
        "compute_type": "int8",
        "fallback": False,
    }
    yield {"type": "meta", "language": "pt", "language_probability": 0.99, "duration": 1.0}
    yield {"type": "progress", "progress": 100.0, "segment": {"start": 0.0, "end": 1.0, "text": "olá mundo"}}
    yield {"type": "done", "full_transcript": [{"start": 0.0, "end": 1.0, "text": "olá mundo"}]}


def test_transcribe_sse_contract(client, main_module, monkeypatch):
    # Contrato de regressão: o frontend depende da sequência e do shape destes
    # eventos SSE (status/model_status/meta/progress/done).
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fake_whisper_generator)

    response = client.post(
        "/api/transcribe",
        files={"file": ("teste.wav", b"RIFF0000fakewav", "audio/wav")},
        data={"model": "tiny", "device": "cpu", "compute_type": "int8"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    payloads = parse_sse_payloads(response.text)
    types = [p["type"] for p in payloads]

    assert "model_status" in types
    assert "done" in types
    assert types.index("model_status") < types.index("done")

    progress_events = [p for p in payloads if p["type"] == "progress"]
    assert progress_events, "esperado ao menos um evento de progresso"
    assert {"start", "end", "text"} <= set(progress_events[0]["segment"].keys())

    done_event = next(p for p in payloads if p["type"] == "done")
    assert done_event["full_transcript"][0]["text"] == "olá mundo"


def test_transcribe_rejects_empty_file(client, main_module, monkeypatch):
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fake_whisper_generator)
    response = client.post(
        "/api/transcribe",
        files={"file": ("vazio.wav", b"", "audio/wav")},
        data={"model": "tiny", "device": "cpu"},
    )
    assert response.status_code == 500

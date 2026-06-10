"""Lote 2 — testes do JobManager, cancelamento real e histórico."""
import json
import time

import pytest

from tests.conftest import parse_sse_payloads


def _fast_generator(**kwargs):
    yield {"type": "status", "message": "iniciando (fake)"}
    yield {"type": "progress", "progress": 50.0, "segment": {"start": 0.0, "end": 1.0, "text": "metade"}}
    yield {"type": "done", "full_transcript": [{"start": 0.0, "end": 1.0, "text": "metade"}]}


def _make_slow_generator(iterations=60, delay=0.15):
    """Gerador que honra cancel_event, como o transcriber real."""

    def slow_generator(**kwargs):
        cancel_event = kwargs.get("cancel_event")
        yield {"type": "status", "message": "transcrevendo devagar (fake)"}
        for i in range(iterations):
            if cancel_event is not None and cancel_event.is_set():
                yield {"type": "cancelled", "message": "Transcrição cancelada pelo usuário."}
                return
            time.sleep(delay)
            yield {
                "type": "progress",
                "progress": (i + 1) * 100.0 / iterations,
                "segment": {"start": float(i), "end": float(i + 1), "text": f"bloco {i}"},
            }
        yield {"type": "done", "full_transcript": []}

    return slow_generator


def _post_transcribe(client, **data):
    payload = {"model": "tiny", "device": "cpu", "compute_type": "int8"}
    payload.update(data)
    return client.post(
        "/api/transcribe",
        files={"file": ("teste.wav", b"RIFF0000fakewav", "audio/wav")},
        data=payload,
    )


def test_sse_emits_job_event_first(client, main_module, monkeypatch):
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fast_generator)
    response = _post_transcribe(client)

    assert response.status_code == 200
    assert response.headers.get("x-escriba-job-id")

    payloads = parse_sse_payloads(response.text)
    assert payloads[0]["type"] == "job"
    assert payloads[0]["job_id"] == response.headers["x-escriba-job-id"]
    # Compatibilidade: os eventos antigos continuam presentes após o novo.
    types = [p["type"] for p in payloads]
    assert "done" in types


def test_job_lifecycle_completed_and_history(client, main_module, monkeypatch, isolated_history):
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fast_generator)
    response = _post_transcribe(client)
    job_id = response.headers["x-escriba-job-id"]

    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["state"] == "completed"
    assert snapshot["progress"] == 100.0
    assert snapshot["kind"] == "transcribe_whisper"
    # Privacidade: parâmetros sensíveis não vão íntegros para o snapshot.
    assert not isinstance(snapshot["params"].get("whisper_prompt"), str) or snapshot["params"]["whisper_prompt"] is None

    history = client.get("/api/history").json()["history"]
    entry = next(e for e in history if e["job_id"] == job_id)
    assert entry["state"] == "completed"

    # O arquivo JSONL guarda uma linha por transição (queued/running/completed).
    lines = [json.loads(l) for l in isolated_history.read_text(encoding="utf-8").splitlines() if l.strip()]
    states = [l["state"] for l in lines if l["job_id"] == job_id]
    assert states == ["queued", "running", "completed"]


def test_cancel_stops_server_processing(client, main_module, monkeypatch):
    # O TestClient não entrega SSE incrementalmente (só ao fim do stream),
    # então o POST roda numa thread e o cancel é disparado pela API enquanto
    # o job está RUNNING — exatamente o que o botão Parar faz no navegador.
    import threading

    from fastapi.testclient import TestClient

    monkeypatch.setattr(main_module, "transcribe_audio_generator", _make_slow_generator())

    result = {}

    def run_transcription():
        with TestClient(main_module.app) as stream_client:
            response = stream_client.post(
                "/api/transcribe",
                files={"file": ("teste.wav", b"RIFF0000fakewav", "audio/wav")},
                data={"model": "tiny", "device": "cpu", "compute_type": "int8"},
            )
            result["payloads"] = parse_sse_payloads(response.text)

    started_at = time.monotonic()
    worker = threading.Thread(target=run_transcription)
    worker.start()

    job_id = None
    deadline = time.monotonic() + 5.0
    while job_id is None and time.monotonic() < deadline:
        jobs = client.get(
            "/api/jobs", params={"kind": "transcribe_whisper", "state": "running"}
        ).json()["jobs"]
        if jobs:
            job_id = jobs[0]["job_id"]
        else:
            time.sleep(0.1)
    assert job_id is not None, "job não chegou ao estado running em 5s"

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 200

    worker.join(timeout=10.0)
    assert not worker.is_alive(), "o stream não terminou após o cancelamento"
    elapsed = time.monotonic() - started_at

    # O gerador completo levaria ~9s; o cancelamento deve interromper bem antes.
    assert elapsed < 6.0, f"cancelamento demorou {elapsed:.1f}s"

    types = [p["type"] for p in result["payloads"]]
    assert "cancelled" in types
    assert "done" not in types

    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["state"] == "cancelled"


def test_cancel_unknown_job_returns_404(client):
    response = client.post("/api/jobs/nao-existe/cancel")
    assert response.status_code == 404


def test_cancel_finished_job_returns_409(client, main_module, monkeypatch):
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fast_generator)
    response = _post_transcribe(client)
    job_id = response.headers["x-escriba-job-id"]

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code == 409


def test_jobs_list_and_filters(client, main_module, monkeypatch):
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fast_generator)
    response = _post_transcribe(client)
    job_id = response.headers["x-escriba-job-id"]

    jobs = client.get("/api/jobs").json()["jobs"]
    assert any(j["job_id"] == job_id for j in jobs)

    completed = client.get("/api/jobs", params={"state": "completed"}).json()["jobs"]
    assert all(j["state"] == "completed" for j in completed)


def test_job_events_reattach_after_finish(client, main_module, monkeypatch):
    monkeypatch.setattr(main_module, "transcribe_audio_generator", _fast_generator)
    response = _post_transcribe(client)
    job_id = response.headers["x-escriba-job-id"]

    events_response = client.get(f"/api/jobs/{job_id}/events")
    assert events_response.status_code == 200
    payloads = parse_sse_payloads(events_response.text)
    assert payloads[0]["type"] == "job_snapshot"
    assert payloads[0]["job"]["state"] == "completed"


def test_failed_generator_marks_job_failed(client, main_module, monkeypatch):
    def failing_generator(**kwargs):
        yield {"type": "status", "message": "vai falhar"}
        yield {"type": "error", "message": "falha simulada do modelo"}

    monkeypatch.setattr(main_module, "transcribe_audio_generator", failing_generator)
    response = _post_transcribe(client)
    job_id = response.headers["x-escriba-job-id"]

    snapshot = client.get(f"/api/jobs/{job_id}").json()
    assert snapshot["state"] == "failed"
    assert "falha simulada" in (snapshot["error"] or "")

"""Lote 3 — testes do gestor de modelos (catálogo, download por job, remoção)."""
import time
from pathlib import Path

import pytest

from services import model_manager


@pytest.fixture()
def tmp_caches(tmp_path, monkeypatch):
    """Redireciona os caches de modelos para pastas temporárias vazias."""
    whisper_cache = tmp_path / "whisper-cache"
    hf_cache = tmp_path / "hf-cache"
    monkeypatch.setattr(model_manager, "get_whisper_cache_dir", lambda: whisper_cache)
    monkeypatch.setattr(model_manager, "get_hf_cache_dir", lambda: hf_cache)
    return {"whisper": whisper_cache, "hf": hf_cache}


def _install_fake_whisper(cache_dir: Path, repo_id="Systran/faster-whisper-tiny", size=1_500_000) -> Path:
    repo_dir = cache_dir / ("models--" + repo_id.replace("/", "--"))
    snapshot = repo_dir / "snapshots" / "fake"
    snapshot.mkdir(parents=True)
    (snapshot / "model.bin").write_bytes(b"0" * size)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    return repo_dir


def _wait_terminal(client, job_id: str, timeout: float = 6.0) -> dict:
    snapshot = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = client.get(f"/api/jobs/{job_id}").json()
        if snapshot["state"] in ("completed", "failed", "cancelled"):
            return snapshot
        time.sleep(0.05)
    raise AssertionError(f"job não terminou a tempo: {snapshot}")


# ------------------------------------------------------------- catálogo

def test_catalog_endpoint_shape(client, tmp_caches):
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()["models"]
    assert len(models) >= 10

    required_keys = {
        "id", "engine", "repo_id", "display_name", "approx_download_mb",
        "installed", "size_on_disk_mb", "loaded", "recommended_for_6gb", "notes",
    }
    for model in models:
        assert required_keys <= set(model.keys()), f"chaves faltando em {model['id']}"
        assert model["installed"] is False  # caches temporários vazios

    large = next(m for m in models if m["id"] == "vibevoice-tts-large")
    assert large["repo_id"] == "aoi-ot/VibeVoice-Large"
    assert large["recommended_for_6gb"] is False


def test_install_detection(tmp_caches):
    _install_fake_whisper(tmp_caches["whisper"])
    spec = model_manager.get_spec("whisper-tiny")
    status = model_manager.get_install_status(spec)
    assert status["installed"] is True
    assert status["size_on_disk_mb"] > 0
    assert "faster-whisper-tiny" in status["path"]


def test_incomplete_download_not_installed(tmp_caches):
    repo_dir = _install_fake_whisper(tmp_caches["whisper"])
    (repo_dir / "blobs").mkdir()
    (repo_dir / "blobs" / "abc.incomplete").write_bytes(b"parcial")
    status = model_manager.get_install_status(model_manager.get_spec("whisper-tiny"))
    assert status["installed"] is False
    assert status["partial"] is True


# -------------------------------------------------------------- remoção

def test_delete_model_route(client, tmp_caches):
    repo_dir = _install_fake_whisper(tmp_caches["whisper"])

    response = client.delete("/api/models/whisper-tiny")
    assert response.status_code == 200
    assert response.json()["freed_mb"] > 0
    assert not repo_dir.exists()

    assert client.delete("/api/models/whisper-tiny").status_code == 404
    assert client.delete("/api/models/nao-existe").status_code == 404


def test_delete_loaded_model_blocked(client, tmp_caches, monkeypatch):
    _install_fake_whisper(tmp_caches["whisper"])
    monkeypatch.setattr(model_manager, "_is_model_loaded", lambda spec: True)
    response = client.delete("/api/models/whisper-tiny")
    assert response.status_code == 409
    assert "memória" in response.json()["detail"].lower()


# -------------------------------------------------------------- download

def test_download_unknown_model_404(client):
    response = client.post("/api/models/download", json={"model_id": "nao-existe"})
    assert response.status_code == 404


def test_download_already_installed_409(client, tmp_caches):
    _install_fake_whisper(tmp_caches["whisper"])
    response = client.post("/api/models/download", json={"model_id": "whisper-tiny"})
    assert response.status_code == 409


def _fake_resolver(repo_id="Systran/faster-whisper-tiny", files=("model.bin", "config.json")):
    def resolver(spec):
        return repo_id, 2048, list(files)
    return resolver


def _fake_downloader_writes_files():
    def fake_download(repo, filename, cache_dir, cancel_event):
        snapshot = Path(cache_dir) / ("models--" + repo.replace("/", "--")) / "snapshots" / "fake"
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / filename).write_bytes(b"0" * 1_000_000)
    return fake_download


def test_download_job_completes(client, tmp_caches, monkeypatch):
    monkeypatch.setattr(model_manager, "_resolve_repo_and_files", _fake_resolver())
    monkeypatch.setattr(model_manager, "_download_file_interruptible", _fake_downloader_writes_files())

    response = client.post("/api/models/download", json={"model_id": "whisper-tiny"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    snapshot = _wait_terminal(client, job_id)
    assert snapshot["state"] == "completed"
    assert snapshot["kind"] == "model_download"
    assert snapshot["result_summary"]["repo_used"] == "Systran/faster-whisper-tiny"

    models = client.get("/api/models").json()["models"]
    tiny = next(m for m in models if m["id"] == "whisper-tiny")
    assert tiny["installed"] is True


def test_download_cancellation(client, tmp_caches, monkeypatch):
    monkeypatch.setattr(model_manager, "_resolve_repo_and_files", _fake_resolver(files=("a.bin", "b.bin")))

    def slow_download(repo, filename, cache_dir, cancel_event):
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                raise model_manager.JobCancelled()
            time.sleep(0.05)
        raise AssertionError("cancelamento não chegou ao download")

    monkeypatch.setattr(model_manager, "_download_file_interruptible", slow_download)

    response = client.post("/api/models/download", json={"model_id": "whisper-tiny"})
    job_id = response.json()["job_id"]

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")
    assert cancel_response.status_code in (200, 409)  # 409 se já transitou

    snapshot = _wait_terminal(client, job_id)
    assert snapshot["state"] == "cancelled"


# ---------------------------------------------------- progresso e ensure

def test_progress_poller_event_shape(tmp_path):
    events = []
    target = tmp_path / "repo"
    target.mkdir()
    poller = model_manager._ProgressPoller(target, total_bytes=1000, emit=events.append,
                                           filename_label="Teste", interval=0.03)
    poller.start()
    (target / "parte.bin").write_bytes(b"0" * 500)
    time.sleep(0.25)
    poller.stop()

    assert events, "poller não emitiu eventos"
    event = events[-1]
    assert event["type"] == "download_progress"
    # Contrato: o frontend consome exatamente estas chaves.
    assert {"percent", "speed_mb", "current_mb", "total_mb", "filename"} <= set(event.keys())
    assert 0 < event["percent"] <= 99.9


def test_ensure_skips_installed_and_unknown(tmp_caches):
    _install_fake_whisper(tmp_caches["whisper"])
    assert list(model_manager.ensure_whisper_model_events("tiny")) == []
    # Modelos fora do catálogo passam direto (faster-whisper resolve sozinho).
    assert list(model_manager.ensure_whisper_model_events("modelo-customizado")) == []


def test_ensure_downloads_when_missing(tmp_caches, monkeypatch):
    monkeypatch.setattr(model_manager, "_resolve_repo_and_files", _fake_resolver())
    monkeypatch.setattr(model_manager, "_download_file_interruptible", _fake_downloader_writes_files())

    events = list(model_manager.ensure_whisper_model_events("tiny"))
    types = [e["type"] for e in events]
    assert "cancelled" not in types
    assert "status" in types  # mensagem "Baixando ..."

    status = model_manager.get_install_status(model_manager.get_spec("whisper-tiny"))
    assert status["installed"] is True


def test_ensure_cancelled_mid_download(tmp_caches, monkeypatch):
    import threading

    cancel_event = threading.Event()
    monkeypatch.setattr(model_manager, "_resolve_repo_and_files", _fake_resolver(files=("a.bin", "b.bin")))

    def download_then_cancel(repo, filename, cache_dir, cancel_event_inner):
        # Simula cancelamento chegando durante o primeiro arquivo.
        cancel_event.set()
        raise model_manager.JobCancelled()

    monkeypatch.setattr(model_manager, "_download_file_interruptible", download_then_cancel)

    events = list(model_manager.ensure_whisper_model_events("tiny", cancel_event=cancel_event))
    assert events[-1]["type"] == "cancelled"

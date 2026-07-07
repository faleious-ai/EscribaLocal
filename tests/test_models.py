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


def test_default_model_cache_dirs_are_inside_project_models():
    expected = model_manager.PROJECT_ROOT / "models"
    assert model_manager.get_model_storage_dir() == expected
    assert model_manager.get_whisper_cache_dir() == expected
    assert model_manager.get_hf_cache_dir() == expected


def test_whisper_loader_uses_project_models_dir(monkeypatch):
    import sys
    import types

    from services import transcriber

    captured = {}

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

    fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    monkeypatch.setattr(transcriber.torch.cuda, "is_available", lambda: False)
    transcriber.unload_whisper_model()

    transcriber.get_whisper_model("tiny", "cpu", "int8")

    assert Path(captured["kwargs"]["download_root"]) == model_manager.get_model_storage_dir()
    transcriber.unload_whisper_model()





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


def test_download_cleans_orphan_incomplete_files(tmp_caches):
    spec = model_manager.get_spec("whisper-tiny")
    repo_dir = tmp_caches["whisper"] / "models--Systran--faster-whisper-tiny"
    blob_dir = repo_dir / "blobs"
    blob_dir.mkdir(parents=True)
    incomplete = blob_dir / "stalled.incomplete"
    incomplete.write_bytes(b"")

    model_manager._clean_stale_locks(spec)

    assert not incomplete.exists()


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


def test_vibevoice_1_5b_states(tmp_caches, monkeypatch):
    # Inicialmente, não instalado
    spec = model_manager.get_spec("vibevoice-tts-1.5b")
    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "not-installed"
    assert item["installed"] is False
    assert item.get("converted") is False

    # Simular download raw (arquivos raw presentes, sem converted)
    repo_dir = tmp_caches["hf"] / "models--microsoft--VibeVoice-1.5B"
    snapshot_dir = repo_dir / "snapshots" / "fake-snap"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "model-01.safetensors").write_bytes(b"0")
    (snapshot_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshot_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "downloaded-raw"
    assert item["installed"] is True
    assert item.get("converted") is False

    # Simular erro de conversão
    out_dir = model_manager._vibevoice_converted_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "conversion_error.txt").write_text("Erro de teste simulado", encoding="utf-8")

    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "error"
    assert item["conversion_error"] == "Erro de teste simulado"
    assert item["installed"] is False

    # Limpar erro e simular convertido com sucesso
    (out_dir / "conversion_error.txt").unlink()
    (out_dir / "config.json").write_text("{}", encoding="utf-8")
def test_incomplete_download_active_vs_orphan(tmp_caches):
    from services.jobs import job_manager, JobState

    # Caso 1: Download ativo em andamento
    repo_dir = _install_fake_whisper(tmp_caches["whisper"])
    (repo_dir / "blobs").mkdir()
    incomplete_file = repo_dir / "blobs" / "abc.incomplete"
    incomplete_file.write_bytes(b"parcial")
    
    # Criar um job de download ativo para o whisper-tiny
    job = job_manager.create(
        kind="model_download",
        params={"model_id": "whisper-tiny"},
    )
    job.state = JobState.RUNNING
    
    try:
        status = model_manager.get_install_status(model_manager.get_spec("whisper-tiny"))
        # Como há download ativo, o arquivo .incomplete é respeitado e o modelo fica como parcial
        assert status["installed"] is False
        assert status["partial"] is True
        assert incomplete_file.exists() is True
    finally:
        # Finalizar o job para manter o estado limpo
        job_manager.finish(job.job_id, JobState.CANCELLED)

    # Caso 2: Sem download ativo (órfão)
    # Ao chamar get_install_status, ele deve limpar o .incomplete órfão e reportar instalado
    status = model_manager.get_install_status(model_manager.get_spec("whisper-tiny"))
    assert status["installed"] is True
    assert status["partial"] is False
    assert incomplete_file.exists() is False


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


def test_vibevoice_1_5b_states(tmp_caches, monkeypatch):
    # Inicialmente, não instalado
    spec = model_manager.get_spec("vibevoice-tts-1.5b")
    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "not-installed"
    assert item["installed"] is False
    assert item.get("converted") is False

    # Simular download raw (arquivos raw presentes, sem converted)
    repo_dir = tmp_caches["hf"] / "models--microsoft--VibeVoice-1.5B"
    snapshot_dir = repo_dir / "snapshots" / "fake-snap"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "model-01.safetensors").write_bytes(b"0")
    (snapshot_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshot_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "downloaded-raw"
    assert item["installed"] is True
    assert item.get("converted") is False

    # Simular erro de conversão
    out_dir = model_manager._vibevoice_converted_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "conversion_error.txt").write_text("Erro de teste simulado", encoding="utf-8")

    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "error"
    assert item["conversion_error"] == "Erro de teste simulado"
    assert item["installed"] is False

    # Limpar erro e simular convertido com sucesso
    (out_dir / "conversion_error.txt").unlink()
    (out_dir / "config.json").write_text("{}", encoding="utf-8")

    catalog = model_manager.get_catalog_with_status()
    item = next(m for m in catalog if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "ready"
    assert item["installed"] is True
    assert item["converted"] is True


def test_convert_endpoint_failures(client, tmp_caches):
    # 1. Inexistente
    response = client.post("/api/models/inexistente/convert")
    assert response.status_code == 404

    # 2. Whisper (não suportado)
    response = client.post("/api/models/whisper-tiny/convert")
    assert response.status_code == 400
    assert "Apenas o VibeVoice TTS 1.5B suporta" in response.json()["detail"]

    # 3. VibeVoice 1.5B sem download prévio
    response = client.post("/api/models/vibevoice-tts-1.5b/convert")
    assert response.status_code == 404
    assert "precisa ser baixado primeiro" in response.json()["detail"]


def test_convert_endpoint_success(client, tmp_caches, monkeypatch):
    import safetensors.torch
    monkeypatch.setattr(safetensors.torch, "load_file", lambda path: {})

    # Criar snapshot bruto no cache temporário
    repo_dir = tmp_caches["hf"] / "models--microsoft--VibeVoice-1.5B"
    snapshot_dir = repo_dir / "snapshots" / "fake-snap"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "model-01.safetensors").write_bytes(b"0")
    (snapshot_dir / "config.json").write_text("{}", encoding="utf-8")
    (snapshot_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")

    # Mockar a conversão
    class FakeConverter:
        def convert_checkpoint(self, checkpoint, output_dir, config_path, push_to_hub, bfloat16, processor_config):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            (Path(output_dir) / "config.json").write_text("{}", encoding="utf-8")

    import sys
    import types
    fake_module = types.ModuleType("transformers.models.vibevoice.convert_vibevoice_to_hf")
    fake_module.convert_checkpoint = FakeConverter().convert_checkpoint
    
    import importlib
    orig_import_module = importlib.import_module
    def mock_import_module(name, *args, **kwargs):
        if name == "transformers.models.vibevoice.convert_vibevoice_to_hf":
            return fake_module
        return orig_import_module(name, *args, **kwargs)
        
    monkeypatch.setattr(importlib, "import_module", mock_import_module)

    # Chamar o endpoint
    response = client.post("/api/models/vibevoice-tts-1.5b/convert")
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert job_id

    # Esperar conclusão do job
    snapshot_job = _wait_terminal(client, job_id)
    assert snapshot_job["state"] == "completed"

    # Verificar que agora está pronto no catálogo
    resp_cat = client.get("/api/models")
    assert resp_cat.status_code == 200
    models = resp_cat.json()["models"]
    item = next(m for m in models if m["id"] == "vibevoice-tts-1.5b")
    assert item["status"] == "ready"
    assert item["converted"] is True

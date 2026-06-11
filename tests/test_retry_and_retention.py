import os
import shutil
import pytest
from services import config_store
from services.jobs import job_manager, JobState
from services.input_retention import retain_input_file, RETAINED_DIR, get_retention_metadata, prune_retained_inputs

@pytest.fixture(autouse=True)
def clean_retention_dir(tmp_path, monkeypatch):
    from services import input_retention
    monkeypatch.setattr(input_retention, "RETAINED_DIR", tmp_path / "temp_uploads" / "retained")
    monkeypatch.setattr(input_retention, "UPLOAD_DIR", tmp_path / "temp_uploads")
    
    retained_dir = tmp_path / "temp_uploads" / "retained"
    retained_dir.mkdir(parents=True, exist_ok=True)
    yield retained_dir
    if retained_dir.exists():
        shutil.rmtree(retained_dir)

def test_file_retention_when_enabled(tmp_path):
    settings = config_store.get_settings()
    settings.retained_inputs_max_mb = 100
    config_store.save_settings(settings)

    # Cria arquivo temporário falso
    fake_temp = tmp_path / "test_audio.mp3"
    fake_temp.write_bytes(b"dummy audio data")

    job_id = "test-job-123"
    retained_path = retain_input_file(job_id, str(fake_temp))
    
    assert retained_path is not None
    assert os.path.exists(retained_path)
    assert not fake_temp.exists() # Foi movido

    # Verifica os metadados de retenção seguros
    meta = get_retention_metadata(job_id, retained_path)
    assert meta["input_available"] is True
    assert meta["input_size_mb"] >= 0
    assert meta["input_retention_status"] == "available"

def test_no_retention_when_disabled(tmp_path):
    settings = config_store.get_settings()
    settings.retained_inputs_max_mb = 0 # Desativada
    config_store.save_settings(settings)

    fake_temp = tmp_path / "test_audio.mp3"
    fake_temp.write_bytes(b"dummy audio data")

    job_id = "test-job-456"
    retained_path = retain_input_file(job_id, str(fake_temp))

    assert retained_path is None
    assert not fake_temp.exists() # Foi excluído imediatamente

    meta = get_retention_metadata(job_id, retained_path)
    assert meta["input_available"] is False
    assert meta["input_retention_status"] == "retained_disabled"

def test_prune_retained_inputs_size_limit(tmp_path):
    settings = config_store.get_settings()
    settings.retained_inputs_max_mb = 1 # Limite de 1 MB
    config_store.save_settings(settings)

    from services.input_retention import RETAINED_DIR
    RETAINED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Cria dois arquivos que somam mais que 1 MB
    f1 = RETAINED_DIR / "job-1.mp3"
    f1.write_bytes(b"0" * (800 * 1024)) # 800 KB
    
    # Modifica a data para ordenar o f1 como mais antigo
    os.utime(f1, (time_sec := os.path.getmtime(f1) - 60, time_sec))

    f2 = RETAINED_DIR / "job-2.mp3"
    f2.write_bytes(b"0" * (800 * 1024)) # 800 KB (Total 1.6 MB)

    prune_retained_inputs()

    assert not f1.exists() # O mais antigo foi removido para respeitar o limite
    assert f2.exists()

def test_retry_endpoint_flow(client, tmp_path):
    # Setup de arquivo retido
    from services.input_retention import RETAINED_DIR
    RETAINED_DIR.mkdir(parents=True, exist_ok=True)
    job_id = "original-job-id"
    retained_file = RETAINED_DIR / "original-job-id.mp3"
    retained_file.write_bytes(b"audio content")

    # Registra o job no gerenciador
    job = job_manager.create(
        kind="transcribe_whisper",
        params={"model": "tiny", "whisper_prompt": "prompt sensivel"},
        input_ref=str(retained_file)
    )
    job_id = job.job_id
    
    # Renomeia o arquivo físico retido para bater com o UUID gerado
    retained_file.rename(RETAINED_DIR / f"{job_id}.mp3")
    retained_file = RETAINED_DIR / f"{job_id}.mp3"
    job.input_ref = str(retained_file)
    
    job_manager.finish(job_id, JobState.COMPLETED)

    # Executa retry via endpoint
    response = client.post(f"/api/jobs/{job_id}/retry")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "job_id" in data
    assert data["prompt_warning"] is True # Avisa sobre o prompt original omitido

    # Tenta retry para job inexistente
    assert client.post("/api/jobs/inexistente/retry").status_code == 404

    # Tenta retry para job não suportado
    job_down = job_manager.create(kind="model_download")
    assert client.post(f"/api/jobs/{job_down.job_id}/retry").status_code == 400

    # Tenta retry após arquivo ser excluído (410 Gone)
    retained_file.unlink()
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 410

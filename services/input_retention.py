import os
import shutil
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

from services.app_logging import record_app_event
from services.config_store import get_settings

logger = logging.getLogger("EscribaLocal.InputRetention")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = PROJECT_ROOT / "temp_uploads"
RETAINED_DIR = UPLOAD_DIR / "retained"

def get_retention_metadata(job_id: str, input_ref: Optional[str]) -> Dict[str, Any]:
    """Retorna os metadados de retenção seguros e sem expor paths absolutos."""
    if not input_ref:
        return {
            "input_available": False,
            "input_size_mb": 0.0,
            "input_retained_until": None,
            "input_retention_status": "retained_disabled"
        }
    
    settings = get_settings()
    if settings.retained_inputs_max_mb == 0:
        return {
            "input_available": False,
            "input_size_mb": 0.0,
            "input_retained_until": None,
            "input_retention_status": "retained_disabled"
        }

    # Verifica se o arquivo existe na pasta de retidos
    # A referência do histórico pode ser o arquivo original ou o retido, mas o ID do arquivo retido usa o job_id.
    ext = os.path.splitext(input_ref)[1] or ".mp3"
    retained_file = RETAINED_DIR / f"{job_id}{ext}"
    
    if retained_file.exists():
        stat = retained_file.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        
        # TTL estimado com base no tempo de modificação do arquivo + history_retention_days
        retained_until_ts = stat.st_mtime + (settings.history_retention_days * 24 * 3600)
        retained_until = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(retained_until_ts))
        
        return {
            "input_available": True,
            "input_size_mb": size_mb,
            "input_retained_until": retained_until,
            "input_retention_status": "available"
        }
    
    return {
        "input_available": False,
        "input_size_mb": 0.0,
        "input_retained_until": None,
        "input_retention_status": "expired"
    }

def retain_input_file(job_id: str, temp_file_path: str) -> Optional[str]:
    """Move o arquivo temporário para a pasta de retidos se a retenção estiver ativada."""
    settings = get_settings()
    if settings.retained_inputs_max_mb == 0:
        # Retenção desativada, exclui imediatamente
        cleanup_temp_file(temp_file_path)
        return None

    if not temp_file_path or not os.path.exists(temp_file_path):
        return None

    try:
        RETAINED_DIR.mkdir(parents=True, exist_ok=True)
        ext = os.path.splitext(temp_file_path)[1] or ".mp3"
        dest_path = RETAINED_DIR / f"{job_id}{ext}"
        
        shutil.move(temp_file_path, dest_path)
        
        record_app_event("input_retained", job_id=job_id, size_bytes=dest_path.stat().st_size)
        
        # Executa limpeza após reter novo arquivo
        prune_retained_inputs()
        
        return str(dest_path)
    except Exception as exc:
        logger.error(f"Erro ao reter o arquivo do job {job_id}: {exc}", exc_info=True)
        cleanup_temp_file(temp_file_path)
        return None

def prune_retained_inputs():
    """Remove os arquivos mais antigos baseado no limite global em MB e TTL."""
    if not RETAINED_DIR.exists():
        return

    settings = get_settings()
    max_bytes = settings.retained_inputs_max_mb * 1024 * 1024
    retention_seconds = settings.history_retention_days * 24 * 3600
    now = time.time()

    files = []
    for f in RETAINED_DIR.glob("*"):
        if f.is_file():
            stat = f.stat()
            files.append({
                "path": f,
                "mtime": stat.st_mtime,
                "size": stat.st_size
            })

    # 1. Prune por TTL
    for item in list(files):
        if now - item["mtime"] > retention_seconds:
            try:
                item["path"].unlink()
                record_app_event("input_removed_by_ttl", path=item["path"].name, age_days=round((now - item["mtime"]) / (24 * 3600), 1))
                files.remove(item)
            except OSError as exc:
                logger.warning(f"Falha ao deletar arquivo retido expirado: {exc}")

    # 2. Prune por tamanho limite (ordena por data de modificação: mais antigos primeiro)
    files.sort(key=lambda x: x["mtime"])
    
    total_size = sum(f["size"] for f in files)
    while total_size > max_bytes and files:
        oldest = files.pop(0)
        try:
            oldest["path"].unlink()
            total_size -= oldest["size"]
            record_app_event("input_removed_by_size_limit", path=oldest["path"].name, size_bytes=oldest["size"])
        except OSError as exc:
            logger.warning(f"Falha ao deletar arquivo retido por limite de tamanho: {exc}")

def cleanup_temp_file(path: str):
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Arquivo temporário removido: {path}")
        except Exception as cleanup_err:
            logger.warning(f"Não foi possível remover o arquivo temporário {path}: {cleanup_err}")

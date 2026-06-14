"""Gestor de modelos: catálogo, detecção de instalados, download e remoção.

O catálogo é a única fonte de verdade de repo_ids (incl. espelhos para repos
que a Microsoft já removeu do HuggingFace, como o VibeVoice-Large oficial).
Tamanhos de download aferidos via HfApi em 2026-06-10.

Progresso de download: em vez do antigo monkey-patch global de tqdm, uma
thread de polling mede o crescimento da pasta do repo no cache a cada 0.5s e
emite eventos com o MESMO shape que o frontend já consome:
{"type": "download_progress", "percent", "speed_mb", "current_mb",
 "total_mb", "filename"}.

Cancelamento: checado entre arquivos; um arquivo em andamento não pode ser
abortado pelo huggingface_hub e termina em segundo plano (fica no cache).
"""
import fnmatch
import os
import queue
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from services.app_logging import record_app_event, record_exception_event
from services.job_execution import run_blocking_job
from services.jobs import job_manager

WHISPER_ALLOW_PATTERNS = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)


class JobCancelled(Exception):
    """Sinaliza cancelamento cooperativo dentro de um worker de download."""


class ModelAlreadyInstalled(Exception):
    pass


class ModelLoadedInMemory(Exception):
    pass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    engine: str                      # "whisper" | "vibevoice_asr" | "tts_1_5b" | "tts_large" | "tts_realtime"
    repo_id: str
    display_name: str
    approx_download_mb: int          # aferido via HfApi (2026-06-10)
    cache_kind: str                  # "whisper_cache" | "hf_cache"
    mirror_repo_ids: Tuple[str, ...] = ()
    allow_patterns: Optional[Tuple[str, ...]] = None
    whisper_size: Optional[str] = None   # nome usado pelo faster-whisper ("tiny", "large-v3-turbo"...)
    approx_vram_mb: Dict[str, int] = field(default_factory=dict)  # estimativas por precisão
    recommended_for_6gb: bool = True
    notes: str = ""


MODEL_CATALOG: List[ModelSpec] = [
    ModelSpec(
        id="whisper-tiny", engine="whisper",
        repo_id="Systran/faster-whisper-tiny", display_name="Whisper Tiny",
        approx_download_mb=78, cache_kind="whisper_cache",
        allow_patterns=WHISPER_ALLOW_PATTERNS, whisper_size="tiny",
        approx_vram_mb={"float16": 500, "int8": 300},
        notes="O menor e mais rápido; qualidade limitada. Bom para testes.",
    ),
    ModelSpec(
        id="whisper-base", engine="whisper",
        repo_id="Systran/faster-whisper-base", display_name="Whisper Base",
        approx_download_mb=148, cache_kind="whisper_cache",
        allow_patterns=WHISPER_ALLOW_PATTERNS, whisper_size="base",
        approx_vram_mb={"float16": 700, "int8": 400},
        notes="Rápido em CPU; qualidade modesta.",
    ),
    ModelSpec(
        id="whisper-small", engine="whisper",
        repo_id="Systran/faster-whisper-small", display_name="Whisper Small",
        approx_download_mb=486, cache_kind="whisper_cache",
        allow_patterns=WHISPER_ALLOW_PATTERNS, whisper_size="small",
        approx_vram_mb={"float16": 1200, "int8": 700},
        notes="Bom equilíbrio para uso leve de VRAM.",
    ),
    ModelSpec(
        id="whisper-medium", engine="whisper",
        repo_id="Systran/faster-whisper-medium", display_name="Whisper Medium",
        approx_download_mb=1531, cache_kind="whisper_cache",
        allow_patterns=WHISPER_ALLOW_PATTERNS, whisper_size="medium",
        approx_vram_mb={"float16": 2500, "int8": 1500},
        notes="Qualidade alta; mais lento que o large-v3-turbo na maioria dos casos.",
    ),
    ModelSpec(
        id="whisper-large-v3", engine="whisper",
        repo_id="Systran/faster-whisper-large-v3", display_name="Whisper Large-v3",
        approx_download_mb=3091, cache_kind="whisper_cache",
        allow_patterns=WHISPER_ALLOW_PATTERNS, whisper_size="large-v3",
        approx_vram_mb={"float16": 3300, "int8_float16": 1800},
        notes="Máxima qualidade. Em float16 ocupa ~3.3GB de VRAM — apertado em 6GB junto com outras cargas.",
    ),
    ModelSpec(
        id="whisper-large-v3-turbo", engine="whisper",
        repo_id="mobiuslabsgmbh/faster-whisper-large-v3-turbo", display_name="Whisper Large-v3-Turbo",
        approx_download_mb=1622, cache_kind="whisper_cache",
        allow_patterns=WHISPER_ALLOW_PATTERNS, whisper_size="large-v3-turbo",
        approx_vram_mb={"float16": 1700, "int8_float16": 1000},
        notes="Qualidade próxima do large-v3 com fração do custo; recomendado para GPU de 6GB.",
    ),
    ModelSpec(
        id="vibevoice-asr", engine="vibevoice_asr",
        repo_id="microsoft/VibeVoice-ASR-HF", display_name="VibeVoice ASR (diarização)",
        approx_download_mb=16674, cache_kind="hf_cache",
        approx_vram_mb={"nf4": 4500},
        notes="Download de ~16.7GB. Carregado quantizado em 4-bit (NF4) na GPU; exige descarregar as demais engines.",
    ),
    ModelSpec(
        id="vibevoice-tts-1.5b", engine="tts_1_5b",
        repo_id="microsoft/VibeVoice-1.5B", display_name="VibeVoice TTS 1.5B",
        approx_download_mb=5408, cache_kind="hf_cache",
        approx_vram_mb={"bfloat16": 5400},
        notes="Após baixar, requer conversão única de formato "
              "(python scripts/convert_vibevoice_1_5b.py) — o fork local não lê o formato original. "
              "Em 6GB de VRAM o app tenta GPU e cai para CPU (lento, mas voz real).",
    ),
    ModelSpec(
        id="vibevoice-tts-large", engine="tts_large",
        # O repo oficial da Microsoft foi removido do HF; o espelho aoi-ot é o
        # repo primário por decisão do usuário.
        repo_id="aoi-ot/VibeVoice-Large", display_name="VibeVoice TTS Large (espelho)",
        approx_download_mb=18687, cache_kind="hf_cache",
        approx_vram_mb={"bfloat16": 19000},
        recommended_for_6gb=False,
        notes="NÃO recomendado neste hardware: 18.7GB de download e mais VRAM do que a disponível (offload massivo, minutos por frase).",
    ),
    ModelSpec(
        id="vibevoice-tts-rt-0.5b", engine="tts_realtime",
        repo_id="microsoft/VibeVoice-Realtime-0.5B", display_name="VibeVoice Realtime 0.5B",
        approx_download_mb=2035, cache_kind="hf_cache",
        approx_vram_mb={"bfloat16": 1500},
        notes="LIMITAÇÃO ATUAL: o checkpoint usa o model_type 'vibevoice_streaming', que nem o fork local "
              "nem o transformers 5.10.2 conhecem — a geração cai no fallback SAPI5 (voz do Windows). "
              "Suporte real exige atualizar o transformers (decisão explícita no painel de ambiente).",
    ),
]

_CATALOG_BY_ID = {spec.id: spec for spec in MODEL_CATALOG}
_WHISPER_BY_SIZE = {spec.whisper_size: spec for spec in MODEL_CATALOG if spec.whisper_size}


def get_spec(model_id: str) -> Optional[ModelSpec]:
    return _CATALOG_BY_ID.get(model_id)


def get_whisper_spec(whisper_size: str) -> Optional[ModelSpec]:
    return _WHISPER_BY_SIZE.get(whisper_size)


# ------------------------------------------------------------------ caches

def get_whisper_cache_dir() -> Path:
    # Mesmo diretório que o transcriber sempre usou.
    return Path(os.path.expanduser("~")) / ".cache" / "whisper-models"


def get_hf_cache_dir() -> Path:
    from huggingface_hub.constants import HF_HUB_CACHE

    return Path(HF_HUB_CACHE)


def _cache_base_for(spec: ModelSpec) -> Path:
    return get_whisper_cache_dir() if spec.cache_kind == "whisper_cache" else get_hf_cache_dir()


def _repo_dirname(repo_id: str) -> str:
    return "models--" + repo_id.replace("/", "--")


def _repo_dir_for(spec: ModelSpec, repo_id: Optional[str] = None) -> Path:
    return _cache_base_for(spec) / _repo_dirname(repo_id or spec.repo_id)


def _existing_repo_dir(spec: ModelSpec) -> Optional[Path]:
    """Pasta do repo no cache, considerando primário e espelhos."""
    for repo in (spec.repo_id, *spec.mirror_repo_ids):
        repo_dir = _repo_dir_for(spec, repo)
        if repo_dir.is_dir():
            return repo_dir
    return None


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            try:
                if not file_path.is_symlink():
                    total += file_path.stat().st_size
            except OSError:
                continue
    return total


_WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pt", ".onnx")


def get_install_status(spec: ModelSpec) -> Dict[str, Any]:
    repo_dir = _existing_repo_dir(spec)
    if repo_dir is None:
        return {"installed": False, "size_on_disk_mb": 0, "path": None}

    has_weights = False
    incomplete = False
    for root, _dirs, files in os.walk(repo_dir):
        for name in files:
            if name.endswith(".incomplete"):
                incomplete = True
            if name.endswith(_WEIGHT_SUFFIXES):
                has_weights = True
    size_mb = round(_dir_size_bytes(repo_dir) / 1e6, 1)
    return {
        "installed": has_weights and not incomplete,
        "size_on_disk_mb": size_mb,
        "path": str(repo_dir),
        "partial": (not has_weights or incomplete) and size_mb > 0,
    }


def _is_model_loaded(spec: ModelSpec) -> bool:
    """Consulta o resource_arbiter (Lote 4); sem ele, assume não carregado."""
    try:
        from services.resource_arbiter import arbiter
    except ImportError:
        return False
    for engine in arbiter.get_loaded():
        if spec.engine == "whisper":
            if engine["engine"] == "whisper" and engine.get("current_model") == spec.whisper_size:
                return True
        elif engine["engine"] == spec.engine:
            return True
    return False


def get_catalog_with_status() -> List[Dict[str, Any]]:
    catalog = []
    for spec in MODEL_CATALOG:
        status = get_install_status(spec)
        catalog.append({
            "id": spec.id,
            "engine": spec.engine,
            "repo_id": spec.repo_id,
            "mirror_repo_ids": list(spec.mirror_repo_ids),
            "display_name": spec.display_name,
            "approx_download_mb": spec.approx_download_mb,
            "approx_vram_mb": spec.approx_vram_mb,
            "recommended_for_6gb": spec.recommended_for_6gb,
            "notes": spec.notes,
            "installed": status["installed"],
            "partial": status.get("partial", False),
            "size_on_disk_mb": status["size_on_disk_mb"],
            "path": status["path"],
            "loaded": _is_model_loaded(spec),
        })
    return catalog


# ----------------------------------------------------------------- remoção

def delete_model(model_id: str) -> Dict[str, Any]:
    spec = get_spec(model_id)
    if spec is None:
        raise KeyError(model_id)
    repo_dir = _existing_repo_dir(spec)
    if repo_dir is None:
        raise FileNotFoundError(model_id)
    if _is_model_loaded(spec):
        raise ModelLoadedInMemory(
            f"{spec.display_name} está carregado na memória. Descarregue-o antes de remover do disco."
        )

    freed_mb = round(_dir_size_bytes(repo_dir) / 1e6, 1)
    shutil.rmtree(repo_dir)
    _clean_stale_locks(spec)
    record_app_event("model_deleted", model_id=model_id, freed_mb=freed_mb, path=str(repo_dir))
    return {"removed": model_id, "freed_mb": freed_mb}


def _clean_stale_locks(spec: ModelSpec) -> None:
    # Travas .lock órfãs (de downloads interrompidos) impedem novos downloads.
    locks_dir = _cache_base_for(spec) / ".locks"
    for repo in (spec.repo_id, *spec.mirror_repo_ids):
        lock_dir = locks_dir / _repo_dirname(repo)
        if lock_dir.is_dir():
            try:
                shutil.rmtree(lock_dir)
                record_app_event("model_stale_locks_removed", model_id=spec.id, path=str(lock_dir))
            except OSError as exc:
                record_app_event("model_stale_locks_error", model_id=spec.id, error_message=str(exc))


# ---------------------------------------------------------------- download

def _matches_patterns(filename: str, patterns: Optional[Tuple[str, ...]]) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def _resolve_repo_and_files(spec: ModelSpec) -> Tuple[str, int, List[str]]:
    """Tenta o repo primário e depois os espelhos; retorna (repo, bytes, arquivos)."""
    last_error: Optional[Exception] = None
    for repo in (spec.repo_id, *spec.mirror_repo_ids):
        try:
            from huggingface_hub import HfApi

            info = HfApi().model_info(repo, files_metadata=True)
            files = [s.rfilename for s in info.siblings if _matches_patterns(s.rfilename, spec.allow_patterns)]
            total_bytes = sum((s.size or 0) for s in info.siblings if _matches_patterns(s.rfilename, spec.allow_patterns))
            if repo != spec.repo_id:
                record_app_event("model_repo_mirror_used", model_id=spec.id, repo=repo, primary=spec.repo_id)
            return repo, total_bytes, files
        except Exception as exc:
            last_error = exc
            record_app_event("model_repo_unavailable", model_id=spec.id, repo=repo, error_message=str(exc))
    raise RuntimeError(
        f"Nenhum repositório acessível para {spec.display_name} "
        f"(tentados: {', '.join((spec.repo_id, *spec.mirror_repo_ids))}). Último erro: {last_error}"
    )


def _run_thread_with_outcome(
    target: Callable[[], None],
    *,
    thread_name: str,
    cancel_event: Optional[threading.Event] = None,
    cancelled_exception: type[BaseException] = JobCancelled,
    poll_timeout: float = 0.25,
) -> Dict[str, Any]:
    """Executa um worker em thread e consolida seu desfecho."""
    outcome: Dict[str, Any] = {}

    def worker():
        try:
            target()
            outcome["ok"] = True
        except cancelled_exception:
            outcome["cancelled"] = True
        except Exception as exc:
            outcome["error"] = exc

    thread = threading.Thread(target=worker, daemon=True, name=thread_name)
    thread.start()
    while thread.is_alive():
        if cancel_event is not None and cancel_event.is_set():
            raise cancelled_exception()
        thread.join(timeout=poll_timeout)
    return outcome


def _download_file_interruptible(repo_id: str, filename: str, cache_dir: Path, cancel_event: Optional[threading.Event]) -> None:
    """Baixa um arquivo; se cancelado no meio, abandona a thread (o arquivo em
    andamento termina em segundo plano e fica aproveitável no cache)."""
    def download_file() -> None:
        from huggingface_hub import hf_hub_download

        hf_hub_download(repo_id=repo_id, filename=filename, cache_dir=str(cache_dir))

    outcome = _run_thread_with_outcome(
        download_file,
        thread_name=f"dl-{filename}",
        cancel_event=cancel_event,
    )
    if "error" in outcome:
        raise outcome["error"]


class _ProgressPoller:
    """Mede o crescimento da pasta do repo e emite eventos download_progress."""

    def __init__(self, repo_dir: Path, total_bytes: int, emit: Callable[[Dict[str, Any]], None],
                 filename_label: str, interval: float = 0.5):
        self._repo_dir = repo_dir
        self._total = max(1, int(total_bytes))
        self._emit = emit
        self._label = filename_label
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="download-progress")
        # Baseline medido antes de a thread iniciar, para não perder o
        # crescimento que acontecer entre start() e o primeiro poll.
        self._baseline_size = self._current_size()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        last_size = self._baseline_size
        last_time = time.monotonic()
        while not self._stop.wait(self._interval):
            size = self._current_size()
            now = time.monotonic()
            if size == last_size:
                continue
            speed_mb = ((size - last_size) / 1e6) / max(now - last_time, 1e-6)
            last_size, last_time = size, now
            self._emit({
                "type": "download_progress",
                "percent": round(min(99.9, size / self._total * 100.0), 1),
                "speed_mb": round(max(0.0, speed_mb), 2),
                "current_mb": round(size / 1e6, 1),
                "total_mb": round(self._total / 1e6, 1),
                "filename": self._label,
            })

    def _current_size(self) -> int:
        if not self._repo_dir.exists():
            return 0
        return _dir_size_bytes(self._repo_dir)


def _download_all_files(spec: ModelSpec, emit: Callable[[Dict[str, Any]], None],
                        cancel_event: Optional[threading.Event]) -> Dict[str, Any]:
    """Baixa todos os arquivos do modelo emitindo progresso. Levanta JobCancelled."""
    _clean_stale_locks(spec)
    repo_used, total_bytes, files = _resolve_repo_and_files(spec)
    cache_dir = _cache_base_for(spec)
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_dir = _repo_dir_for(spec, repo_used)

    emit({
        "type": "status",
        "message": f"Baixando {spec.display_name}: {len(files)} arquivos, "
                   f"{round(total_bytes / 1e6)} MB de {repo_used}...",
    })

    poller = _ProgressPoller(repo_dir, total_bytes, emit, spec.display_name)
    poller.start()
    try:
        for index, filename in enumerate(files, 1):
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled()
            _download_file_interruptible(repo_used, filename, cache_dir, cancel_event)
    finally:
        poller.stop()

    status = get_install_status(spec)
    return {"repo_used": repo_used, "path": status["path"], "size_on_disk_mb": status["size_on_disk_mb"]}


def start_download_job(model_id: str) -> str:
    """Inicia o download como job em background; progresso via /api/jobs/{id}/events."""
    spec = get_spec(model_id)
    if spec is None:
        raise KeyError(model_id)
    if get_install_status(spec)["installed"]:
        raise ModelAlreadyInstalled(model_id)

    job = job_manager.create(
        kind="model_download",
        params={"model_id": spec.id, "repo_id": spec.repo_id, "approx_download_mb": spec.approx_download_mb},
    )

    def worker():
        def run_download(publish, cancel_event):
            return _download_all_files(
                spec,
                emit=publish,
                cancel_event=cancel_event,
            )
        def cancelled_event(_exc):
            return {
                "type": "cancelled",
                "message": "Download cancelado. Arquivos já baixados permanecem no cache; "
                           "um arquivo em andamento termina em segundo plano.",
            }

        def download_error(exc):
            record_exception_event("model_download_error", exc, model_id=spec.id)

        run_blocking_job(
            job,
            run_download,
            cancelled_exceptions=(JobCancelled,),
            success_event_factory=lambda summary: {"type": "done", "result": summary},
            cancelled_event_factory=cancelled_event,
            result_summary_factory=lambda summary: summary,
            on_exception=download_error,
        )

    threading.Thread(target=worker, daemon=True, name=f"download-{spec.id}").start()
    record_app_event("model_download_started", model_id=spec.id, job_id=job.job_id)
    return job.job_id


# ------------------------------------------- integração com o transcriber

def ensure_whisper_model_events(model_name: str, cancel_event: Optional[threading.Event] = None
                                ) -> Generator[Dict[str, Any], None, None]:
    """Garante o modelo Whisper no cache, emitindo os mesmos eventos SSE que o
    fluxo de transcrição sempre emitiu durante downloads.

    Modelos fora do catálogo passam direto (o faster-whisper resolve sozinho,
    preservando o comportamento antigo para nomes customizados).
    """
    spec = get_whisper_spec(model_name)
    if spec is None or get_install_status(spec)["installed"]:
        return

    events: "queue.Queue" = queue.Queue()
    outcome = _run_thread_with_outcome(
        lambda: _download_all_files(spec, emit=events.put, cancel_event=cancel_event),
        thread_name=f"ensure-{spec.id}",
        cancel_event=cancel_event,
        poll_timeout=0.2,
    )

    while not events.empty():
        try:
            yield events.get(timeout=0.2)
        except queue.Empty:
            continue

    if outcome.get("cancelled") or (cancel_event is not None and cancel_event.is_set()):
        yield {
            "type": "cancelled",
            "message": "Tarefa cancelada durante o download do modelo. "
                       "Arquivos já baixados permanecem no cache.",
        }
        return
    if "error" in outcome:
        raise outcome["error"]

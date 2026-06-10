"""Gestão de jobs: estados explícitos, cancelamento cooperativo e histórico.

Cada trabalho pesado (transcrição, e futuramente downloads/instalações)
ganha um ``Job`` com ``job_id``, estado e um ``threading.Event`` de
cancelamento que os geradores síncronos checam cooperativamente.

Persistência: uma linha JSONL por transição de estado em ``data/history.jsonl``
(append-only, com lock). Parâmetros passam por ``_sanitize_for_log`` antes de
serem guardados — conteúdo de prompts/textos nunca é persistido íntegro.
"""
import json
import queue
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.app_logging import _sanitize_for_log, record_app_event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_PATH = DATA_DIR / "history.jsonl"

# Quantidade de jobs terminados mantidos em memória para consulta rápida.
MAX_FINISHED_JOBS_IN_MEMORY = 200


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}


@dataclass
class Job:
    job_id: str
    kind: str
    params: Dict[str, Any] = field(default_factory=dict)
    state: JobState = JobState.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    result_summary: Dict[str, Any] = field(default_factory=dict)
    input_ref: Optional[str] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    subscribers: List["queue.Queue"] = field(default_factory=list)
    gpu_held: bool = False

    def snapshot(self) -> Dict[str, Any]:
        duration_ms = None
        if self.started_at is not None:
            end = self.finished_at if self.finished_at is not None else time.time()
            duration_ms = round((end - self.started_at) * 1000, 1)
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "state": self.state.value,
            "params": self.params,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": duration_ms,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "result_summary": self.result_summary,
            "input_ref": self.input_ref,
            "cancel_requested": self.cancel_event.is_set(),
        }


class JobManager:
    """Registro de jobs em memória + histórico JSONL.

    Os jobs de GPU são serializados por um semáforo (1 slot): o servidor é
    single-GPU e duas inferências pesadas simultâneas estouram os 6GB de VRAM.
    """

    def __init__(self, history_path: Path = HISTORY_PATH):
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._lock = threading.RLock()
        self._history_lock = threading.Lock()
        self._history_path = Path(history_path)
        self._gpu_semaphore = threading.BoundedSemaphore(1)

    # ------------------------------------------------------------- ciclo

    def create(
        self,
        kind: str,
        params: Optional[Dict[str, Any]] = None,
        input_ref: Optional[str] = None,
    ) -> Job:
        import uuid

        job = Job(
            job_id=str(uuid.uuid4()),
            kind=kind,
            params=_sanitize_for_log(dict(params or {})),
            input_ref=input_ref,
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._prune_finished()
        self._persist(job)
        record_app_event("job_created", job_id=job.job_id, kind=kind)
        return job

    def start(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state in TERMINAL_STATES:
                return
            job.state = JobState.RUNNING
            job.started_at = time.time()
        self._persist(job)
        record_app_event("job_started", job_id=job_id, kind=job.kind)
        self._notify_subscribers(job, {"type": "job_state", "job_id": job_id, "state": job.state.value})

    def publish(self, job_id: str, event: Dict[str, Any]) -> None:
        """Atualiza progresso/mensagem a partir de um evento do gerador e
        repassa o evento aos assinantes (re-attach via /api/jobs/{id}/events)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            event_type = event.get("type")
            if event_type in ("progress", "download_progress") and "progress" in event:
                job.progress = float(event["progress"])
            elif event_type == "download_progress" and "percent" in event:
                job.progress = float(event["percent"])
            elif event_type == "status" and event.get("message"):
                job.message = str(event["message"])
            elif event_type == "done":
                job.progress = 100.0
        self._notify_subscribers(job, event)

    def finish(
        self,
        job_id: str,
        state: JobState,
        error: Optional[str] = None,
        result_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state in TERMINAL_STATES:
                return
            job.state = state
            job.finished_at = time.time()
            job.error = error
            if result_summary:
                job.result_summary = _sanitize_for_log(result_summary)
        self._persist(job)
        record_app_event(
            "job_finished",
            job_id=job_id,
            kind=job.kind,
            state=state.value,
            error=error,
            duration_ms=job.snapshot()["duration_ms"],
        )
        self._notify_subscribers(
            job,
            {"type": "job_state", "job_id": job_id, "state": state.value, "error": error},
            close=True,
        )

    def cancel(self, job_id: str, reason: str = "solicitado pelo usuário") -> Optional[Dict[str, Any]]:
        """Sinaliza cancelamento cooperativo. Jobs ainda na fila terminam na
        hora; jobs em execução mudam para CANCELLED quando o worker confirma."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            already_terminal = job.state in TERMINAL_STATES
            if not already_terminal:
                job.cancel_event.set()
                job.message = f"Cancelamento solicitado ({reason})"
        if job is not None and not already_terminal:
            record_app_event("job_cancel_requested", job_id=job_id, kind=job.kind, reason=reason)
            if job.state == JobState.QUEUED:
                self.finish(job_id, JobState.CANCELLED)
        return self.get_snapshot(job_id)

    # ------------------------------------------------------------ fila GPU

    def try_acquire_gpu(self, job_id: str, timeout: float = 0.5) -> bool:
        acquired = self._gpu_semaphore.acquire(timeout=timeout)
        if acquired:
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    job.gpu_held = True
        return acquired

    def release_gpu(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or not job.gpu_held:
                return
            job.gpu_held = False
        self._gpu_semaphore.release()

    # ----------------------------------------------------------- consultas

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_snapshot(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job is not None else None

    def list(self, state: Optional[str] = None, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            snapshots = [job.snapshot() for job in self._jobs.values()]
        if state:
            snapshots = [s for s in snapshots if s["state"] == state]
        if kind:
            snapshots = [s for s in snapshots if s["kind"] == kind]
        snapshots.sort(key=lambda s: s["created_at"], reverse=True)
        return snapshots

    def subscribe(self, job_id: str) -> Optional["queue.Queue"]:
        """Retorna uma fila de eventos do job, ou None se ele já terminou."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state in TERMINAL_STATES:
                return None
            subscriber: "queue.Queue" = queue.Queue()
            job.subscribers.append(subscriber)
            return subscriber

    def unsubscribe(self, job_id: str, subscriber: "queue.Queue") -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None and subscriber in job.subscribers:
                job.subscribers.remove(subscriber)

    def history(
        self,
        limit: int = 50,
        offset: int = 0,
        kind: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lê o histórico consolidando por job_id (última transição vence)."""
        entries: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        with self._history_lock:
            if not self._history_path.exists():
                return []
            with self._history_path.open("r", encoding="utf-8", errors="replace") as history_file:
                for line in history_file:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    job_id = entry.get("job_id")
                    if job_id:
                        entries[job_id] = entry
        consolidated = list(entries.values())
        if kind:
            consolidated = [e for e in consolidated if e.get("kind") == kind]
        if state:
            consolidated = [e for e in consolidated if e.get("state") == state]
        consolidated.sort(key=lambda e: e.get("created_at") or 0, reverse=True)
        return consolidated[offset:offset + limit]

    # ------------------------------------------------------------ internos

    def _notify_subscribers(self, job: Optional[Job], event: Dict[str, Any], close: bool = False) -> None:
        if job is None:
            return
        with self._lock:
            subscribers = list(job.subscribers)
            if close:
                job.subscribers.clear()
        for subscriber in subscribers:
            subscriber.put(event)
            if close:
                subscriber.put(None)

    def _persist(self, job: Job) -> None:
        snapshot = job.snapshot()
        snapshot["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
        snapshot.pop("cancel_requested", None)
        try:
            with self._history_lock:
                self._history_path.parent.mkdir(parents=True, exist_ok=True)
                with self._history_path.open("a", encoding="utf-8") as history_file:
                    history_file.write(json.dumps(snapshot, ensure_ascii=False, default=str) + "\n")
        except Exception as exc:
            # Histórico nunca pode derrubar o fluxo principal.
            record_app_event("job_history_write_error", job_id=job.job_id, error_message=str(exc))

    def _prune_finished(self) -> None:
        finished_ids = [
            job_id for job_id, job in self._jobs.items() if job.state in TERMINAL_STATES
        ]
        excess = len(finished_ids) - MAX_FINISHED_JOBS_IN_MEMORY
        for job_id in finished_ids[:max(0, excess)]:
            self._jobs.pop(job_id, None)


job_manager = JobManager()

"""Rotas de jobs: listagem, snapshot, cancelamento, re-attach de eventos e histórico."""
import asyncio
import json
import queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.jobs import TERMINAL_STATES, job_manager

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs")
async def list_jobs(state: str | None = None, kind: str | None = None):
    return {"jobs": job_manager.list(state=state, kind=kind)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    snapshot = job_manager.get_snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return snapshot


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if job.state in TERMINAL_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Job já finalizado com estado '{job.state.value}'.",
        )
    snapshot = job_manager.cancel(job_id)
    return snapshot


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    """Re-attach: stream SSE dos eventos de um job em andamento.

    Sempre envia primeiro um snapshot do estado atual; se o job já terminou,
    encerra em seguida.
    """
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    subscriber = job_manager.subscribe(job_id)

    async def event_stream():
        loop = asyncio.get_running_loop()
        snapshot = job_manager.get_snapshot(job_id)
        yield f"data: {json.dumps({'type': 'job_snapshot', 'job': snapshot})}\n\n"
        if subscriber is None:
            return
        try:
            while True:
                try:
                    event = await loop.run_in_executor(None, subscriber.get, True, 0.5)
                except queue.Empty:
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            job_manager.unsubscribe(job_id, subscriber)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history")
async def get_history(limit: int = 50, offset: int = 0, kind: str | None = None, state: str | None = None):
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    return {"history": job_manager.history(limit=limit, offset=offset, kind=kind, state=state)}

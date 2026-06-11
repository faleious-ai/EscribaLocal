"""Streaming de logs em tempo real (tail -f via SSE)."""
import asyncio
import json
from pathlib import Path
from typing import List, Tuple

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from services.app_logging import APP_LOG_PATH, EVENT_LOG_PATH, read_recent_log_lines

router = APIRouter(prefix="/api", tags=["logs"])

POLL_INTERVAL_SECONDS = 0.5
HEARTBEAT_SECONDS = 15.0


def read_new_lines(path: Path, offset: int, partial: bytes) -> Tuple[List[str], int, bytes]:
    """Lê linhas completas novas a partir de ``offset`` (em bytes).

    Detecta rotação do RotatingFileHandler pelo encolhimento do arquivo
    (size < offset) e recomeça do zero. A última linha sem ``\n`` fica em
    ``partial`` até completar.
    """
    if not path.exists():
        return [], 0, b""
    size = path.stat().st_size
    if size < offset:
        offset = 0
        partial = b""
    if size == offset:
        return [], offset, partial

    with path.open("rb") as log_file:
        log_file.seek(offset)
        chunk = log_file.read()
        new_offset = log_file.tell()

    data = partial + chunk
    raw_lines = data.split(b"\n")
    partial = raw_lines.pop()
    lines = [
        raw.decode("utf-8", errors="replace").rstrip("\r")
        for raw in raw_lines
        if raw.strip()
    ]
    return lines, new_offset, partial


@router.get("/logs/stream")
async def stream_logs(kind: str = "events", tail_lines: int = 50, follow: bool = True):
    """SSE com as últimas linhas do log e, com follow=true, acompanhamento
    contínuo (cada cliente mantém seu próprio offset)."""
    log_path = EVENT_LOG_PATH if kind == "events" else APP_LOG_PATH
    initial_tail = max(0, min(int(tail_lines), 500))

    async def event_stream():
        if initial_tail:
            for line in read_recent_log_lines(log_path, max_lines=initial_tail):
                yield f"data: {json.dumps({'type': 'log_line', 'line': line.rstrip()})}\n\n"
        if not follow:
            return

        offset = log_path.stat().st_size if log_path.exists() else 0
        partial = b""
        silent_for = 0.0
        while True:
            lines, offset, partial = read_new_lines(log_path, offset, partial)
            if lines:
                silent_for = 0.0
                for line in lines:
                    yield f"data: {json.dumps({'type': 'log_line', 'line': line})}\n\n"
            else:
                silent_for += POLL_INTERVAL_SECONDS
                if silent_for >= HEARTBEAT_SECONDS:
                    silent_for = 0.0
                    yield ": ping\n\n"
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

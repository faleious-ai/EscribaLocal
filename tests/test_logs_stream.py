"""Lote 9 — testes do streaming de logs (tail SSE com rotação)."""
from pathlib import Path

from routers.logs_routes import read_new_lines
from services.app_logging import record_app_event
from tests.conftest import parse_sse_payloads


# ------------------------------------------------------------ read_new_lines

def test_read_new_lines_progression(tmp_path):
    log = tmp_path / "teste.log"
    log.write_bytes(b"linha um\nlinha dois\n")

    lines, offset, partial = read_new_lines(log, 0, b"")
    assert lines == ["linha um", "linha dois"]
    assert partial == b""

    # Sem mudanças: nada novo.
    lines, offset, partial = read_new_lines(log, offset, partial)
    assert lines == []

    # Append: só as novas.
    with log.open("ab") as f:
        f.write(b"linha tres\n")
    lines, offset, partial = read_new_lines(log, offset, partial)
    assert lines == ["linha tres"]


def test_read_new_lines_partial_line(tmp_path):
    log = tmp_path / "teste.log"
    log.write_bytes(b"completa\nincompleta sem newline")

    lines, offset, partial = read_new_lines(log, 0, b"")
    assert lines == ["completa"]
    assert partial == b"incompleta sem newline"

    with log.open("ab") as f:
        f.write(b" agora completa\n")
    lines, offset, partial = read_new_lines(log, offset, partial)
    assert lines == ["incompleta sem newline agora completa"]
    assert partial == b""


def test_read_new_lines_detects_rotation(tmp_path):
    log = tmp_path / "teste.log"
    log.write_bytes(b"antes da rotacao um\nantes da rotacao dois\n")
    _lines, offset, partial = read_new_lines(log, 0, b"")

    # Rotação: o arquivo encolhe (handler recomeça do zero).
    log.write_bytes(b"depois da rotacao\n")
    lines, offset, partial = read_new_lines(log, offset, partial)
    assert lines == ["depois da rotacao"]
    assert partial == b""


def test_read_new_lines_missing_file(tmp_path):
    lines, offset, partial = read_new_lines(tmp_path / "nao-existe.log", 100, b"resto")
    assert lines == [] and offset == 0 and partial == b""


# -------------------------------------------------------------------- rota

def test_stream_endpoint_returns_recent_event(client):
    record_app_event("logs_stream_smoke_marker", origem="teste-automatizado")

    response = client.get("/api/logs/stream", params={"kind": "events", "follow": "false", "tail_lines": 200})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    payloads = parse_sse_payloads(response.text)
    assert payloads, "nenhuma linha de log no stream"
    assert all(p["type"] == "log_line" for p in payloads)
    assert any("logs_stream_smoke_marker" in p["line"] for p in payloads)


def test_stream_endpoint_app_log(client):
    response = client.get("/api/logs/stream", params={"kind": "app", "follow": "false", "tail_lines": 50})
    assert response.status_code == 200
    payloads = parse_sse_payloads(response.text)
    assert payloads

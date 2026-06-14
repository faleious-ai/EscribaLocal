import json
import logging
import os
import platform
import sys
import threading
import time
import traceback
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logs"
APP_LOG_PATH = LOG_DIR / "escribalocal.log"
EVENT_LOG_PATH = LOG_DIR / "events.jsonl"

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if isinstance(getattr(record, "event_data", None), dict):
            payload.update(_sanitize_for_log(record.event_data))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_app_logging() -> None:
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    plain_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | req=%(request_id)s | %(message)s"
    )
    event_formatter = JsonLineFormatter()
    request_filter = RequestIdFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(plain_formatter)
    console_handler.addFilter(request_filter)

    file_handler = RotatingFileHandler(
        APP_LOG_PATH,
        maxBytes=8 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(plain_formatter)
    file_handler.addFilter(request_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [console_handler, file_handler]

    event_handler = RotatingFileHandler(
        EVENT_LOG_PATH,
        maxBytes=8 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    event_handler.setLevel(logging.INFO)
    event_handler.setFormatter(event_formatter)
    event_handler.addFilter(request_filter)

    event_logger = logging.getLogger("EscribaLocal.Events")
    event_logger.setLevel(logging.INFO)
    event_logger.handlers = [event_handler]
    event_logger.propagate = False

    sys.excepthook = _handle_unhandled_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = _handle_thread_exception

    _configured = True
    record_app_event(
        "logging_configured",
        log_dir=str(LOG_DIR),
        python=sys.version.split()[0],
        platform=platform.platform(),
    )


def set_request_id(request_id: str):
    return request_id_var.set(request_id)


def reset_request_id(token) -> None:
    request_id_var.reset(token)


def record_app_event(event_type: str, **fields: Any) -> None:
    configure_app_logging()
    safe_fields = _sanitize_for_log(fields)
    safe_fields["event_type"] = event_type
    logging.getLogger("EscribaLocal.Events").info(event_type, extra={"event_data": safe_fields})


def record_exception_event(event_type: str, exc: BaseException, **fields: Any) -> None:
    record_app_event(
        event_type,
        error_type=exc.__class__.__name__,
        error_message=str(exc),
        stack=traceback.format_exception(type(exc), exc, exc.__traceback__),
        **fields,
    )


def get_log_paths() -> Dict[str, str]:
    configure_app_logging()
    return {
        "directory": str(LOG_DIR),
        "app_log": str(APP_LOG_PATH),
        "event_log": str(EVENT_LOG_PATH),
    }


def read_recent_log_lines(path: Path, max_lines: int = 250) -> Iterable[str]:
    if not path.exists():
        return []
    max_lines = max(1, min(int(max_lines), 2000))
    with path.open("r", encoding="utf-8", errors="replace") as log_file:
        lines = log_file.readlines()
    return lines[-max_lines:]


def _handle_unhandled_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("EscribaLocal.Unhandled").critical(
        "Exceção não tratada no processo principal",
        exc_info=(exc_type, exc_value, exc_traceback),
    )
    record_app_event(
        "unhandled_exception",
        error_type=exc_type.__name__,
        error_message=str(exc_value),
        stack=traceback.format_exception(exc_type, exc_value, exc_traceback),
    )


def _handle_thread_exception(args) -> None:
    logging.getLogger("EscribaLocal.Unhandled").critical(
        "Exceção não tratada em thread",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )
    record_app_event(
        "unhandled_thread_exception",
        thread_name=getattr(args.thread, "name", None),
        error_type=args.exc_type.__name__,
        error_message=str(args.exc_value),
        stack=traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback),
    )


def _sanitize_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            lowered = key_str.lower()
            if any(secret in lowered for secret in ("token", "password", "secret", "authorization", "cookie")):
                sanitized[key_str] = "[redacted]"
            elif any(content in lowered for content in ("text", "transcript", "audio", "prompt")):
                sanitized[key_str] = _summarize_value(item)
            else:
                sanitized[key_str] = _sanitize_for_log(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_log(item) for item in list(value)[:50]]
    return value


def _summarize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (list, tuple, dict)):
        return {
            "type": type(value).__name__,
            "size": len(value),
        }
    text = str(value)
    return {
        "type": type(value).__name__,
        "length": len(text),
    }

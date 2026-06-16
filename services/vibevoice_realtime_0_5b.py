import gc
import io
import json
import logging
import os
import shlex
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, Generator, List

import numpy as np
import scipy.io.wavfile as wavfile
from services.app_logging import record_app_event

logger = logging.getLogger("EscribaLocal.VibeVoiceRealtime05B")

_model_id = "microsoft/VibeVoice-Realtime-0.5B"
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_WORKER_PATH = os.path.join(_PROJECT_ROOT, "workers", "vibevoice_realtime_worker.py")
_WORKER_PROTOCOL_VERSION = 1


class RealtimeUnavailableError(RuntimeError):
    """Realtime 0.5B ainda não tem geração nativa disponível neste ambiente."""

    def __init__(self, message: str, code: str = "tts_realtime_unavailable", engine_key: str = "realtime_0_5b"):
        super().__init__(message)
        self.code = code
        self.engine_key = engine_key

    def to_payload(self) -> Dict[str, Any]:
        return {
            "type": "error",
            "code": self.code,
            "engine_key": self.engine_key,
            "message": str(self),
        }


def _engine_metadata(engine_key: str, engine_label: str, fallback: bool, worker: Dict[str, Any] | None = None) -> Dict[str, Any]:
    metadata = {
        "engine_key": engine_key,
        "engine_label": engine_label,
        "fallback": fallback,
    }
    if worker is not None:
        metadata["worker"] = worker
    return metadata


def _resolve_worker_command() -> List[str]:
    raw = os.environ.get("ESCRIBA_REALTIME_WORKER_CMD", "").strip()
    if raw:
        return shlex.split(raw, posix=False)
    return [sys.executable, _DEFAULT_WORKER_PATH]


def _build_worker_request(
    op: str,
    text: str,
    speaker_id: str,
    temperature: float,
    top_p: float,
    top_k: int,
    repetition_penalty: float,
    speed: float,
) -> Dict[str, Any]:
    return {
        "op": op,
        "protocol_version": _WORKER_PROTOCOL_VERSION,
        "request_id": str(uuid.uuid4()),
        "transport": "subprocess",
        "model_id": _model_id,
        "text": text,
        "speaker_id": speaker_id,
        "params": {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
            "speed": speed,
        },
    }


def _invoke_realtime_worker(request: Dict[str, Any]) -> Dict[str, Any]:
    command = _resolve_worker_command()
    started = time.perf_counter()
    record_app_event(
        "tts_realtime_worker_invoked",
        requested_model="realtime_0_5b",
        worker_op=request.get("op"),
        worker_transport="subprocess",
        worker_protocol_version=request.get("protocol_version"),
        request_id=request.get("request_id"),
        command=command,
    )
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
            cwd=_PROJECT_ROOT,
            check=False,
        )
    except FileNotFoundError as exc:
        record_app_event(
            "tts_realtime_worker_failed",
            requested_model="realtime_0_5b",
            worker_op=request.get("op"),
            worker_transport="subprocess",
            worker_protocol_version=request.get("protocol_version"),
            request_id=request.get("request_id"),
            failure_stage="spawn",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        record_app_event(
            "tts_realtime_worker_failed",
            requested_model="realtime_0_5b",
            worker_op=request.get("op"),
            worker_transport="subprocess",
            worker_protocol_version=request.get("protocol_version"),
            request_id=request.get("request_id"),
            failure_stage="timeout",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao respondeu a tempo."
        ) from exc

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        logger.error("Worker realtime retornou JSON invalido: %s", stdout[:400])
        record_app_event(
            "tts_realtime_worker_failed",
            requested_model="realtime_0_5b",
            worker_op=request.get("op"),
            worker_transport="subprocess",
            worker_protocol_version=request.get("protocol_version"),
            request_id=request.get("request_id"),
            failure_stage="invalid-json",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado retornou resposta invalida."
        ) from exc

    if completed.returncode != 0:
        message = (
            payload.get("error", {}).get("message")
            or stderr
            or "worker isolado falhou sem detalhes."
        )
        record_app_event(
            "tts_realtime_worker_failed",
            requested_model="realtime_0_5b",
            worker_op=request.get("op"),
            worker_transport="subprocess",
            worker_protocol_version=request.get("protocol_version"),
            request_id=request.get("request_id"),
            returncode=completed.returncode,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        raise RealtimeUnavailableError(f"VibeVoice Realtime 0.5B indisponivel: {message}")

    native_probe = (payload.get("worker") or {}).get("native_probe") or {}
    deep_probe = native_probe.get("deep_probe") or {}
    breakdown = deep_probe.get("breakdown") or {}

    telemetry_fields = {
        "requested_model": "realtime_0_5b",
        "worker_op": request.get("op"),
        "worker_transport": (payload.get("worker") or {}).get("transport", "subprocess"),
        "worker_protocol_version": (payload.get("worker") or {}).get("protocol_version"),
        "request_id": request.get("request_id"),
        "worker_status": (payload.get("worker") or {}).get("status"),
        "worker_native_probe_status": native_probe.get("status"),
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }

    if deep_probe:
        telemetry_fields.update({
            "deep_probe_enabled": True,
            "deep_probe_failed_step": deep_probe.get("failed_step"),
            "deep_probe_error_type": deep_probe.get("error_type"),
            "deep_probe_imports_ok": breakdown.get("imports_ok"),
            "deep_probe_config_ok": breakdown.get("config_ok"),
            "deep_probe_processor_ok": breakdown.get("processor_ok"),
            "deep_probe_tokenizer_ok": breakdown.get("tokenizer_ok"),
            "deep_probe_feature_extractor_ok": breakdown.get("feature_extractor_ok"),
            "deep_probe_model_class_ok": breakdown.get("model_class_ok"),
        })
        if native_probe.get("model_class_name"):
            telemetry_fields["model_class_name"] = native_probe.get("model_class_name")
    else:
        telemetry_fields["deep_probe_enabled"] = False

    record_app_event("tts_realtime_worker_completed", **telemetry_fields)
    return payload


def get_realtime_worker_status() -> Dict[str, Any]:
    request = _build_worker_request(
        op="healthcheck",
        text="",
        speaker_id="speaker_1",
        temperature=0.5,
        top_p=0.9,
        top_k=40,
        repetition_penalty=1.1,
        speed=1.0,
    )
    try:
        payload = _invoke_realtime_worker(request)
    except RealtimeUnavailableError as exc:
        return {
            "ok": False,
            "worker": {
                "transport": "subprocess",
                "protocol_version": request.get("protocol_version"),
                "status": "unavailable",
            },
            "error": exc.to_payload(),
        }
    return payload


def _decode_worker_audio(payload: Dict[str, Any]) -> bytes:
    worker = payload.get("worker") or {}
    if worker.get("status") == "synthetic-smoke" or (worker.get("smoke") or {}).get("synthetic"):
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado retornou audio sintetico, nao PCM/WAV nativo real."
        )
    audio = payload.get("audio") or {}
    if audio.get("format") != "pcm_s16le":
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao entregou audio PCM valido."
        )
    data_hex = audio.get("data_hex", "")
    if not data_hex:
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao entregou audio nativo."
        )
    try:
        return bytes.fromhex(data_hex)
    except ValueError as exc:
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado retornou bytes de audio invalidos."
        ) from exc


def generate_voice_stream_0_5b(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0,
    status_callback=None,
) -> Generator[bytes, None, None]:
    request = _build_worker_request(
        op="synthesize_stream",
        text=text,
        speaker_id=speaker_id,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        speed=speed,
    )
    payload = _invoke_realtime_worker(request)

    if not payload.get("ok"):
        error = payload.get("error") or {}
        raise RealtimeUnavailableError(
            error.get("message", "worker isolado sinalizou indisponibilidade."),
            code=error.get("code", "tts_realtime_unavailable"),
            engine_key=(payload.get("engine") or {}).get("engine_key", "realtime_0_5b"),
        )

    engine = payload.get("engine") or {}
    engine_key = engine.get("engine_key")
    if not engine_key:
        raise RealtimeUnavailableError(
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao declarou engine_key."
        )
    if status_callback:
        status_callback(_engine_metadata(
            engine_key,
            engine.get("engine_label", "VibeVoice-Realtime-0.5B"),
            bool(engine.get("fallback", False)),
            worker=payload.get("worker"),
        ))

    pcm_bytes = _decode_worker_audio(payload)
    chunk_size = 8192
    for i in range(0, len(pcm_bytes), chunk_size):
        yield pcm_bytes[i:i + chunk_size]


def generate_voice_realtime_wav(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0,
) -> bytes:
    return generate_voice_realtime_wav_with_metadata(
        text=text,
        speaker_id=speaker_id,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        speed=speed,
    )["wav_bytes"]


def generate_voice_realtime_wav_with_metadata(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0,
) -> Dict[str, Any]:
    engine_info: Dict[str, Any] = {}

    def capture_engine(info: Dict[str, Any]):
        engine_info.update(info)

    pcm_bytes = b"".join(generate_voice_stream_0_5b(
        text=text,
        speaker_id=speaker_id,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        speed=speed,
        status_callback=capture_engine,
    ))
    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
    wav_io = io.BytesIO()
    wavfile.write(wav_io, 24000, audio)
    return {
        "wav_bytes": wav_io.getvalue(),
        "engine_key": engine_info.get("engine_key", "realtime_0_5b"),
        "engine_label": engine_info.get("engine_label", "VibeVoice-Realtime-0.5B"),
        "fallback": bool(engine_info.get("fallback", False)),
        "worker": engine_info.get("worker"),
    }


def unload_realtime_model():
    gc.collect()


from services.resource_arbiter import arbiter as _arbiter

_arbiter.register_engine(
    engine="tts_realtime",
    label="VibeVoice Realtime 0.5B",
    is_loaded=lambda: False,
    unload=unload_realtime_model,
    est_vram_mb=lambda: 1500.0,
    current_model=lambda: _model_id,
)

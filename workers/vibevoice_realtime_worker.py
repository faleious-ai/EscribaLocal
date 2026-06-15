import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _native_runtime_enabled() -> bool:
    return os.environ.get("ESCRIBA_REALTIME_NATIVE_ENABLE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _synthetic_smoke_enabled() -> bool:
    return os.environ.get("ESCRIBA_REALTIME_SYNTHETIC_SMOKE_ENABLE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _deep_probe_enabled() -> bool:
    return os.environ.get("ESCRIBA_REALTIME_DEEP_PROBE_ENABLE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _get_model_status(model_id: str) -> Dict[str, Any]:
    try:
        from services import model_manager
    except Exception as exc:
        return {
            "installed": False,
            "path": None,
            "status": "metadata-unavailable",
            "reason": "model_manager_import_failed",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "model_id": model_id,
        }

    spec = next((item for item in model_manager.MODEL_CATALOG if item.repo_id == model_id), None)
    if spec is None:
        return {
            "installed": False,
            "path": None,
            "status": "unknown-model",
            "reason": "model_spec_missing",
            "model_id": model_id,
        }

    status = model_manager.get_install_status(spec)
    return {
        "installed": bool(status.get("installed")),
        "path": status.get("path"),
        "size_on_disk_mb": status.get("size_on_disk_mb"),
        "partial": bool(status.get("partial", False)),
        "status": "installed" if status.get("installed") else "missing",
        "model_id": model_id,
    }


def _probe_native_stack(model_status: Dict[str, Any]) -> Dict[str, Any]:
    if not _native_runtime_enabled():
        return {
            "ok": False,
            "status": "disabled",
            "reason": "native_runtime_disabled",
            "message": "Probing nativo desligado por padrao neste ambiente.",
        }

    if not model_status.get("installed") or not model_status.get("path"):
        return {
            "ok": False,
            "status": "model-missing",
            "reason": "model_not_installed",
            "message": "Checkpoint Realtime 0.5B ausente no cache local.",
        }

    started = time.perf_counter()
    try:
        from services.runtime_patches import apply_runtime_patches
        from services.transformers_loader import use_standard_transformers
    except Exception as exc:
        return {
            "ok": False,
            "status": "runtime-import-failed",
            "reason": "runtime_setup_failed",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }

    try:
        apply_runtime_patches()
        with use_standard_transformers():
            from transformers import AutoConfig, AutoProcessor

            config = AutoConfig.from_pretrained(
                model_status["path"],
                local_files_only=True,
                trust_remote_code=True,
            )

            if not _deep_probe_enabled():
                return {
                    "ok": True,
                    "status": "config-loaded",
                    "reason": "config_loaded",
                    "model_type": getattr(config, "model_type", None),
                    "deep_probe_enabled": False,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }

            try:
                processor = AutoProcessor.from_pretrained(
                    model_status["path"],
                    local_files_only=True,
                    trust_remote_code=True,
                )
            except Exception as exc:
                return {
                    "ok": False,
                    "status": "processor-load-failed",
                    "reason": "processor_not_ready",
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                    "model_type": getattr(config, "model_type", None),
                    "deep_probe_enabled": True,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }

    except Exception as exc:
        return {
            "ok": False,
            "status": "config-load-failed",
            "reason": "native_stack_not_ready",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "deep_probe_enabled": _deep_probe_enabled(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    return {
        "ok": True,
        "status": "processor-loaded",
        "reason": "processor_loaded",
        "model_type": getattr(config, "model_type", None),
        "processor_class": processor.__class__.__name__,
        "deep_probe_enabled": True,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _base_worker_payload(request: Dict[str, Any], status: str, **extra: Any) -> Dict[str, Any]:
    payload = {
        "transport": "subprocess",
        "protocol_version": request.get("protocol_version"),
        "status": status,
    }
    payload.update(extra)
    return payload


def _worker_environment(request: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "supports_native_realtime": False,
        "native_runtime_enabled": _native_runtime_enabled(),
        "deep_probe_enabled": _deep_probe_enabled(),
        "synthetic_smoke_enabled": _synthetic_smoke_enabled(),
        "model_id": request.get("model_id"),
    }


def _worker_capabilities(native_probe: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "healthcheck": True,
        "native_probe": True,
        "deep_native_probe": _deep_probe_enabled(),
        "synthesize_stream": False,
        "synthetic_smoke": bool(native_probe.get("ok")) and _synthetic_smoke_enabled(),
    }


def _synthetic_smoke_pcm_bytes(sample_rate: int = 24000, duration_ms: int = 300) -> bytes:
    frame_count = max(1, int(sample_rate * duration_ms / 1000))
    pcm = bytearray()
    for index in range(frame_count):
        sample = int(12000 * math.sin(2 * math.pi * 220 * (index / sample_rate)))
        pcm.extend(int(sample).to_bytes(2, byteorder="little", signed=True))
    return bytes(pcm)


def _healthcheck_response(request: Dict[str, Any]) -> Dict[str, Any]:
    model_status = _get_model_status(request.get("model_id"))
    native_probe = _probe_native_stack(model_status)
    return {
        "ok": True,
        "worker": _base_worker_payload(
            request,
            status="healthy",
            environment=_worker_environment(request),
            capabilities=_worker_capabilities(native_probe),
            model=model_status,
            native_probe=native_probe,
        ),
        "request_id": request.get("request_id"),
    }


def _synthesize_unavailable_response(request: Dict[str, Any], model_status: Dict[str, Any], native_probe: Dict[str, Any]) -> Dict[str, Any]:
    if native_probe.get("status") == "disabled":
        message = "Worker isolado disponivel, mas a carga nativa controlada ainda esta desligada neste ambiente."
    elif native_probe.get("status") == "model-missing":
        message = "Worker isolado disponivel, mas o checkpoint Realtime 0.5B ainda nao foi instalado localmente."
    elif not native_probe.get("ok"):
        message = (
            "Worker isolado disponivel, mas a pilha nativa do Realtime 0.5B ainda nao carregou com sucesso: "
            f"{native_probe.get('message') or native_probe.get('reason') or native_probe.get('status')}."
        )
    elif not _synthetic_smoke_enabled():
        message = "Worker isolado carregou o config nativo, mas o smoke controlado ainda esta desligado neste ambiente."
    else:
        message = "Worker isolado carregou o config nativo, mas a sintese Realtime 0.5B ainda nao foi validada neste ambiente."

    return {
        "ok": False,
        "engine": {
            "engine_key": "realtime_0_5b",
            "engine_label": "VibeVoice Realtime 0.5B (worker isolado)",
            "fallback": False,
        },
        "error": {
            "code": "tts_realtime_unavailable",
            "message": message,
            "details": {
                "model": model_status,
                "native_probe": native_probe,
            },
        },
        "worker": _base_worker_payload(
            request,
            status=native_probe.get("status", "stub-unavailable"),
            environment=_worker_environment(request),
            capabilities=_worker_capabilities(native_probe),
            model=model_status,
            native_probe=native_probe,
        ),
        "request_id": request.get("request_id"),
    }


def _synthetic_smoke_response(request: Dict[str, Any], model_status: Dict[str, Any], native_probe: Dict[str, Any]) -> Dict[str, Any]:
    pcm_bytes = _synthetic_smoke_pcm_bytes()
    return {
        "ok": True,
        "engine": {
            "engine_key": "realtime_0_5b",
            "engine_label": "VibeVoice Realtime 0.5B (worker isolado)",
            "fallback": False,
        },
        "audio": {
            "format": "pcm_s16le",
            "sample_rate": 24000,
            "data_hex": pcm_bytes.hex(),
        },
        "worker": _base_worker_payload(
            request,
            status="synthetic-smoke",
            environment=_worker_environment(request),
            capabilities=_worker_capabilities(native_probe),
            model=model_status,
            native_probe=native_probe,
            smoke={
                "synthetic": True,
                "duration_ms": 300,
                "sample_rate": 24000,
            },
        ),
        "request_id": request.get("request_id"),
    }


def _synthesize_response(request: Dict[str, Any]) -> Dict[str, Any]:
    model_status = _get_model_status(request.get("model_id"))
    native_probe = _probe_native_stack(model_status)
    if native_probe.get("ok") and _synthetic_smoke_enabled():
        return _synthetic_smoke_response(request, model_status, native_probe)
    return _synthesize_unavailable_response(request, model_status, native_probe)


def handle_request(request: Dict[str, Any]) -> Dict[str, Any]:
    if request.get("op") == "healthcheck":
        return _healthcheck_response(request)
    return _synthesize_response(request)


def main() -> int:
    request = json.load(sys.stdin)
    try:
        payload = handle_request(request)
    except Exception as exc:
        payload = {
            "ok": False,
            "engine": {
                "engine_key": "realtime_0_5b",
                "engine_label": "VibeVoice Realtime 0.5B (worker isolado)",
                "fallback": False,
            },
            "error": {
                "code": "tts_realtime_unavailable",
                "message": "Worker isolado falhou antes de concluir a verificacao nativa do Realtime 0.5B.",
                "details": {
                    "error_type": exc.__class__.__name__,
                    "message": str(exc),
                },
            },
            "worker": _base_worker_payload(
                request,
                status="internal-error",
                environment=_worker_environment(request),
            ),
            "request_id": request.get("request_id"),
        }
    json.dump(payload, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

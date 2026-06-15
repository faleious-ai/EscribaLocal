import json
import platform
import sys


def main() -> int:
    request = json.load(sys.stdin)
    if request.get("op") == "healthcheck":
        json.dump({
            "ok": True,
            "worker": {
                "transport": "subprocess",
                "protocol_version": request.get("protocol_version"),
                "status": "healthy",
                "environment": {
                    "python_version": platform.python_version(),
                    "platform": platform.system(),
                    "supports_native_realtime": False,
                    "model_id": request.get("model_id"),
                },
            },
            "request_id": request.get("request_id"),
        }, sys.stdout)
        return 0

    response = {
        "ok": False,
        "engine": {
            "engine_key": "realtime_0_5b",
            "engine_label": "VibeVoice Realtime 0.5B (worker isolado)",
            "fallback": False,
        },
        "error": {
            "code": "tts_realtime_unavailable",
            "message": (
                "worker isolado presente, mas a geracao nativa Realtime 0.5B ainda nao foi validada "
                "para este ambiente."
            ),
        },
        "worker": {
            "transport": "subprocess",
            "protocol_version": request.get("protocol_version"),
            "status": "stub-unavailable",
        },
        "request_id": request.get("request_id"),
    }
    json.dump(response, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

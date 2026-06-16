import json
import sys


def test_realtime_worker_client_accepts_fake_success(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    captured = {}
    command = [
        sys.executable,
        "-c",
        (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            "captured = {"
            "'op': req.get('op'),"
            "'protocol_version': req.get('protocol_version'),"
            "'request_id_present': bool(req.get('request_id')),"
            "'worker_transport': req.get('transport')"
            "};"
            "json.dump({"
            "'ok': True,"
            "'engine': {'engine_key': 'realtime_0_5b', 'engine_label': 'Fake Realtime Worker', 'fallback': False},"
            "'audio': {'format': 'pcm_s16le', 'sample_rate': 24000, 'data_hex': '01000200'},"
            "'worker': {'transport': 'subprocess', 'protocol_version': 1, 'status': 'fake-success', 'echo': captured},"
            "'request_id': req.get('request_id')"
            "}, sys.stdout)"
        ),
    ]
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: command)

    result = realtime.generate_voice_realtime_wav_with_metadata("Ola.")

    assert result["engine_key"] == "realtime_0_5b"
    assert result["worker"] == {
        "transport": "subprocess",
        "protocol_version": 1,
        "status": "fake-success",
        "echo": {
            "op": "synthesize_stream",
            "protocol_version": 1,
            "request_id_present": True,
            "worker_transport": "subprocess",
        },
    }
    assert result["wav_bytes"].startswith(b"RIFF")


def test_realtime_worker_missing_returns_structured_unavailable(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    try:
        list(realtime.generate_voice_stream_0_5b("Ola."))
    except realtime.RealtimeUnavailableError as exc:
        payload = exc.to_payload()
    else:
        raise AssertionError("expected RealtimeUnavailableError")

    assert payload == {
        "type": "error",
        "code": "tts_realtime_unavailable",
        "engine_key": "realtime_0_5b",
        "message": (
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ),
    }


def test_tts_stream_reports_worker_unavailable_without_audio(client, monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    with client.websocket_connect("/api/tts/stream") as websocket:
        websocket.send_text(json.dumps({"text": "Ola.", "speaker_id": "speaker_1"}))
        message = json.loads(websocket.receive_text())

    assert message == {
        "type": "error",
        "code": "tts_realtime_unavailable",
        "engine_key": "realtime_0_5b",
        "message": (
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ),
    }


def test_tts_generate_returns_structured_worker_unavailable(client, monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    response = client.post(
        "/api/tts/generate",
        data={"text": "Ola.", "tts_model": "realtime_0_5b"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "type": "error",
        "code": "tts_realtime_unavailable",
        "engine_key": "realtime_0_5b",
        "message": (
            "VibeVoice Realtime 0.5B indisponivel: worker isolado nao encontrado ou nao instalado."
        ),
    }


def test_realtime_module_does_not_load_transformers_pipeline_directly():
    from pathlib import Path

    source = Path("services/vibevoice_realtime_0_5b.py").read_text(encoding="utf-8")

    assert "from transformers import pipeline" not in source
    assert "vibevoice_streaming" not in source


def test_realtime_worker_healthcheck_returns_environment_metadata(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    command = [
        sys.executable,
        "-c",
        (
            "import json,sys,platform;"
            "req=json.load(sys.stdin);"
            "json.dump({"
            "'ok': True,"
            "'worker': {"
            "'transport': 'subprocess',"
            "'protocol_version': req.get('protocol_version'),"
            "'status': 'healthy',"
            "'environment': {"
            "'python_version': platform.python_version(),"
            "'platform': platform.system(),"
            "'supports_native_realtime': False,"
            "'native_runtime_enabled': False"
            "}"
            ",'model': {'installed': False, 'status': 'missing'}"
            ",'native_probe': {'ok': False, 'status': 'disabled'}"
            "},"
            "'request_id': req.get('request_id')"
            "}, sys.stdout)"
        ),
    ]
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: command)

    status = realtime.get_realtime_worker_status()

    assert status["ok"] is True
    assert status["worker"]["transport"] == "subprocess"
    assert status["worker"]["protocol_version"] == 1
    assert status["worker"]["status"] == "healthy"
    assert status["worker"]["environment"]["supports_native_realtime"] is False
    assert status["worker"]["environment"]["native_runtime_enabled"] is False
    assert status["worker"]["model"]["status"] == "missing"
    assert status["worker"]["native_probe"]["status"] == "disabled"


def test_realtime_worker_healthcheck_reports_missing_worker(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["__worker_missing__"])

    status = realtime.get_realtime_worker_status()

    assert status["ok"] is False
    assert status["worker"]["status"] == "unavailable"
    assert status["error"]["code"] == "tts_realtime_unavailable"


def test_realtime_worker_status_endpoint(client, monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    monkeypatch.setattr(realtime, "get_realtime_worker_status", lambda: {
        "ok": True,
        "worker": {
            "transport": "subprocess",
            "protocol_version": 1,
            "status": "healthy",
            "environment": {
                "python_version": "3.12.0",
                "platform": "Windows",
                "supports_native_realtime": False,
                "native_runtime_enabled": False,
            },
            "model": {"installed": False, "status": "missing"},
            "native_probe": {"ok": False, "status": "disabled"},
        },
    })

    response = client.get("/api/tts/realtime-worker/status")

    assert response.status_code == 200
    assert response.json()["worker"]["status"] == "healthy"


def test_worker_healthcheck_reports_disabled_native_probe(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.delenv("ESCRIBA_REALTIME_NATIVE_ENABLE", raising=False)
    monkeypatch.setattr(worker, "_get_model_status", lambda model_id: {
        "installed": False,
        "path": None,
        "status": "missing",
        "model_id": model_id,
    })

    payload = worker.handle_request({
        "op": "healthcheck",
        "protocol_version": 1,
        "request_id": "req-1",
        "model_id": "microsoft/VibeVoice-Realtime-0.5B",
    })

    assert payload["ok"] is True
    assert payload["worker"]["environment"]["native_runtime_enabled"] is False
    assert payload["worker"]["model"]["status"] == "missing"
    assert payload["worker"]["native_probe"] == {
        "ok": False,
        "status": "disabled",
        "reason": "native_runtime_disabled",
        "message": "Probing nativo desligado por padrao neste ambiente.",
    }


def test_worker_healthcheck_reports_probe_failure_when_native_enabled(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setattr(worker, "_get_model_status", lambda model_id: {
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
        "model_id": model_id,
    })
    monkeypatch.setattr(worker, "_probe_native_stack", lambda model_status: {
        "ok": False,
        "status": "config-load-failed",
        "reason": "native_stack_not_ready",
        "message": "Unrecognized model type 'vibevoice_streaming'.",
        "duration_ms": 12.4,
    })

    payload = worker.handle_request({
        "op": "healthcheck",
        "protocol_version": 1,
        "request_id": "req-2",
        "model_id": "microsoft/VibeVoice-Realtime-0.5B",
    })

    assert payload["ok"] is True
    assert payload["worker"]["environment"]["native_runtime_enabled"] is True
    assert payload["worker"]["model"]["installed"] is True
    assert payload["worker"]["native_probe"]["status"] == "config-load-failed"


def test_worker_healthcheck_does_not_report_synthetic_smoke_capability(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setenv("ESCRIBA_REALTIME_SYNTHETIC_SMOKE_ENABLE", "1")
    monkeypatch.setattr(worker, "_get_model_status", lambda model_id: {
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
        "model_id": model_id,
    })
    monkeypatch.setattr(worker, "_probe_native_stack", lambda model_status: {
        "ok": True,
        "status": "config-loaded",
        "reason": "config_loaded",
        "model_type": "vibevoice_streaming",
        "duration_ms": 8.1,
    })

    payload = worker.handle_request({
        "op": "healthcheck",
        "protocol_version": 1,
        "request_id": "req-2b",
        "model_id": "microsoft/VibeVoice-Realtime-0.5B",
    })

    assert payload["ok"] is True
    assert payload["worker"]["capabilities"] == {
        "healthcheck": True,
        "native_probe": True,
        "deep_native_probe": False,
        "synthesize_stream": False,
    }


def test_worker_healthcheck_reports_deep_probe_capability_when_enabled(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setenv("ESCRIBA_REALTIME_DEEP_PROBE_ENABLE", "1")
    monkeypatch.setattr(worker, "_get_model_status", lambda model_id: {
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
        "model_id": model_id,
    })
    monkeypatch.setattr(worker, "_probe_native_stack", lambda model_status: {
        "ok": True,
        "status": "processor-loaded",
        "reason": "processor_loaded",
        "model_type": "vibevoice_streaming",
        "processor_class": "FakeProcessor",
        "duration_ms": 9.7,
    })

    payload = worker.handle_request({
        "op": "healthcheck",
        "protocol_version": 1,
        "request_id": "req-2c",
        "model_id": "microsoft/VibeVoice-Realtime-0.5B",
    })

    assert payload["ok"] is True
    assert payload["worker"]["capabilities"] == {
        "healthcheck": True,
        "native_probe": True,
        "deep_native_probe": True,
        "synthesize_stream": False,
    }
    assert payload["worker"]["native_probe"]["status"] == "processor-loaded"
    assert payload["worker"]["native_probe"]["processor_class"] == "FakeProcessor"


def test_worker_synthesize_unavailable_surfaces_probe_reason(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setattr(worker, "_get_model_status", lambda model_id: {
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
        "model_id": model_id,
    })
    monkeypatch.setattr(worker, "_probe_native_stack", lambda model_status: {
        "ok": False,
        "status": "config-load-failed",
        "reason": "native_stack_not_ready",
        "message": "Unrecognized model type 'vibevoice_streaming'.",
    })

    payload = worker.handle_request({
        "op": "synthesize_stream",
        "protocol_version": 1,
        "request_id": "req-3",
        "model_id": "microsoft/VibeVoice-Realtime-0.5B",
    })

    assert payload["ok"] is False
    assert payload["worker"]["status"] == "config-load-failed"
    assert payload["error"]["details"]["native_probe"]["status"] == "config-load-failed"
    assert "vibevoice_streaming" in payload["error"]["message"]


def test_worker_synthesize_returns_unavailable_even_when_synthetic_smoke_was_requested(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setenv("ESCRIBA_REALTIME_SYNTHETIC_SMOKE_ENABLE", "1")
    monkeypatch.setattr(worker, "_get_model_status", lambda model_id: {
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
        "model_id": model_id,
    })
    monkeypatch.setattr(worker, "_probe_native_stack", lambda model_status: {
        "ok": True,
        "status": "config-loaded",
        "reason": "config_loaded",
        "model_type": "vibevoice_streaming",
        "duration_ms": 5.4,
    })

    payload = worker.handle_request({
        "op": "synthesize_stream",
        "protocol_version": 1,
        "request_id": "req-4",
        "model_id": "microsoft/VibeVoice-Realtime-0.5B",
    })

    assert payload["ok"] is False
    assert payload["error"]["code"] == "tts_realtime_unavailable"
    assert "audio" not in payload
    assert payload["worker"]["status"] == "config-loaded"


def test_worker_probe_loads_processor_when_deep_probe_enabled(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setenv("ESCRIBA_REALTIME_DEEP_PROBE_ENABLE", "1")

    entered = []

    class DummyContext:
        def __enter__(self):
            entered.append("enter")
            return None

        def __exit__(self, exc_type, exc, tb):
            entered.append("exit")
            return False

    class FakeConfig:
        model_type = "vibevoice_streaming"
        auto_map = {}

    class FakeProcessor:
        tokenizer = object()
        feature_extractor = object()

    class FakeModel:
        pass

    monkeypatch.setitem(sys.modules, "transformers", type("FakeTransformers", (), {
        "AutoConfig": type("AutoConfig", (), {
            "from_pretrained": staticmethod(lambda *args, **kwargs: FakeConfig()),
        }),
        "AutoProcessor": type("AutoProcessor", (), {
            "from_pretrained": staticmethod(lambda *args, **kwargs: FakeProcessor()),
        }),
        "AutoTokenizer": type("AutoTokenizer", (), {}),
        "AutoFeatureExtractor": type("AutoFeatureExtractor", (), {}),
        "AutoModel": type("AutoModel", (), {
            "_model_mapping": {FakeConfig: FakeModel}
        }),
    })())

    runtime_patches = type("RuntimePatches", (), {"apply_runtime_patches": staticmethod(lambda: entered.append("patched"))})()
    transformers_loader = type("TransformersLoader", (), {"use_standard_transformers": staticmethod(lambda: DummyContext())})()
    monkeypatch.setitem(sys.modules, "services.runtime_patches", runtime_patches)
    monkeypatch.setitem(sys.modules, "services.transformers_loader", transformers_loader)

    probe = worker._probe_native_stack({
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
    })

    assert probe["ok"] is True
    assert probe["status"] == "processor-loaded"
    assert probe["model_type"] == "vibevoice_streaming"
    assert probe["processor_class"] == "FakeProcessor"
    assert entered == ["patched", "enter", "exit"]


def test_realtime_worker_client_rejects_synthetic_smoke_audio(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    command = [
        sys.executable,
        "-c",
        (
            "import json,sys;"
            "req=json.load(sys.stdin);"
            "json.dump({"
            "'ok': True,"
            "'engine': {'engine_key': 'realtime_0_5b', 'engine_label': 'Synthetic Smoke Worker', 'fallback': False},"
            "'audio': {'format': 'pcm_s16le', 'sample_rate': 24000, 'data_hex': '0000010002000300'},"
            "'worker': {'transport': 'subprocess', 'protocol_version': 1, 'status': 'synthetic-smoke', 'smoke': {'synthetic': True}},"
            "'request_id': req.get('request_id')"
            "}, sys.stdout)"
        ),
    ]
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: command)

    try:
        realtime.generate_voice_realtime_wav_with_metadata("Ola.")
    except realtime.RealtimeUnavailableError as exc:
        payload = exc.to_payload()
    else:
        raise AssertionError("expected RealtimeUnavailableError")

    assert payload["code"] == "tts_realtime_unavailable"
    assert "sintetico" in payload["message"].lower()


def test_realtime_worker_client_records_basic_telemetry(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    events = []

    class FakeCompleted:
        returncode = 0
        stdout = json.dumps({
            "ok": True,
            "worker": {
                "transport": "subprocess",
                "protocol_version": 1,
                "status": "healthy",
                "native_probe": {"status": "disabled"},
            },
        })
        stderr = ""

    monkeypatch.setattr(realtime, "record_app_event", lambda event_type, **fields: events.append((event_type, fields)))
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["fake-worker"])
    monkeypatch.setattr(realtime.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    realtime.get_realtime_worker_status()

    assert events[0][0] == "tts_realtime_worker_invoked"
    assert events[0][1]["worker_op"] == "healthcheck"
    assert events[1][0] == "tts_realtime_worker_completed"
    assert events[1][1]["worker_native_probe_status"] == "disabled"
    assert isinstance(events[1][1]["duration_ms"], float)


def test_worker_probe_returns_breakdown_on_success(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setenv("ESCRIBA_REALTIME_DEEP_PROBE_ENABLE", "1")

    class FakeConfig:
        model_type = "vibevoice_streaming"
        auto_map = {"AutoModel": "modeling_vibevoice_realtime.VibeVoiceRealtimeModel"}

    class FakeProcessor:
        tokenizer = object()
        feature_extractor = object()

    class FakeModelClass:
        pass

    monkeypatch.setitem(sys.modules, "transformers", type("FakeTransformers", (), {
        "AutoConfig": type("AutoConfig", (), {
            "from_pretrained": staticmethod(lambda *args, **kwargs: FakeConfig()),
        }),
        "AutoProcessor": type("AutoProcessor", (), {
            "from_pretrained": staticmethod(lambda *args, **kwargs: FakeProcessor()),
        }),
        "AutoTokenizer": type("AutoTokenizer", (), {}),
        "AutoFeatureExtractor": type("AutoFeatureExtractor", (), {}),
        "AutoModel": type("AutoModel", (), {}),
    })())

    monkeypatch.setitem(sys.modules, "transformers.models.auto.dynamic_module_utils", type("FakeDynamicUtils", (), {
        "get_class_from_dynamic_module": staticmethod(lambda *args, **kwargs: FakeModelClass),
    })())

    runtime_patches = type("RuntimePatches", (), {"apply_runtime_patches": staticmethod(lambda: None)})()
    transformers_loader = type("TransformersLoader", (), {"use_standard_transformers": staticmethod(lambda: type("DummyCtx", (), {"__enter__": lambda s: None, "__exit__": lambda s, *a: False})())})()
    monkeypatch.setitem(sys.modules, "services.runtime_patches", runtime_patches)
    monkeypatch.setitem(sys.modules, "services.transformers_loader", transformers_loader)

    probe = worker._probe_native_stack({
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
    })

    assert probe["ok"] is True
    assert probe["status"] == "processor-loaded"
    assert probe["deep_probe_enabled"] is True
    assert probe["model_class_name"] == "FakeModelClass"

    breakdown = probe["deep_probe"]["breakdown"]
    assert breakdown["imports_ok"] is True
    assert breakdown["config_ok"] is True
    assert breakdown["processor_ok"] is True
    assert breakdown["tokenizer_ok"] is True
    assert breakdown["feature_extractor_ok"] is True
    assert breakdown["model_class_ok"] is True
    assert probe["deep_probe"]["failed_step"] is None


def test_worker_probe_returns_breakdown_on_partial_failure(monkeypatch):
    import workers.vibevoice_realtime_worker as worker

    monkeypatch.setenv("ESCRIBA_REALTIME_NATIVE_ENABLE", "1")
    monkeypatch.setenv("ESCRIBA_REALTIME_DEEP_PROBE_ENABLE", "1")

    class FakeConfig:
        model_type = "vibevoice_streaming"
        auto_map = {}

    class FakeProcessor:
        tokenizer = None
        feature_extractor = object()

    class BadTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            raise ValueError("Falha simulada no carregamento do tokenizer")

    monkeypatch.setitem(sys.modules, "transformers", type("FakeTransformers", (), {
        "AutoConfig": type("AutoConfig", (), {
            "from_pretrained": staticmethod(lambda *args, **kwargs: FakeConfig()),
        }),
        "AutoProcessor": type("AutoProcessor", (), {
            "from_pretrained": staticmethod(lambda *args, **kwargs: FakeProcessor()),
        }),
        "AutoTokenizer": BadTokenizer,
        "AutoFeatureExtractor": type("AutoFeatureExtractor", (), {}),
        "AutoModel": type("AutoModel", (), {}),
    })())

    runtime_patches = type("RuntimePatches", (), {"apply_runtime_patches": staticmethod(lambda: None)})()
    transformers_loader = type("TransformersLoader", (), {"use_standard_transformers": staticmethod(lambda: type("DummyCtx", (), {"__enter__": lambda s: None, "__exit__": lambda s, *a: False})())})()
    monkeypatch.setitem(sys.modules, "services.runtime_patches", runtime_patches)
    monkeypatch.setitem(sys.modules, "services.transformers_loader", transformers_loader)

    probe = worker._probe_native_stack({
        "installed": True,
        "path": "C:/fake/model",
        "status": "installed",
    })

    assert probe["ok"] is False
    assert probe["status"] == "tokenizer-load-failed"
    assert probe["reason"] == "tokenizer_load_failed"
    assert probe["deep_probe_enabled"] is True

    breakdown = probe["deep_probe"]["breakdown"]
    assert breakdown["imports_ok"] is True
    assert breakdown["config_ok"] is True
    assert breakdown["processor_ok"] is True
    assert breakdown["tokenizer_ok"] is False
    assert breakdown["feature_extractor_ok"] is False
    assert breakdown["model_class_ok"] is False
    assert probe["deep_probe"]["failed_step"] == "tokenizer"
    assert probe["deep_probe"]["error_type"] == "ValueError"
    assert "Falha simulada" in probe["deep_probe"]["message"]


def test_realtime_worker_telemetry_captures_deep_probe_breakdown(monkeypatch):
    from services import vibevoice_realtime_0_5b as realtime

    events = []

    class FakeCompleted:
        returncode = 0
        stdout = json.dumps({
            "ok": True,
            "worker": {
                "transport": "subprocess",
                "protocol_version": 1,
                "status": "healthy",
                "native_probe": {
                    "ok": True,
                    "status": "processor-loaded",
                    "reason": "processor_loaded",
                    "model_class_name": "VibeVoiceRealtimeModel",
                    "deep_probe_enabled": True,
                    "deep_probe": {
                        "failed_step": None,
                        "error_type": None,
                        "message": None,
                        "breakdown": {
                            "imports_ok": True,
                            "config_ok": True,
                            "processor_ok": True,
                            "tokenizer_ok": True,
                            "feature_extractor_ok": True,
                            "model_class_ok": True,
                        }
                    }
                },
            },
        })
        stderr = ""

    monkeypatch.setattr(realtime, "record_app_event", lambda event_type, **fields: events.append((event_type, fields)))
    monkeypatch.setattr(realtime, "_resolve_worker_command", lambda: ["fake-worker"])
    monkeypatch.setattr(realtime.subprocess, "run", lambda *args, **kwargs: FakeCompleted())

    realtime.get_realtime_worker_status()

    completed_event = next(evt for evt in events if evt[0] == "tts_realtime_worker_completed")
    fields = completed_event[1]

    assert fields["deep_probe_enabled"] is True
    assert fields["deep_probe_failed_step"] is None
    assert fields["deep_probe_imports_ok"] is True
    assert fields["deep_probe_config_ok"] is True
    assert fields["deep_probe_processor_ok"] is True
    assert fields["deep_probe_tokenizer_ok"] is True
    assert fields["deep_probe_feature_extractor_ok"] is True
    assert fields["deep_probe_model_class_ok"] is True
    assert fields["model_class_name"] == "VibeVoiceRealtimeModel"

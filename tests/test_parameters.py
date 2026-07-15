"""Lote 7 — testes do registro de parâmetros e da validação clamp+warn."""
import inspect

import pytest

from services.parameters_registry import REGISTRY, get_engine_specs, validate_params


# ----------------------------------------------------------------- registro

def test_registry_metadata_complete():
    assert set(REGISTRY.keys()) == {"whisper", "vibevoice_asr", "tts", "tts_chatterbox"}
    assert len(REGISTRY["whisper"]) == 9
    assert len(REGISTRY["vibevoice_asr"]) == 9
    # TTS: só parâmetros REAIS do caminho nativo do 1.5B (temperature/top_p/
    # top_k/repetition_penalty foram removidos — argmax, sem efeito).
    assert len(REGISTRY["tts"]) == 10
    tts_names = {spec.name for spec in REGISTRY["tts"]}
    assert {"temperature", "top_p", "top_k", "repetition_penalty"}.isdisjoint(tts_names)
    assert {"voice_id", "cfg_scale", "n_diffusion_steps", "max_frames",
            "seed", "failure_policy", "device"} <= tts_names

    chatterbox_names = {spec.name for spec in REGISTRY["tts_chatterbox"]}
    assert {"exaggeration", "cfg_weight", "temperature", "top_p", "min_p",
            "repetition_penalty", "seed"} <= chatterbox_names

    for engine, specs in REGISTRY.items():
        for spec in specs:
            assert spec.label, f"{engine}.{spec.name} sem label"
            assert spec.description, f"{engine}.{spec.name} sem descrição"
            assert spec.impact, f"{engine}.{spec.name} sem impacto"
            if spec.type in ("int", "float"):
                assert spec.min is not None and spec.max is not None, f"{engine}.{spec.name} sem faixa"
            if spec.type == "enum":
                assert spec.choices, f"{engine}.{spec.name} sem choices"
                assert spec.default in spec.choices


def _form_default(func, param_name):
    parameter = inspect.signature(func).parameters[param_name]
    default = parameter.default
    return getattr(default, "default", default)


def test_registry_defaults_match_endpoint_signatures(main_module):
    """Paridade: os defaults do registro DEVEM ser os mesmos dos Form(...) dos
    endpoints. Se este teste quebrar, registro e API divergiram."""
    endpoint_by_engine = {
        "whisper": main_module.transcribe_audio,
        "vibevoice_asr": main_module.transcribe_vibevoice,
        "tts": main_module.tts_generate,
    }
    for engine, endpoint in endpoint_by_engine.items():
        for spec in get_engine_specs(engine):
            endpoint_default = _form_default(endpoint, spec.name)
            assert endpoint_default == spec.default, (
                f"default divergente em {engine}.{spec.name}: "
                f"endpoint={endpoint_default!r} registro={spec.default!r}"
            )


# ---------------------------------------------------------------- validação

def test_clamp_out_of_range_with_warning():
    result = validate_params("whisper", {"beam_size": 50})
    assert result["valid"] is True
    assert result["normalized"]["beam_size"] == 10
    assert any(i["level"] == "warning" and i["param"] == "beam_size" for i in result["issues"])

    result = validate_params("whisper", {"beam_size": 0})
    assert result["normalized"]["beam_size"] == 1


def test_invalid_number_is_error_with_default():
    result = validate_params("whisper", {"beam_size": "abc"})
    assert result["valid"] is False
    assert result["normalized"]["beam_size"] == 5
    assert any(i["level"] == "error" for i in result["issues"])


def test_unknown_enum_resets_to_default():
    result = validate_params("whisper", {"compute_type": "fp64"})
    assert result["valid"] is True
    assert result["normalized"]["compute_type"] == "float16"
    assert any(i["param"] == "compute_type" and i["level"] == "warning" for i in result["issues"])


def test_unknown_param_warned_and_ignored():
    result = validate_params("whisper", {"warp_drive": 9})
    assert "warp_drive" not in result["normalized"]
    assert any(i["param"] == "warp_drive" for i in result["issues"])


def test_chatterbox_parameters_are_typed_and_clamped_by_registry():
    result = validate_params("tts_chatterbox", {"temperature": "1.2", "seed": "42", "top_p": 4})
    assert result["valid"] is True
    assert result["normalized"]["temperature"] == 1.2
    assert result["normalized"]["seed"] == 42
    assert result["normalized"]["top_p"] == 1.0


def test_bool_coercion_from_strings():
    result = validate_params("whisper", {"vad_filter": "false"})
    assert result["normalized"]["vad_filter"] is False
    result = validate_params("whisper", {"vad_filter": "sim"})
    assert result["normalized"]["vad_filter"] is True


def test_cross_check_sampling_ignored_when_deterministic():
    result = validate_params("vibevoice_asr", {"vibevoice_temperature": 0.0, "vibevoice_top_p": 0.5})
    assert any("ignorados" in i["message"] for i in result["issues"])


def test_cross_check_beam_vram_warning():
    result = validate_params("whisper", {"beam_size": 9, "device": "cuda"})
    assert any("VRAM" in i["message"] for i in result["issues"])


def test_validate_unknown_engine_raises():
    with pytest.raises(KeyError):
        validate_params("desconhecida", {})


# -------------------------------------------------------------------- rotas

def test_parameters_endpoints(client):
    data = client.get("/api/parameters").json()
    assert set(data["engines"].keys()) == {"whisper", "vibevoice_asr", "tts", "tts_chatterbox"}

    whisper = client.get("/api/parameters/whisper").json()
    assert len(whisper["parameters"]) == 9
    assert client.get("/api/parameters/nao-existe").status_code == 404

    validation = client.post(
        "/api/parameters/validate",
        json={"engine": "whisper", "params": {"beam_size": 99}},
    ).json()
    assert validation["normalized"]["beam_size"] == 10
    assert client.post(
        "/api/parameters/validate", json={"engine": "x", "params": {}}
    ).status_code == 404


def test_transcribe_endpoint_applies_clamp(client, main_module, monkeypatch):
    captured = {}

    def capture_generator(**kwargs):
        captured.update(kwargs)
        yield {"type": "done", "full_transcript": []}

    monkeypatch.setattr(main_module, "transcribe_audio_generator", capture_generator)

    response = client.post(
        "/api/transcribe",
        files={"file": ("teste.wav", b"RIFF0000fakewav", "audio/wav")},
        data={"model": "tiny", "device": "cpu", "compute_type": "fp64", "beam_size": "50"},
    )
    assert response.status_code == 200
    # O gerador deve receber os valores normalizados, não os enviados.
    assert captured["beam_size"] == 10
    assert captured["compute_type"] == "float16"
    assert captured["model_name"] == "tiny"

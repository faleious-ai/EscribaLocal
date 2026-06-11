"""Lote 10 — testes de presets, adequação ao hardware e mapeamento de nomes."""
import pytest

from services import hardware, presets
from services.config_store import EngineDefaults
from services.parameters_registry import validate_params

GPU_6GB = {
    "available": True, "name": "RTX 3050 6GB (fake)", "vram_total_mb": 6144.0,
    "vram_allocated_mb": 500.0, "vram_cached_mb": 0.0, "driver_version": "1",
    "cuda_version": "12.1", "temperature_c": 50, "gpu_utilization_percent": 0,
}
NO_GPU = {**GPU_6GB, "available": False, "vram_total_mb": 0}


# ------------------------------------------------------------- consistência

def test_every_preset_value_within_registry_limits():
    """Teste do plano: todo valor de preset deve estar dentro de min/max e
    choices do registro de parâmetros — sem nenhum ajuste/warning."""
    for preset in presets.PRESETS:
        for engine, params in preset["engine_params"].items():
            result = validate_params(engine, params)
            assert result["valid"], f"{preset['id']}.{engine}: {result['issues']}"
            assert not any(i["level"] in ("warning", "error") for i in result["issues"]), (
                f"{preset['id']}.{engine} fora dos limites do registro: {result['issues']}"
            )
            # Round-trip exato: nenhum valor foi clampado.
            for name, value in params.items():
                assert result["normalized"][name] == value, (
                    f"{preset['id']}.{engine}.{name}: {value} foi normalizado para "
                    f"{result['normalized'][name]}"
                )


def test_preset_params_convert_to_valid_config_defaults():
    for preset in presets.PRESETS:
        converted = presets.form_params_to_config_defaults(preset["engine_params"])
        base = EngineDefaults().model_dump()
        for engine, params in converted.items():
            base[engine].update(params)
        EngineDefaults.model_validate(base)  # não pode levantar


# --------------------------------------------------------------- adequação

def test_suitability_on_6gb_gpu(monkeypatch):
    monkeypatch.setattr(hardware, "get_gpu_status", lambda: GPU_6GB)
    suitability = {p["id"]: p["suitability"] for p in presets.get_presets_with_suitability()}
    assert suitability["seguro"] == "ok"
    assert suitability["baixa-memoria"] == "ok"
    assert suitability["equilibrado"] == "tight"          # tts_1_5b ~5.4GB em 6GB
    assert suitability["maximo-desempenho"] == "ok"
    assert suitability["maxima-qualidade"] == "not_recommended"  # tts_large 19GB
    assert suitability["experimental"] == "tight"


def test_suitability_without_gpu(monkeypatch):
    monkeypatch.setattr(hardware, "get_gpu_status", lambda: NO_GPU)
    enriched = {p["id"]: p for p in presets.get_presets_with_suitability()}
    assert enriched["seguro"]["suitability"] == "ok"
    for preset_id in ("baixa-memoria", "equilibrado", "maximo-desempenho"):
        assert enriched[preset_id]["suitability"] == "not_recommended"


def test_suggest_is_conservative(monkeypatch):
    monkeypatch.setattr(hardware, "get_gpu_status", lambda: GPU_6GB)
    assert presets.suggest_preset()["preset_id"] == "baixa-memoria"

    monkeypatch.setattr(hardware, "get_gpu_status", lambda: NO_GPU)
    assert presets.suggest_preset()["preset_id"] == "seguro"


# -------------------------------------------------------------- mapeamento

def test_form_config_mapping_roundtrip():
    from services.config_store import SettingsModel
    from services.parameters_registry import REGISTRY

    defaults = SettingsModel().defaults.model_dump()
    form_params = presets.config_defaults_to_form_params(defaults)
    # Todos os nomes convertidos devem existir no registro da engine.
    for engine, params in form_params.items():
        registry_names = {spec.name for spec in REGISTRY[engine]}
        unknown = set(params.keys()) - registry_names
        assert not unknown, f"nomes fora do registro em {engine}: {unknown}"

    # Ida e volta preserva os valores.
    back = presets.form_params_to_config_defaults(form_params)
    assert back["whisper"]["temperature"] == defaults["whisper"]["temperature"]
    assert back["vibevoice_asr"]["chunk_length_seconds"] == defaults["vibevoice_asr"]["chunk_length_seconds"]


# -------------------------------------------------------------------- rotas

def test_presets_endpoint_shape(client, monkeypatch):
    monkeypatch.setattr(hardware, "get_gpu_status", lambda: GPU_6GB)
    data = client.get("/api/presets").json()["presets"]
    assert len(data) == 6
    for preset in data:
        assert {"id", "label", "description", "suitability", "suitability_reason",
                "benchmark_dependent", "engine_params"} <= set(preset.keys())


def test_apply_preset_endpoint_updates_settings(client):
    response = client.post("/api/presets/baixa-memoria/apply")
    assert response.status_code == 200
    payload = response.json()
    assert payload["settings"]["defaults"]["whisper"]["model"] == "small"
    assert payload["settings"]["defaults"]["whisper"]["compute_type"] == "int8"
    assert payload["form_params"]["whisper"]["whisper_temperature"] == 0.0

    # Persistiu nos settings.
    config = client.get("/api/config").json()
    assert config["defaults"]["whisper"]["model"] == "small"

    assert client.post("/api/presets/nao-existe/apply").status_code == 404


def test_profile_save_from_form_and_apply(client):
    body = {
        "name": "Perfil do Formulário",
        "engine_params_form": {
            "whisper": {"model": "tiny", "whisper_temperature": 0.2, "beam_size": "2"},
            "vibevoice_asr": {"vibevoice_chunk_size": 30.0},
        },
    }
    response = client.post("/api/profiles/perfil-do-formulario/save-from-form", json=body)
    assert response.status_code == 200
    profile = response.json()
    assert profile["engine_params"]["whisper"]["model"] == "tiny"
    assert profile["engine_params"]["whisper"]["temperature"] == 0.2
    assert profile["engine_params"]["whisper"]["beam_size"] == 2
    assert profile["engine_params"]["vibevoice_asr"]["chunk_length_seconds"] == 30.0

    applied = client.post("/api/profiles/perfil-do-formulario/apply").json()
    assert applied["form_params"]["whisper"]["whisper_temperature"] == 0.2
    assert applied["form_params"]["vibevoice_asr"]["vibevoice_chunk_size"] == 30.0


def test_profile_save_from_form_rejects_invalid(client):
    body = {
        "name": "Inválido",
        "engine_params_form": {"whisper": {"beam_size": 99}},
    }
    response = client.post("/api/profiles/invalido/save-from-form", json=body)
    assert response.status_code == 422

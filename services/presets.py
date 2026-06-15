"""Presets de configuração calibrados para o hardware-alvo (RTX 3050 6GB).

Cada preset usa os MESMOS nomes de campos dos formulários/endpoints (os do
parameters_registry) — a consistência é garantida por teste. A adequação ao
hardware (``suitability``) é calculada em runtime contra a VRAM detectada,
então a tabela continua fazendo sentido em outros PCs.

Diretriz da auditoria externa: o preset sugerido por padrão é CONSERVADOR
(baixa-memoria, ou seguro sem GPU); presets agressivos ficam marcados como
``tight``/``benchmark_dependent`` e a promoção automática só virá com o
benchmark local (Lote 13).

Este módulo também é dono do mapeamento de nomes formulário ↔ config store
(ex.: ``whisper_temperature`` ↔ ``defaults.whisper.temperature``), usado para
aplicar presets/perfis nos settings persistidos.
"""
from typing import Any, Dict, List, Optional

from services.app_logging import record_app_event

# Pico de VRAM estimado (MB) por preset = maior engine que ele configura
# (a política exclusive descarrega as demais antes de cada carga).

PRESETS: List[Dict[str, Any]] = [
    {
        "id": "seguro",
        "label": "Seguro / Compatível",
        "description": "Funciona em qualquer máquina, sem GPU. Whisper base em CPU e TTS 1.5B em CPU quando o modelo estiver pronto, sem fallback para voz do Windows.",
        "min_vram_mb": 0,
        "uses_cuda": False,
        "benchmark_dependent": False,
        "engine_params": {
            "whisper": {"model": "base", "device": "cpu", "compute_type": "int8",
                        "beam_size": 1, "vad_filter": True, "cpu_threads": 8,
                        "whisper_temperature": 0.0},
            "vibevoice_asr": {"vibevoice_diarization": False, "vibevoice_chunk_size": 30.0,
                              "vibevoice_temperature": 0.0, "vibevoice_repetition_penalty": 1.1,
                              "vibevoice_num_beams": 1, "vibevoice_max_new_tokens": 2048},
            "tts": {"tts_model": "tts_1_5b", "speed": 1.0, "device": "cpu",
                    "failure_policy": "cpu"},
        },
    },
    {
        "id": "baixa-memoria",
        "label": "Baixa memória (inicial recomendado)",
        "description": "Conservador para GPUs de 6GB: Whisper small em int8 deixa VRAM livre para o resto do sistema. É o ponto de partida recomendado até o benchmark local promover algo mais forte.",
        "min_vram_mb": 1500,
        "uses_cuda": True,
        "benchmark_dependent": False,
        "engine_params": {
            "whisper": {"model": "small", "device": "cuda", "compute_type": "int8",
                        "beam_size": 1, "vad_filter": True, "cpu_threads": 4,
                        "whisper_temperature": 0.0},
            "vibevoice_asr": {"vibevoice_diarization": True, "vibevoice_chunk_size": 30.0,
                              "vibevoice_temperature": 0.0, "vibevoice_repetition_penalty": 1.1,
                              "vibevoice_num_beams": 1, "vibevoice_max_new_tokens": 2048},
            "tts": {"tts_model": "tts_1_5b", "speed": 1.0, "device": "auto",
                    "failure_policy": "cpu", "cfg_scale": 1.7, "n_diffusion_steps": 10},
        },
    },
    {
        "id": "equilibrado",
        "label": "Equilibrado (pós-benchmark)",
        "description": "Whisper large-v3-turbo em float16 (qualidade quase máxima, rápido) e TTS 1.5B. Em 6GB é APERTADO com o TTS 1.5B — valide com o benchmark antes de adotar como padrão.",
        "min_vram_mb": 5400,
        "uses_cuda": True,
        "benchmark_dependent": True,
        "engine_params": {
            "whisper": {"model": "large-v3-turbo", "device": "cuda", "compute_type": "float16",
                        "beam_size": 5, "vad_filter": True, "cpu_threads": 8,
                        "whisper_temperature": 0.0},
            "vibevoice_asr": {"vibevoice_diarization": True, "vibevoice_chunk_size": 45.0,
                              "vibevoice_temperature": 0.0, "vibevoice_repetition_penalty": 1.1,
                              "vibevoice_num_beams": 1, "vibevoice_max_new_tokens": 2048},
            "tts": {"tts_model": "tts_1_5b", "speed": 1.0, "device": "auto",
                    "failure_policy": "cpu", "cfg_scale": 1.7, "n_diffusion_steps": 12},
        },
    },
    {
        "id": "maximo-desempenho",
        "label": "Máximo desempenho",
        "description": "Velocidade máxima: Whisper large-v3-turbo quantizado (int8_float16, ~1GB) com beam 1, e TTS 1.5B com menos passos de difusão.",
        "min_vram_mb": 1500,
        "uses_cuda": True,
        "benchmark_dependent": False,
        "engine_params": {
            "whisper": {"model": "large-v3-turbo", "device": "cuda", "compute_type": "int8_float16",
                        "beam_size": 1, "vad_filter": True, "cpu_threads": 8,
                        "whisper_temperature": 0.0},
            "vibevoice_asr": {"vibevoice_diarization": True, "vibevoice_chunk_size": 45.0,
                              "vibevoice_temperature": 0.0, "vibevoice_repetition_penalty": 1.1,
                              "vibevoice_num_beams": 1, "vibevoice_max_new_tokens": 2048},
            "tts": {"tts_model": "tts_1_5b", "speed": 1.0, "device": "auto",
                    "failure_policy": "cpu", "cfg_scale": 1.7, "n_diffusion_steps": 8},
        },
    },
    {
        "id": "maxima-qualidade",
        "label": "Máxima qualidade",
        "description": "Whisper large-v3 completo em float16 (~3.3GB) e ASR com janela maior. O TTS Large (19GB) NÃO cabe neste hardware — fica marcado como não recomendado.",
        "min_vram_mb": 19000,
        "uses_cuda": True,
        "benchmark_dependent": True,
        "engine_params": {
            "whisper": {"model": "large-v3", "device": "cuda", "compute_type": "float16",
                        "beam_size": 5, "vad_filter": True, "cpu_threads": 8,
                        "whisper_temperature": 0.0},
            "vibevoice_asr": {"vibevoice_diarization": True, "vibevoice_chunk_size": 60.0,
                              "vibevoice_temperature": 0.0, "vibevoice_repetition_penalty": 1.05,
                              "vibevoice_num_beams": 1, "vibevoice_max_new_tokens": 4096},
            "tts": {"tts_model": "tts_large", "speed": 1.0, "device": "auto",
                    "failure_policy": "fail"},
        },
    },
    {
        "id": "experimental",
        "label": "Experimental / Avançado",
        "description": "Combinações para testar limites: large-v3 quantizado com beam 8 e ASR com amostragem leve. Pode estourar VRAM ou produzir saídas instáveis — use por sua conta.",
        "min_vram_mb": 5400,
        "uses_cuda": True,
        "benchmark_dependent": True,
        "engine_params": {
            "whisper": {"model": "large-v3", "device": "cuda", "compute_type": "int8_float16",
                        "beam_size": 8, "vad_filter": True, "cpu_threads": 10,
                        "whisper_temperature": 0.0},
            "vibevoice_asr": {"vibevoice_diarization": True, "vibevoice_chunk_size": 45.0,
                              "vibevoice_temperature": 0.2, "vibevoice_top_p": 0.9,
                              "vibevoice_repetition_penalty": 1.1, "vibevoice_num_beams": 1,
                              "vibevoice_max_new_tokens": 4096},
            "tts": {"tts_model": "tts_1_5b", "speed": 1.0, "device": "auto",
                    "failure_policy": "cpu", "cfg_scale": 1.4, "n_diffusion_steps": 20},
        },
    },
]

_PRESETS_BY_ID = {preset["id"]: preset for preset in PRESETS}


# ------------------------------------------------------- adequação/sugestão

def _compute_suitability(preset: Dict[str, Any], gpu: Dict[str, Any]) -> Dict[str, str]:
    if not preset["uses_cuda"]:
        return {"suitability": "ok", "suitability_reason": "Não depende de GPU."}
    if not gpu.get("available"):
        return {"suitability": "not_recommended",
                "suitability_reason": "GPU/CUDA não detectada nesta máquina."}
    total_mb = float(gpu.get("vram_total_mb") or 0)
    needed = float(preset["min_vram_mb"])
    if total_mb and needed > total_mb:
        return {"suitability": "not_recommended",
                "suitability_reason": f"Exige ~{needed / 1000:.1f}GB de VRAM; a GPU tem {total_mb / 1000:.1f}GB."}
    if total_mb and needed > total_mb * 0.7:
        return {"suitability": "tight",
                "suitability_reason": f"Usa ~{needed / 1000:.1f}GB dos {total_mb / 1000:.1f}GB de VRAM — apertado; valide com o benchmark."}
    return {"suitability": "ok", "suitability_reason": "Dentro da capacidade da GPU."}


def get_presets_with_suitability() -> List[Dict[str, Any]]:
    from services.hardware import get_gpu_status

    gpu = get_gpu_status()
    enriched = []
    for preset in PRESETS:
        entry = dict(preset)
        entry.update(_compute_suitability(preset, gpu))
        enriched.append(entry)
    return enriched


def suggest_preset() -> Dict[str, str]:
    """Sugestão conservadora (sem benchmark — Lote 13 fará a promoção)."""
    from services.hardware import get_gpu_status

    gpu = get_gpu_status()
    if not gpu.get("available"):
        return {"preset_id": "seguro",
                "reason": "GPU/CUDA não detectada; o preset Seguro roda inteiramente em CPU."}
    return {
        "preset_id": "baixa-memoria",
        "reason": f"GPU {gpu.get('name', '')} detectada. Início conservador para estabilidade; "
                  f"rode o benchmark local (em breve) para promover a um preset mais forte.",
    }


def get_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    return _PRESETS_BY_ID.get(preset_id)


# --------------------------------------- mapeamento formulário ↔ config store

# Campos cujo nome difere entre o formulário (registry) e o config store.
_FORM_TO_CONFIG = {
    "whisper": {"whisper_temperature": "temperature", "whisper_prompt": None},
    "vibevoice_asr": {
        "vibevoice_prompt": None,  # conteúdo do usuário; não persiste em defaults
        "vibevoice_diarization": "diarization",
        "vibevoice_chunk_size": "chunk_length_seconds",
        "vibevoice_temperature": "temperature",
        "vibevoice_repetition_penalty": "repetition_penalty",
        "vibevoice_top_p": "top_p",
        "vibevoice_top_k": "top_k",
        "vibevoice_num_beams": "num_beams",
        "vibevoice_max_new_tokens": "max_new_tokens",
    },
    "tts": {},
}
_CONFIG_TO_FORM = {
    engine: {config: form for form, config in mapping.items() if config}
    for engine, mapping in _FORM_TO_CONFIG.items()
}


def form_params_to_config_defaults(engine_params: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Converte params com nomes de formulário para o shape do config store."""
    converted: Dict[str, Dict[str, Any]] = {}
    for engine, params in (engine_params or {}).items():
        mapping = _FORM_TO_CONFIG.get(engine, {})
        engine_out: Dict[str, Any] = {}
        for form_name, value in params.items():
            config_name = mapping.get(form_name, form_name)
            if config_name is None:
                continue
            engine_out[config_name] = value
        converted[engine] = engine_out
    return converted


def config_defaults_to_form_params(defaults: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Converte defaults do config store para os nomes de formulário.

    Campos legados do config que não existem mais no registro (ex.:
    temperature do TTS, sem efeito no caminho nativo do 1.5B) são omitidos.
    """
    from services.parameters_registry import REGISTRY

    converted: Dict[str, Dict[str, Any]] = {}
    for engine, params in (defaults or {}).items():
        mapping = _CONFIG_TO_FORM.get(engine, {})
        registry_names = {spec.name for spec in REGISTRY.get(engine, [])}
        converted[engine] = {
            mapping.get(name, name): value
            for name, value in params.items()
            if not registry_names or mapping.get(name, name) in registry_names
        }
    return converted


def apply_preset(preset_id: str):
    """Aplica um preset aos defaults persistidos; retorna (settings, form_params)."""
    from services.config_store import get_settings, save_settings

    preset = get_preset(preset_id)
    if preset is None:
        return None

    settings = get_settings()
    defaults = settings.defaults.model_dump()
    for engine, params in form_params_to_config_defaults(preset["engine_params"]).items():
        defaults.setdefault(engine, {}).update(params)

    updated = settings.model_copy(update={"defaults": type(settings.defaults).model_validate(defaults)})
    saved = save_settings(updated)
    record_app_event("preset_applied", preset_id=preset_id)
    return saved, preset["engine_params"]

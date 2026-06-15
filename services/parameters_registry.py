"""Registro central de parâmetros das engines — fonte única de verdade.

Cada parâmetro carrega metadados completos (nome, descrição, default,
intervalo, impacto, riscos, dependências e incompatibilidades) consumidos
pelo modo avançado da UI via GET /api/parameters.

Os nomes dos specs são EXATAMENTE os nomes dos campos de formulário dos
endpoints (/api/transcribe, /api/transcribe-vibevoice, /api/tts/generate);
o teste de paridade em tests/test_parameters.py garante que os defaults
daqui nunca divirjam das assinaturas dos endpoints.

A validação opera em modo *clamp + warn*: valores fora de faixa são
ajustados ao limite (warning), enums inválidos voltam ao default (warning) e
apenas valores impossíveis de converter geram erro.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

ENGINES = ("whisper", "vibevoice_asr", "tts")


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    engine: str
    type: str                      # "int" | "float" | "bool" | "str" | "enum"
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    choices: Optional[Tuple[Any, ...]] = None
    label: str = ""
    description: str = ""
    impact: str = ""               # "qualidade" | "velocidade" | "memoria" | "misto" | "conteudo"
    risks: Optional[str] = None
    requires: Tuple[str, ...] = ()
    incompatible_with: Tuple[str, ...] = ()
    advanced: bool = False


_WHISPER_PARAMS: List[ParameterSpec] = [
    ParameterSpec(
        name="model", engine="whisper", type="enum", default="large-v3-turbo",
        choices=("tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"),
        label="Modelo Whisper",
        description="Tamanho do modelo. Maior = melhor qualidade e mais VRAM/tempo.",
        impact="misto",
        risks="large-v3 em float16 ocupa ~3.3GB de VRAM; apertado em GPUs de 6GB.",
    ),
    ParameterSpec(
        name="device", engine="whisper", type="enum", default="cuda",
        choices=("cuda", "cpu"),
        label="Dispositivo",
        description="GPU (cuda) é muito mais rápida; CPU sempre funciona.",
        impact="velocidade",
    ),
    ParameterSpec(
        name="compute_type", engine="whisper", type="enum", default="float16",
        choices=("float32", "float16", "int8", "int8_float16"),
        label="Precisão de cálculo",
        description="float16 = qualidade plena na GPU; int8/int8_float16 = menos VRAM com perda mínima; float32 = CPU.",
        impact="memoria",
        risks="float16 em CPU não é suportado pelo CTranslate2 (haverá fallback interno).",
    ),
    ParameterSpec(
        name="beam_size", engine="whisper", type="int", default=5, min=1, max=10,
        label="Beam size",
        description="Largura da busca de decodificação. Maior = mais preciso e mais lento.",
        impact="qualidade",
        risks="Acima de 8 na GPU aumenta o pico de VRAM consideravelmente.",
        advanced=True,
    ),
    ParameterSpec(
        name="language", engine="whisper", type="str", default="auto",
        label="Idioma",
        description="Código ISO 639-1 (pt, en, es...) ou 'auto' para detecção automática.",
        impact="qualidade",
    ),
    ParameterSpec(
        name="vad_filter", engine="whisper", type="bool", default=True,
        label="Filtro de voz (VAD)",
        description="Pula trechos sem fala. Acelera e evita alucinações em silêncio.",
        impact="misto",
        risks="Pode descartar fala muito baixa ou sussurrada.",
    ),
    ParameterSpec(
        name="cpu_threads", engine="whisper", type="int", default=4, min=1, max=32,
        label="Threads de CPU",
        description="Núcleos usados na decodificação em CPU.",
        impact="velocidade",
        advanced=True,
    ),
    ParameterSpec(
        name="whisper_prompt", engine="whisper", type="str", default=None,
        label="Termos de contexto",
        description="Vocabulário/contexto inicial (nomes próprios, jargões) para guiar a transcrição.",
        impact="conteudo",
        advanced=True,
    ),
    ParameterSpec(
        name="whisper_temperature", engine="whisper", type="float", default=0.0, min=0.0, max=1.0,
        label="Temperatura",
        description="0.0 = determinístico (recomendado); valores altos só ajudam quando o modelo trava em repetições.",
        impact="qualidade",
        risks="Temperatura alta aumenta alucinações.",
        advanced=True,
    ),
]

_VIBEVOICE_ASR_PARAMS: List[ParameterSpec] = [
    ParameterSpec(
        name="vibevoice_prompt", engine="vibevoice_asr", type="str", default=None,
        label="Termos de contexto",
        description="Contexto/vocabulário para guiar a transcrição do VibeVoice.",
        impact="conteudo",
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_diarization", engine="vibevoice_asr", type="bool", default=True,
        label="Diarização",
        description="Identifica e separa os falantes (Speaker 1, Speaker 2...).",
        impact="conteudo",
    ),
    ParameterSpec(
        name="vibevoice_chunk_size", engine="vibevoice_asr", type="float", default=45.0, min=15.0, max=90.0,
        label="Janela do tokenizer (s)",
        description="Tamanho dos blocos do tokenizer acústico. Menor = menos memória; maior = mais contexto.",
        impact="memoria",
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_temperature", engine="vibevoice_asr", type="float", default=0.0, min=0.0, max=1.0,
        label="Temperatura",
        description="0.0 = determinístico (recomendado para transcrição).",
        impact="qualidade",
        risks="Acima de 0 ativa amostragem e pode inventar conteúdo.",
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_repetition_penalty", engine="vibevoice_asr", type="float", default=1.1, min=1.0, max=1.5,
        label="Penalidade de repetição",
        description="Desencoraja loops de texto repetido na saída.",
        impact="qualidade",
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_top_p", engine="vibevoice_asr", type="float", default=1.0, min=0.0, max=1.0,
        label="Top-P (nucleus)",
        description="Limita a amostragem aos tokens mais prováveis.",
        impact="qualidade",
        requires=("vibevoice_temperature > 0",),
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_top_k", engine="vibevoice_asr", type="int", default=50, min=0, max=100,
        label="Top-K",
        description="Considera apenas os K tokens mais prováveis na amostragem.",
        impact="qualidade",
        requires=("vibevoice_temperature > 0",),
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_num_beams", engine="vibevoice_asr", type="int", default=1, min=1, max=5,
        label="Beams",
        description="Busca em feixe. Maior = mais preciso, bem mais lento e mais VRAM.",
        impact="misto",
        risks="Beams altos com modelo de ~7B podem estourar a VRAM de 6GB.",
        incompatible_with=("vibevoice_temperature",),
        advanced=True,
    ),
    ParameterSpec(
        name="vibevoice_max_new_tokens", engine="vibevoice_asr", type="int", default=2048, min=256, max=8192,
        label="Máx. de tokens gerados",
        description="Limite da saída. Áudios longos com diarização precisam de mais tokens.",
        impact="memoria",
        risks="Valor baixo trunca a transcrição de áudios longos.",
        advanced=True,
    ),
]

# Auditoria do caminho nativo do 1.5B (generation_vibevoice.py do fork):
# a seleção de token é SEMPRE argmax — temperature/top_p/top_k/repetition_
# penalty NÃO afetam a geração e foram removidos deste registro. Os controles
# reais são cfg_scale, n_diffusion_steps, max_new_tokens (frames) e a seed
# global da difusão.
_TTS_PARAMS: List[ParameterSpec] = [
    ParameterSpec(
        name="tts_model", engine="tts", type="enum", default="tts_1_5b",
        choices=("tts_1_5b", "tts_large"),
        label="Modelo TTS",
        description="1.5B = qualidade alta (~5.4GB VRAM); Large = 18.7GB, não recomendado em 6GB. Realtime 0.5B: em desenvolvimento — indisponível.",
        impact="misto",
        risks="tts_large excede a VRAM deste hardware (offload lento).",
    ),
    ParameterSpec(
        name="voice_id", engine="tts", type="str", default=None,
        label="Voz (biblioteca)",
        description="Voz real da biblioteca, criada por gravação, upload ou importação.",
        impact="conteudo",
    ),
    ParameterSpec(
        name="speaker_id", engine="tts", type="enum", default="speaker_1",
        choices=("speaker_1", "speaker_2", "speaker_3", "speaker_4"),
        label="Locutor (legado)",
        description="Compatibilidade com roteiros antigos; a identidade vocal vem da biblioteca de vozes reais.",
        impact="conteudo",
        advanced=True,
    ),
    ParameterSpec(
        name="speed", engine="tts", type="float", default=1.0, min=0.5, max=2.0,
        label="Velocidade",
        description="Multiplicador de velocidade aplicado APÓS a geração (resample).",
        impact="conteudo",
    ),
    ParameterSpec(
        name="cfg_scale", engine="tts", type="float", default=1.7, min=1.0, max=3.0,
        label="CFG (adesão ao texto)",
        description="Classifier-Free Guidance da difusão. Maior = pronúncia mais fiel ao texto; menor = voz mais livre/expressiva. 1.7 validado em PT-BR por round-trip.",
        impact="qualidade",
        risks="Abaixo de 1.4 a pronúncia em PT-BR degrada; acima de 2.5 a voz fica tensa/metálica.",
        advanced=True,
    ),
    ParameterSpec(
        name="n_diffusion_steps", engine="tts", type="int", default=10, min=4, max=40,
        label="Passos de difusão",
        description="Passos do scheduler (DPMSolver) por frame de áudio. Mais passos = mais fidelidade e mais tempo de geração (linear).",
        impact="misto",
        advanced=True,
    ),
    ParameterSpec(
        name="max_frames", engine="tts", type="int", default=0, min=0, max=4000,
        label="Teto de frames",
        description="Limite de frames acústicos (7.5/s ≈ 0.13s cada). 0 = automático proporcional ao texto. A geração normalmente termina antes, por fim de fala.",
        impact="memoria",
        risks="Teto baixo demais trunca a fala (a resposta indica truncamento).",
        advanced=True,
    ),
    ParameterSpec(
        name="seed", engine="tts", type="int", default=-1, min=-1, max=2147483647,
        label="Seed da difusão",
        description="-1 = aleatória. Valor fixo reproduz a mesma tomada na mesma máquina/dispositivo/dtype.",
        impact="conteudo",
        advanced=True,
    ),
    ParameterSpec(
        name="failure_policy", engine="tts", type="enum", default="cpu",
        choices=("fail", "cpu"),
        label="Política de falha",
        description="fail = erro sem fallback; cpu = tenta CPU quando a GPU falhar (mesma engine, voz real, lenta).",
        impact="misto",
        risks="Nenhuma política troca para SAPI5, tom sintético ou outra engine; voz personalizada inválida sempre gera erro.",
        advanced=True,
    ),
    ParameterSpec(
        name="device", engine="tts", type="enum", default="auto",
        choices=("auto", "cuda", "cpu"),
        label="Dispositivo",
        description="auto = GPU com retry em CPU; cuda/cpu forçam o dispositivo (trocar exige recarregar o modelo, feito automaticamente).",
        impact="velocidade",
        advanced=True,
    ),
]

REGISTRY: Dict[str, List[ParameterSpec]] = {
    "whisper": _WHISPER_PARAMS,
    "vibevoice_asr": _VIBEVOICE_ASR_PARAMS,
    "tts": _TTS_PARAMS,
}


def get_registry() -> Dict[str, List[Dict[str, Any]]]:
    return {engine: [asdict(spec) for spec in specs] for engine, specs in REGISTRY.items()}


def get_engine_specs(engine: str) -> List[ParameterSpec]:
    if engine not in REGISTRY:
        raise KeyError(engine)
    return REGISTRY[engine]


# ---------------------------------------------------------------- validação

def _issue(param: str, level: str, message: str) -> Dict[str, str]:
    return {"param": param, "level": level, "message": message}


_TRUE_STRINGS = {"true", "1", "yes", "on", "sim"}
_FALSE_STRINGS = {"false", "0", "no", "off", "nao", "não"}


def _coerce(spec: ParameterSpec, value: Any) -> Tuple[Any, Optional[Dict[str, str]]]:
    if value is None:
        return spec.default, None

    if spec.type == "bool":
        if isinstance(value, bool):
            return value, None
        text = str(value).strip().lower()
        if text in _TRUE_STRINGS:
            return True, None
        if text in _FALSE_STRINGS:
            return False, None
        return spec.default, _issue(spec.name, "error",
                                    f"Valor booleano inválido ({value!r}); usado o padrão {spec.default}.")

    if spec.type in ("int", "float"):
        caster = int if spec.type == "int" else float
        try:
            number = caster(float(value))
        except (TypeError, ValueError):
            return spec.default, _issue(spec.name, "error",
                                        f"Valor numérico inválido ({value!r}); usado o padrão {spec.default}.")
        if spec.min is not None and number < spec.min:
            return caster(spec.min), _issue(spec.name, "warning",
                                            f"Valor {number} abaixo do mínimo; ajustado para {spec.min}.")
        if spec.max is not None and number > spec.max:
            return caster(spec.max), _issue(spec.name, "warning",
                                            f"Valor {number} acima do máximo; ajustado para {spec.max}.")
        return number, None

    if spec.type == "enum":
        if value in spec.choices:
            return value, None
        return spec.default, _issue(spec.name, "warning",
                                    f"Opção desconhecida ({value!r}); usado o padrão {spec.default!r}. "
                                    f"Opções: {', '.join(map(str, spec.choices))}.")

    return str(value), None  # "str"


def _cross_checks(engine: str, params: Dict[str, Any], issues: List[Dict[str, str]]) -> None:
    if engine == "whisper":
        if params.get("beam_size", 0) > 8 and params.get("device") == "cuda":
            issues.append(_issue("beam_size", "warning",
                                 "beam_size acima de 8 na GPU eleva bastante o pico de VRAM (6GB)."))
        if params.get("device") == "cpu" and params.get("compute_type") in ("float16", "int8_float16"):
            issues.append(_issue("compute_type", "info",
                                 "float16 não é suportado em CPU; o motor fará fallback interno para int8/float32."))
    elif engine == "vibevoice_asr":
        temperature = params.get("vibevoice_temperature")
        sampling_tuned = (
            ("vibevoice_top_p" in params and params["vibevoice_top_p"] < 1.0)
            or ("vibevoice_top_k" in params and params["vibevoice_top_k"] != 50)
        )
        if sampling_tuned and temperature == 0.0:
            issues.append(_issue("vibevoice_top_p", "info",
                                 "top_p/top_k são ignorados com temperature=0 (decodificação determinística)."))
        if params.get("vibevoice_num_beams", 1) > 1 and (temperature or 0.0) > 0.0:
            issues.append(_issue("vibevoice_num_beams", "warning",
                                 "Beam search com amostragem (temperature>0) é instável; prefira um dos dois."))


def validate_params(engine: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Valida/normaliza parâmetros em modo clamp+warn.

    Retorna {"valid": bool, "normalized": dict, "issues": [..]}.
    ``valid`` só é False quando há issue de nível "error".
    """
    specs = {spec.name: spec for spec in get_engine_specs(engine)}
    normalized: Dict[str, Any] = {}
    issues: List[Dict[str, str]] = []

    for key, value in params.items():
        spec = specs.get(key)
        if spec is None:
            issues.append(_issue(key, "warning", "Parâmetro desconhecido; ignorado."))
            continue
        coerced, issue = _coerce(spec, value)
        normalized[key] = coerced
        if issue is not None:
            issues.append(issue)

    _cross_checks(engine, normalized, issues)
    valid = not any(issue["level"] == "error" for issue in issues)
    return {"valid": valid, "normalized": normalized, "issues": issues}

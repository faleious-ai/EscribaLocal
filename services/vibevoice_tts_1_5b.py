import sys
import os
import gc
import io
import importlib.util
import logging
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.io.wavfile as wavfile
import torch

from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()

from services.transformers_loader import apply_vibevoice_fork_patches, use_custom_transformers

with use_custom_transformers():
    apply_vibevoice_fork_patches()



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.VibeVoiceTTS")

TTS_MODEL_IDS = {
    "tts_1_5b": "microsoft/VibeVoice-1.5B",
    "tts_large": "aoi-ot/VibeVoice-Large",
    "chatterbox-tts-pt-br": "ResembleAI/Chatterbox-Multilingual-pt-br",
}
TTS_MODEL_DISPLAY_NAMES = {
    "tts_1_5b": "VibeVoice-TTS-1.5B (microsoft/VibeVoice-1.5B)",
    "tts_large": "VibeVoice-Large (aoi-ot/VibeVoice-Large)",
    "chatterbox-tts-pt-br": "Chatterbox PT-BR (ResembleAI/Chatterbox-Multilingual-pt-br)",
}
SUPPORTED_LONGFORM_TTS_MODELS = set(TTS_MODEL_IDS)

# O checkpoint oficial está no formato ORIGINAL do VibeVoice; o fork em
# custom_transformers só carrega o formato CONVERTIDO (pesos renomeados +
# config reestruturado). A conversão é local e única por máquina
# (scripts/convert_vibevoice_1_5b.py); sem ela, tokenizers de áudio e
# diffusion head ficam com pesos aleatórios e o TTS deve falhar com erro claro.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVERTED_MODEL_DIRS = {
    "tts_1_5b": os.path.join(_PROJECT_ROOT, "models", "VibeVoice-1.5B-hf"),
}

_native_model_keys = {"tts_1_5b"}
_direct_model_keys = {"tts_large"}

# Receita validada por round-trip TTS->Whisper em PT-BR (scripts/diag_tts_roundtrip.py):
# template de chat do checkpoint + generate direto + referência de voz limpa +
# cfg_scale 1.7 (o default 1.3 produzia pronúncia instável em frases curtas).
DEFAULT_CFG_SCALE = 1.7
ACOUSTIC_HOP = 3200  # amostras por frame acústico (24kHz / 7.5 frames/s)
VIBEVOICE_SYSTEM_PROMPT = (
    " Transform the text provided by various speakers into speech output, "
    "utilizing the distinct voice of each respective speaker.\n"
)
VOICE_REFERENCE_TEXT = (
    "Esta é uma amostra de voz para clonagem. A fala gerada deve soar clara e natural."
)

_native_models: Dict[str, Dict[str, Any]] = {}   # model_key -> {processor, model, device, gen_cfg}
_voice_embeds_cache: Dict[str, Any] = {}          # f"{model_key}:{speaker_id}" -> tensor (n, hidden)
_direct_processors: Dict[str, Any] = {}
_direct_models: Dict[str, Any] = {}

LARGE_MIN_VRAM_MB = 19000


def _resolve_tts_source(model_key: str) -> str:
    """Pasta convertida local quando existe; senão o repo, que deve falhar
    com aviso claro no log."""
    converted_dir = CONVERTED_MODEL_DIRS.get(model_key)
    if converted_dir and os.path.isdir(converted_dir):
        return converted_dir
    if converted_dir:
        logger.warning(
            "Checkpoint convertido ausente em %s — o fork não carrega o formato "
            "original do HuggingFace. Rode: python scripts/convert_vibevoice_1_5b.py",
            converted_dir,
        )
    return TTS_MODEL_IDS[model_key]

_voice_line_pattern = re.compile(r"^(?:voz|voice|speaker)\s*([0-9]+)\s*:\s*(.*)$", re.IGNORECASE)
_speaker_pattern = re.compile(r"^Speaker\s+([0-9]+):", re.IGNORECASE)


def _voice_result(wav_bytes: bytes, engine_key: str, engine_label: str, fallback: bool) -> Dict[str, Any]:
    return {
        "wav_bytes": wav_bytes,
        "engine_key": engine_key,
        "engine_label": engine_label,
        "fallback": fallback,
    }


def get_tts_model_and_processor(model_key: str = "tts_1_5b"):
    """Helper de compatibilidade: retorna a entrada nativa carregada (ou None)."""
    return _load_native_model(model_key)


def get_model_revision(model_key: str = "tts_1_5b") -> str:
    """Revisão do checkpoint em uso (hash do config.json do diretório/repos
    resolvido). Invalida embeddings persistidos quando a conversão muda."""
    source = _resolve_tts_source(model_key)
    config_path = os.path.join(source, "config.json")
    if os.path.exists(config_path):
        import hashlib
        with open(config_path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()[:12]
    return f"repo:{source}"


def _load_native_model(model_key: str, device_preference: str = "auto"):
    """Carrega processor+modelo do checkpoint convertido (cacheados).

    A pipeline genérica text-to-speech do fork foi abandonada de propósito:
    ela tokeniza o texto cru (sem o template de chat com Speaker/tokens de
    fala) e limita a geração a 256 frames — o modelo nunca emitia o fim de
    fala e a saída não era inteligível.
    """
    if model_key not in _native_model_keys:
        return None
    cached = _native_models.get(model_key)
    if cached is not None:
        if device_preference in ("auto", cached["device"]):
            return cached
        # Preferência explícita mudou (ex.: cpu -> cuda): recarrega.
        unload_tts_model()

    source = _resolve_tts_source(model_key)
    if device_preference == "cuda":
        attempts = ["cuda"] if torch.cuda.is_available() else []
    elif device_preference == "cpu":
        attempts = ["cpu"]
    else:  # auto
        attempts = ["cuda"] if torch.cuda.is_available() else []
        # CPU é fallback real: lento, mas é a voz verdadeira do VibeVoice.
        if model_key != "tts_large":
            attempts.append("cpu")

    for device_label in attempts:
        try:
            if device_label == "cuda":
                from services.resource_arbiter import arbiter
                arbiter.prepare_load(model_key)
            with use_custom_transformers():
                from transformers import AutoModelForTextToWaveform, AutoProcessor

                logger.info("Carregando VibeVoice TTS nativo (%s) em %s...", source, device_label)
                processor = AutoProcessor.from_pretrained(source)
                model = AutoModelForTextToWaveform.from_pretrained(
                    source, dtype=torch.bfloat16,
                ).to(device_label).eval()

            import copy
            gen_cfg = copy.deepcopy(model.generation_config)
            gen_cfg.cfg_scale = DEFAULT_CFG_SCALE

            entry = {"processor": processor, "model": model,
                     "device": device_label, "gen_cfg": gen_cfg}
            _native_models[model_key] = entry
            logger.info("VibeVoice TTS nativo carregado: %s (%s)", source, device_label)
            return entry
        except Exception as exc:
            logger.warning("Falha ao carregar VibeVoice TTS nativo (%s) em %s: %s",
                           source, device_label, str(exc)[:400])
    return None


def _voice_reference_waveform(speaker_id: str) -> "np.ndarray | None":
    """Amostra de FALA limpa em PT-BR (SAPI5, 24kHz) usada como referência de
    clonagem por locutor. Sem referência o modelo 'inventa' uma voz instável e
    a pronúncia degrada — comprovado no round-trip. Nunca usa tom senoidal."""
    try:
        import win32com.client

        sapi = win32com.client.Dispatch("SAPI.SpVoice")
        selected = _select_sapi_voice(sapi, speaker_id)
        if selected is not None:
            sapi.Voice = selected
        stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
        stream.Format.Type = 30  # SPSF_24kHz16BitMono
        sapi.AudioOutputStream = stream
        sapi.Speak(VOICE_REFERENCE_TEXT)
        pcm = np.frombuffer(bytes(stream.GetData()), dtype=np.int16)
        if pcm.size < ACOUSTIC_HOP:
            return None
        return pcm.astype(np.float32) / 32768.0
    except Exception as exc:
        logger.warning("Sem referência de voz SAPI5 (%s); gerando sem condicionamento.", exc)
        return None


class VoiceUnavailableError(RuntimeError):
    """Voz escolhida ausente/corrompida — NUNCA cair silenciosamente em outra."""


class LargeModelUnavailableError(RuntimeError):
    """VibeVoice-Large não deve cair em fallback nem tentar carga cega."""


def _cuda_total_vram_mb() -> Optional[float]:
    try:
        if not torch.cuda.is_available():
            return None
        return float(torch.cuda.get_device_properties(0).total_memory) / 1e6
    except Exception as exc:
        logger.debug("Falha ao detectar VRAM total para VibeVoice-Large: %s", exc)
        return None


def _preflight_direct_vibevoice_model(model_key: str) -> None:
    if model_key != "tts_large":
        return
    if importlib.util.find_spec("vibevoice") is None:
        raise LargeModelUnavailableError(
            "VibeVoice-Large indisponivel: dependencia upstream 'vibevoice' ausente. "
            "Instale a biblioteca VibeVoice em ambiente local compativel ou use o VibeVoice-1.5B."
        )

    total_vram_mb = _cuda_total_vram_mb()
    if total_vram_mb is None:
        raise LargeModelUnavailableError(
            "VibeVoice-Large indisponivel: hardware insuficiente ou GPU CUDA nao detectada. "
            "O Large exige estrategia explicita de GPU/offload antes de qualquer carga."
        )
    if total_vram_mb < LARGE_MIN_VRAM_MB:
        raise LargeModelUnavailableError(
            f"VibeVoice-Large indisponivel: hardware insuficiente para este perfil "
            f"({total_vram_mb / 1000:.1f}GB detectados; ~{LARGE_MIN_VRAM_MB / 1000:.0f}GB recomendados). "
            "Nao recomendado para 6GB; defina uma estrategia explicita de hardware/offload antes de usar."
        )


def _embeds_from_waveform(entry: Dict[str, Any], waveform: "np.ndarray"):
    model, processor, device = entry["model"], entry["processor"], entry["device"]
    features = processor.feature_extractor(
        waveform, sampling_rate=24000, return_tensors="pt",
        padding=True, pad_to_multiple_of=ACOUSTIC_HOP,
    )["input_features"].to(device=device, dtype=torch.bfloat16)
    n_frames = int(features.shape[-1] // ACOUSTIC_HOP)
    mask = torch.ones((1, n_frames), dtype=torch.bool, device=device)
    with torch.no_grad():
        return model.get_audio_features(features, mask)


def build_reference_embeddings(reference_wav_path: str):
    """Builder usado pela biblioteca de vozes: tensor CPU + revisão do modelo."""
    entry = _load_native_model("tts_1_5b")
    if entry is None:
        raise RuntimeError("Modelo VibeVoice 1.5B indisponível para extrair embeddings.")
    from services.transcriber import decode_audio_ffmpeg

    waveform = decode_audio_ffmpeg(reference_wav_path, sampling_rate=24000).astype(np.float32)
    embeds = _embeds_from_waveform(entry, waveform)
    return embeds.detach().to("cpu"), get_model_revision("tts_1_5b")


def _embeds_for_voice(entry: Dict[str, Any], model_key: str, voice_id: str):
    """Embeddings da voz (preset SAPI5 ou perfil persistido), no device.

    Cache em memória por identidade real: model_key + revisão do checkpoint +
    voice_id + hash da referência — trocar a gravação ou reconverter o modelo
    invalida automaticamente.
    """
    from services import voice_profiles

    revision = get_model_revision(model_key)
    resolved = voice_profiles.resolve_voice_id(voice_id)

    if voice_profiles.is_preset(resolved):
        cache_key = f"{model_key}:{revision}:{resolved}:sapi5"
        if cache_key not in _voice_embeds_cache:
            speaker_hint = next(p["speaker_hint"] for p in voice_profiles.PRESET_VOICES
                                if p["id"] == resolved)
            waveform = _voice_reference_waveform(speaker_hint)
            if waveform is None:
                raise VoiceUnavailableError(
                    f"Preset {resolved} indisponível (SAPI5 não respondeu). "
                    "Crie uma voz personalizada na biblioteca de vozes."
                )
            _voice_embeds_cache[cache_key] = _embeds_from_waveform(entry, waveform)
            logger.info("Referência do preset %s preparada (%d frames).",
                        resolved, int(_voice_embeds_cache[cache_key].shape[0]))
        return _voice_embeds_cache[cache_key]

    try:
        profile = voice_profiles.get_voice(resolved)
        cache_key = f"{model_key}:{revision}:{resolved}:{profile.get('reference_hash')}"
        if cache_key not in _voice_embeds_cache:
            embeds_cpu = voice_profiles.load_embeddings(resolved)
            _voice_embeds_cache[cache_key] = embeds_cpu.to(
                device=entry["device"], dtype=torch.bfloat16,
            )
            logger.info("Embeddings da voz personalizada carregados (%d frames).",
                        int(_voice_embeds_cache[cache_key].shape[0]))
        return _voice_embeds_cache[cache_key]
    except voice_profiles.VoiceNotFound as exc:
        raise VoiceUnavailableError(str(exc))
    except voice_profiles.InvalidVoice as exc:
        raise VoiceUnavailableError(f"Voz {resolved} sem embeddings válidos: {exc}")


def build_vibevoice_prompt(script: str, pads_by_speaker: "Dict[str, int]") -> str:
    """Monta o prompt EXATAMENTE como o chat_template.jinja do checkpoint:
    system prompt + seção Voice input (pads por locutor) + Text input + início
    da fala. Função pura — coberta por teste unitário."""
    voice_section = ""
    if any(pads_by_speaker.values()):
        voice_section = " Voice input:\n"
        for number, n_pads in pads_by_speaker.items():
            if n_pads > 0:
                voice_section += (
                    f" Speaker {number}:<|vision_start|>"
                    + "<|vision_pad|>" * n_pads
                    + "<|vision_end|>\n"
                )
    text_section = "".join(f" {line}\n" for line in script.splitlines())
    return (
        VIBEVOICE_SYSTEM_PROMPT
        + voice_section
        + " Text input:\n"
        + text_section
        + " Speech output:\n"
        + "<|vision_start|>"
    )


def _frames_cap_for(script: str) -> int:
    # ~7.5 frames/s e ~2.5 palavras/s => ~3 frames/palavra; margem 6x p/ pausas.
    words = max(1, len(script.split()))
    return int(min(4000, max(120, words * 18 + 60)))


def _get_direct_vibevoice_model(model_key: str):
    if model_key not in _direct_model_keys:
        raise ValueError(f"Modelo VibeVoice direto nao suportado: {model_key}")
    if model_key in _direct_models and model_key in _direct_processors:
        return _direct_processors[model_key], _direct_models[model_key]

    model_id = TTS_MODEL_IDS[model_key]
    try:
        from vibevoice.modular.modeling_vibevoice_inference import (
            VibeVoiceForConditionalGenerationInference,
        )
        from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
    except Exception as exc:
        raise LargeModelUnavailableError(
            "VibeVoice-Large indisponivel: dependencia upstream 'vibevoice' incompleta. "
            "Instale a biblioteca VibeVoice em ambiente local compativel ou use o VibeVoice-1.5B."
        ) from exc

    logger.info("Carregando VibeVoice direto (%s). O modelo Large tem cerca de 18.7 GB.", model_id)
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        from services.resource_arbiter import arbiter
        arbiter.prepare_load(model_key)
    model_kwargs = {
        "torch_dtype": torch.bfloat16 if cuda_available else torch.float32,
    }
    if cuda_available:
        model_kwargs["device_map"] = "auto"

    try:
        processor = VibeVoiceProcessor.from_pretrained(model_id)
        model = VibeVoiceForConditionalGenerationInference.from_pretrained(
            model_id,
            **model_kwargs,
        )
    except Exception as exc:
        raise LargeModelUnavailableError(
            f"Erro de carga no VibeVoice-Large ({model_id}): {exc}. "
            "Nenhum fallback foi executado; revise dependencia, cache e estrategia de hardware."
        ) from exc
    if not hasattr(model, "hf_device_map"):
        model = model.to("cuda" if cuda_available else "cpu")
    model.eval()
    if hasattr(model, "set_ddpm_inference_steps"):
        model.set_ddpm_inference_steps(5)

    _direct_processors[model_key] = processor
    _direct_models[model_key] = model
    logger.info("VibeVoice direto carregado: %s", model_id)
    return processor, model


def _speaker_number_from_id(speaker_id: str) -> str:
    match = re.search(r"([0-9]+)$", speaker_id or "")
    number = match.group(1) if match else "1"
    return number if number in {"1", "2", "3", "4"} else "1"


def _speaker_id_for_number(number: str, default_speaker_id: str) -> str:
    if number == "0":
        return default_speaker_id
    if number in {"1", "2", "3", "4"}:
        return f"speaker_{number}"
    raise ValueError("O VibeVoice TTS suporta no maximo 4 vozes por roteiro.")


def _normalize_script_for_vibevoice(text: str, default_speaker_id: str) -> str:
    default_number = _speaker_number_from_id(default_speaker_id)
    normalized_lines: List[str] = []
    current_speaker = default_number

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        match = _voice_line_pattern.match(line)
        if match:
            current_speaker = match.group(1)
            spoken_text = match.group(2).strip()
            _speaker_id_for_number(current_speaker, default_speaker_id)
            if spoken_text:
                normalized_lines.append(f"Speaker {current_speaker}: {spoken_text}")
            continue

        if normalized_lines:
            normalized_lines[-1] = f"{normalized_lines[-1]} {line}"
        else:
            normalized_lines.append(f"Speaker {current_speaker}: {line}")

    if not normalized_lines:
        raise ValueError("Informe um texto para gerar voz.")
    return "\n".join(normalized_lines)


def _unique_speaker_numbers(script: str) -> List[str]:
    speakers: List[str] = []
    seen = set()
    for line in script.splitlines():
        match = _speaker_pattern.match(line.strip())
        if match and match.group(1) not in seen:
            number = match.group(1)
            speakers.append(number)
            seen.add(number)
    if len(speakers) > 4:
        raise ValueError("O VibeVoice TTS suporta no maximo 4 vozes por roteiro.")
    return speakers or ["1"]


def _select_sapi_voice(sapi_voice, speaker_id: str):
    voices = list(sapi_voice.GetVoices())
    if not voices:
        return None

    is_female = speaker_id in {"speaker_2", "speaker_4"}
    preferred_terms = ("Maria", "Zira") if is_female else ("Daniel", "David", "Mark")

    for voice in voices:
        desc = voice.GetDescription()
        if any(term in desc for term in preferred_terms):
            return voice
    for voice in voices:
        desc = voice.GetDescription()
        if "Portuguese" in desc or "Brazil" in desc or "Brasil" in desc:
            return voice
    return voices[0]


def _write_sine_voice_prompt(path: str, speaker_id: str):
    sample_rate = 24000
    duration = 1.4
    frequency = 210 if speaker_id in {"speaker_2", "speaker_4"} else 135
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    envelope = np.sin(np.pi * t / duration)
    signal = (
        np.sin(2 * np.pi * frequency * t)
        + 0.35 * np.sin(2 * np.pi * frequency * 2.0 * t)
        + 0.15 * np.sin(2 * np.pi * frequency * 3.0 * t)
    ) * envelope * 0.45
    wavfile.write(path, sample_rate, (signal * 32767).astype(np.int16))


def _create_voice_prompt_wav(speaker_id: str) -> str:
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    prompt_texts = {
        "speaker_1": "Ola, esta e uma amostra de voz clara, firme e natural.",
        "speaker_2": "Ola, esta e uma amostra de voz suave, clara e natural.",
        "speaker_3": "Ola, esta e uma amostra de voz narrativa, calma e natural.",
        "speaker_4": "Ola, esta e uma amostra de voz dinamica, leve e natural.",
    }
    prompt_text = prompt_texts.get(speaker_id, prompt_texts["speaker_1"])

    try:
        import win32com.client

        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
        selected_voice = _select_sapi_voice(sapi_voice, speaker_id)
        if selected_voice:
            sapi_voice.Voice = selected_voice

        file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
        file_stream.Open(temp_path, 3, False)
        sapi_voice.AudioOutputStream = file_stream
        sapi_voice.Speak(prompt_text)
        file_stream.Close()
    except Exception as exc:
        logger.warning("Nao foi possivel gerar amostra SAPI5; usando amostra sintetica: %s", exc)
        _write_sine_voice_prompt(temp_path, speaker_id)

    return temp_path


def _load_voice_prompt(path: str) -> np.ndarray:
    import librosa
    import soundfile as sf

    voice, sample_rate = sf.read(path)
    if voice.ndim > 1:
        voice = voice.mean(axis=1)
    if sample_rate != 24000:
        voice = librosa.resample(voice.astype(np.float32), orig_sr=sample_rate, target_sr=24000)
    return voice.astype(np.float32)


def _build_voice_samples(script: str, default_speaker_id: str) -> Tuple[List[np.ndarray], List[str]]:
    voice_samples: List[np.ndarray] = []
    temp_paths: List[str] = []

    for speaker_number in _unique_speaker_numbers(script):
        speaker_id = _speaker_id_for_number(speaker_number, default_speaker_id)
        prompt_path = _create_voice_prompt_wav(speaker_id)
        temp_paths.append(prompt_path)
        voice_samples.append(_load_voice_prompt(prompt_path))

    return voice_samples, temp_paths


def _get_model_input_device(model) -> torch.device:
    device_map = getattr(model, "hf_device_map", None)
    if isinstance(device_map, dict):
        for device_name in device_map.values():
            if isinstance(device_name, int):
                return torch.device(f"cuda:{device_name}")
            if isinstance(device_name, str) and device_name not in {"cpu", "disk"}:
                return torch.device(device_name)

    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _move_inputs_to_device(inputs, device: torch.device):
    if hasattr(inputs, "to"):
        try:
            return inputs.to(device)
        except Exception:
            pass
    return {
        key: value.to(device) if isinstance(value, torch.Tensor) else value
        for key, value in inputs.items()
    }


def _apply_speed(audio_array: np.ndarray, speed: float) -> np.ndarray:
    try:
        speed = float(speed)
    except Exception:
        return audio_array
    if abs(speed - 1.0) < 0.02:
        return audio_array

    try:
        import librosa

        return librosa.effects.time_stretch(audio_array.astype(np.float32), rate=max(0.5, min(2.0, speed)))
    except Exception as exc:
        logger.warning("Ajuste de velocidade ignorado: %s", exc)
        return audio_array


def _wav_bytes_from_array(audio_array, sample_rate: int = 24000, speed: float = 1.0) -> bytes:
    if isinstance(audio_array, torch.Tensor):
        audio_array = audio_array.detach().cpu().float().numpy()
    audio_array = np.asarray(audio_array).squeeze()
    audio_array = _apply_speed(audio_array, speed)

    if np.issubdtype(audio_array.dtype, np.floating):
        audio_array = np.nan_to_num(audio_array, nan=0.0, posinf=0.0, neginf=0.0)
        audio_array = np.clip(audio_array, -1.0, 1.0)
        audio_array = (audio_array * 32767).astype(np.int16)
    else:
        audio_array = audio_array.astype(np.int16)

    wav_io = io.BytesIO()
    wavfile.write(wav_io, sample_rate, audio_array)
    return wav_io.getvalue()


def _resolve_speaker_voice_map(
    speaker_numbers: List[str],
    speaker_id: str,
    voice_id: Optional[str],
    speaker_voices: Optional[Dict[str, str]],
) -> Dict[str, str]:
    """Mapeia cada número de speaker do roteiro para um voice_id.

    Prioridade: mapeamento explícito por speaker > voice_id único da request >
    voz padrão da biblioteca. Sem voz real, falha antes da geração.
    """
    from services import voice_profiles

    explicit = {str(k).strip(): v for k, v in (speaker_voices or {}).items() if v}
    default_single = voice_profiles.resolve_voice_id(voice_id) if voice_id else None
    library_default = voice_profiles.get_default_voice_id()

    mapping: Dict[str, str] = {}
    for number in speaker_numbers:
        if number in explicit:
            mapping[number] = voice_profiles.resolve_voice_id(explicit[number])
        elif default_single:
            mapping[number] = default_single
        elif library_default:
            mapping[number] = library_default
        else:
            raise VoiceUnavailableError(
                "Crie, importe ou selecione uma voz real antes de gerar TTS."
            )
        if voice_profiles.is_preset(mapping[number]):
            raise VoiceUnavailableError(
                "Presets Windows não são vozes reais de produção. Crie, importe ou selecione uma voz real."
            )
    return mapping


def _run_native_vibevoice(
    text: str,
    model_key: str,
    speaker_id: str,
    speed: float,
    voice_id: Optional[str] = None,
    speaker_voices: Optional[Dict[str, str]] = None,
    cfg_scale: Optional[float] = None,
    n_diffusion_steps: Optional[int] = None,
    max_frames: int = 0,
    seed: int = -1,
    device_preference: str = "auto",
):
    """Geração nativa: template do checkpoint + condicionamento de voz POR
    LOCUTOR + generate custom do VibeVoice (EOS interno, CFG, diffusion).

    Parâmetros REAIS do caminho 1.5B (auditados em generation_vibevoice.py):
    cfg_scale (mistura CFG), n_diffusion_steps (passos do scheduler),
    max_new_tokens (teto de frames) e seed global do torch (o randn da
    difusão não usa generator próprio). temperature/top_p/top_k/repetition_
    penalty NÃO se aplicam (seleção de token é sempre argmax).

    Levanta VoiceUnavailableError quando a voz escolhida não pode ser usada —
    jamais troca silenciosamente por SAPI5/outra voz.
    """
    from services import voice_profiles

    script = _normalize_script_for_vibevoice(text, speaker_id)
    speaker_numbers = _unique_speaker_numbers(script)
    voice_map = _resolve_speaker_voice_map(speaker_numbers, speaker_id, voice_id, speaker_voices)

    entry = _load_native_model(model_key, device_preference)
    if entry is None:
        return None

    with voice_profiles.voice_in_use(list(voice_map.values())):
        with use_custom_transformers():
            model, processor, device = entry["model"], entry["processor"], entry["device"]

            embeds_per_speaker = []
            pads_by_speaker: Dict[str, int] = {}
            for number in speaker_numbers:
                embeds = _embeds_for_voice(entry, model_key, voice_map[number])
                pads_by_speaker[number] = int(embeds.shape[0])
                embeds_per_speaker.append(embeds)

            prompt = build_vibevoice_prompt(script, pads_by_speaker)
            inputs = processor(text=prompt)
            input_ids = inputs["input_ids"].to(device)
            attention_mask = inputs["attention_mask"].to(device)

            import copy
            run_cfg = copy.deepcopy(entry["gen_cfg"])
            run_cfg.cfg_scale = float(cfg_scale) if cfg_scale else DEFAULT_CFG_SCALE
            if n_diffusion_steps:
                run_cfg.n_diffusion_steps = int(n_diffusion_steps)
            frames_cap = int(max_frames) if max_frames and int(max_frames) > 0 else _frames_cap_for(script)

            generate_kwargs: Dict[str, Any] = dict(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=frames_cap,
                return_dict_in_generate=True,
                generation_config=run_cfg,
            )
            if embeds_per_speaker:
                # O port do fork define get_audio_features mas não o conecta ao
                # generate; o encaixe é feito aqui, no nível de embeddings, nas
                # posições <|vision_pad|> da seção Voice input.
                voice_embeds = torch.cat(embeds_per_speaker, dim=0)
                embed_layer = model.get_input_embeddings()
                inputs_embeds = embed_layer(input_ids).clone()
                pad_positions = input_ids == int(model.config.speech_diffusion_id)
                if int(pad_positions.sum().item()) != int(voice_embeds.shape[0]):
                    raise VoiceUnavailableError(
                        f"Inconsistência no condicionamento de voz: {int(pad_positions.sum().item())} "
                        f"posições vs {int(voice_embeds.shape[0])} embeddings."
                    )
                inputs_embeds[pad_positions] = voice_embeds.to(inputs_embeds.dtype)
                generate_kwargs["inputs_embeds"] = inputs_embeds

            if seed is not None and int(seed) >= 0:
                # O randn da difusão usa o gerador global do torch; semear
                # reproduz o resultado na mesma máquina/device/dtype.
                torch.manual_seed(int(seed))
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(int(seed))

            with torch.no_grad():
                output = model.generate(**generate_kwargs)

    audio_list = getattr(output, "audio", None)
    if not audio_list:
        raise RuntimeError("O generate do VibeVoice não retornou áudio.")
    audio_array = audio_list[0].detach().to(torch.float32).cpu().numpy().squeeze()

    reach_max = getattr(output, "reach_max_step_sample", None)
    truncated = bool(reach_max[0].item()) if reach_max is not None else False
    if truncated:
        logger.warning("Geração atingiu o teto de frames (%d) sem fim de fala; áudio pode estar truncado.",
                       frames_cap)

    engine_label = TTS_MODEL_DISPLAY_NAMES[model_key] + " - voz nativa"
    if entry["device"] == "cpu":
        engine_label += " (CPU, mais lento)"
    result = _voice_result(
        wav_bytes=_wav_bytes_from_array(audio_array, sample_rate=24000, speed=speed),
        engine_key=model_key,
        engine_label=engine_label,
        fallback=False,
    )
    result["voice_map"] = voice_map
    result["params_used"] = {
        "cfg_scale": run_cfg.cfg_scale,
        "n_diffusion_steps": getattr(run_cfg, "n_diffusion_steps", None),
        "max_frames": frames_cap,
        "seed": int(seed) if seed is not None and int(seed) >= 0 else None,
        "device": entry["device"],
        "speed": speed,
        "truncated": truncated,
    }
    return result


def _run_direct_vibevoice(
    text: str,
    model_key: str,
    speaker_id: str,
    temperature: float,
    top_p: float,
    top_k: int,
    repetition_penalty: float,
    speed: float,
) -> Dict[str, Any]:
    _preflight_direct_vibevoice_model(model_key)
    processor, model = _get_direct_vibevoice_model(model_key)
    script = _normalize_script_for_vibevoice(text, speaker_id)
    voice_samples, temp_paths = _build_voice_samples(script, speaker_id)

    try:
        inputs = processor(
            text=[script],
            voice_samples=[voice_samples],
            padding=True,
            return_tensors="pt",
            return_attention_mask=True,
        )
        inputs = _move_inputs_to_device(inputs, _get_model_input_device(model))

        generation_config: Dict[str, Any] = {"do_sample": bool(temperature > 0)}
        if temperature > 0:
            generation_config["temperature"] = temperature
            generation_config["top_p"] = top_p
            generation_config["top_k"] = top_k
        if repetition_penalty and repetition_penalty != 1.0:
            generation_config["repetition_penalty"] = repetition_penalty

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=None,
                cfg_scale=1.3,
                tokenizer=processor.tokenizer,
                generation_config=generation_config,
                verbose=False,
            )

        if not getattr(outputs, "speech_outputs", None) or outputs.speech_outputs[0] is None:
            raise RuntimeError("O VibeVoice nao retornou audio.")
        return _voice_result(
            wav_bytes=_wav_bytes_from_array(outputs.speech_outputs[0], sample_rate=24000, speed=speed),
            engine_key=model_key,
            engine_label=TTS_MODEL_DISPLAY_NAMES[model_key],
            fallback=False,
        )
    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass


def generate_voice_1_5b(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
    speed: float = 1.0,
    model_key: str = "tts_1_5b",
) -> bytes:
    """
    Gera audio WAV para os modelos long-form:
    - tts_1_5b: microsoft/VibeVoice-1.5B via Transformers pipeline.
    - tts_large: aoi-ot/VibeVoice-Large via biblioteca upstream vibevoice.
    """
    return generate_voice_1_5b_with_metadata(
        text=text,
        speaker_id=speaker_id,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        speed=speed,
        model_key=model_key,
    )["wav_bytes"]


def generate_voice_1_5b_with_metadata(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
    speed: float = 1.0,
    model_key: str = "tts_1_5b",
    voice_id: Optional[str] = None,
    speaker_voices: Optional[Dict[str, str]] = None,
    cfg_scale: Optional[float] = None,
    n_diffusion_steps: Optional[int] = None,
    max_frames: int = 0,
    seed: int = -1,
    failure_policy: str = "cpu",
    device: str = "auto",
) -> Dict[str, Any]:
    """Geração TTS 1.5B.

    temperature/top_p/top_k/repetition_penalty são aceitos por compatibilidade,
    mas NÃO afetam o caminho nativo do 1.5B (seleção de token é argmax; a
    aleatoriedade real é a difusão, controlada por seed/n_diffusion_steps).

    failure_policy: "fail" (sem retry/fallback) ou "cpu" (tenta CPU quando a
    GPU falha, mantendo a mesma engine). Voz personalizada inválida sempre é
    erro — nunca é trocada silenciosamente.
    """
    if model_key not in TTS_MODEL_IDS:
        raise ValueError(f"Modelo TTS invalido: {model_key}")
    if not text or not text.strip():
        raise ValueError("Informe um texto para gerar voz.")
    if failure_policy not in ("fail", "cpu"):
        raise ValueError(f"failure_policy inválida: {failure_policy}")

    from services.tts_orchestration import orchestrate_tts
    orchestration_max_segment_chars = 320 if model_key == "chatterbox-tts-pt-br" else 500
    tts_plan = orchestrate_tts(
        text,
        default_speaker_id=speaker_id,
        speaker_voices=speaker_voices,
        max_segment_chars=orchestration_max_segment_chars,
    )
    text = tts_plan.engine_script

    if model_key == "tts_large":
        return _run_direct_vibevoice(
            text=text,
            model_key=model_key,
            speaker_id=speaker_id,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            speed=speed,
        )

    if model_key == "chatterbox-tts-pt-br":
        from services.chatterbox_adapter import chatterbox_engine
        return chatterbox_engine.generate_voice_chatterbox(
            text=text,
            voice_id=voice_id,
            speaker_voices=speaker_voices,
            speaker_id=speaker_id,
            speed=speed,
            segment_texts=[segment.text for segment in tts_plan.segments if segment.text],
        )

    if device != "auto":
        device_preference = device
    elif failure_policy == "fail":
        # "fail" = sem retry implícito em CPU: usa só o melhor device disponível.
        device_preference = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device_preference = "auto"

    native_error: Optional[str] = None
    try:
        native_result = _run_native_vibevoice(
            text=text, model_key=model_key, speaker_id=speaker_id, speed=speed,
            voice_id=voice_id, speaker_voices=speaker_voices,
            cfg_scale=cfg_scale, n_diffusion_steps=n_diffusion_steps,
            max_frames=max_frames, seed=seed, device_preference=device_preference,
        )
        if native_result:
            return native_result
        native_error = "modelo VibeVoice 1.5B não pôde ser carregado (ver logs)."
    except VoiceUnavailableError:
        # Voz escolhida indisponível: erro claro, NUNCA trocar de voz.
        raise
    except Exception as exc:
        logger.error("Erro na geração nativa VibeVoice: %s", exc, exc_info=True)
        native_error = str(exc)

    raise RuntimeError(
        f"Falha na geração com o VibeVoice 1.5B: {native_error} "
        f"(política '{failure_policy}' — sem fallback automático)."
    )


def unload_tts_model():
    if _native_models or _direct_models:
        logger.info("Descarregando modelos VibeVoice TTS...")
    _native_models.clear()
    _voice_embeds_cache.clear()
    _direct_processors.clear()
    _direct_models.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# Registro no árbitro de VRAM (ver services/resource_arbiter.py).
# O unload é compartilhado: descarregar qualquer um dos dois limpa ambos os
# caches (são o mesmo módulo e raramente coexistem em 6GB).
from services.resource_arbiter import arbiter as _arbiter

_arbiter.register_engine(
    engine="tts_1_5b",
    label="VibeVoice TTS 1.5B",
    is_loaded=lambda: "tts_1_5b" in _native_models,
    unload=unload_tts_model,
    est_vram_mb=lambda: 5400.0,
    current_model=lambda: TTS_MODEL_IDS["tts_1_5b"],
)
_arbiter.register_engine(
    engine="tts_large",
    label="VibeVoice TTS Large",
    is_loaded=lambda: "tts_large" in _direct_models,
    unload=unload_tts_model,
    est_vram_mb=lambda: 19000.0,
    current_model=lambda: TTS_MODEL_IDS["tts_large"],
)

# Registra o builder de embeddings na biblioteca de vozes (import tardio no
# voice_profiles evita ciclo; este módulo é o único dono do modelo 1.5B).
from services import voice_profiles as _voice_profiles

_voice_profiles.set_embedding_builder(build_reference_embeddings,
                                      lambda: get_model_revision("tts_1_5b"))

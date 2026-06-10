import sys
import os
import gc
import io
import logging
import re
import tempfile
from typing import Any, Dict, List, Tuple

import numpy as np
import scipy.io.wavfile as wavfile
import torch

from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()

from services.transformers_loader import use_custom_transformers

with use_custom_transformers():
    from transformers import pipeline, AutoConfig, AutoModelForTextToWaveform
    from transformers.models.vibevoice_acoustic_tokenizer.configuration_vibevoice_acoustic_tokenizer import VibeVoiceAcousticTokenizerConfig
    VibeVoiceAcousticTokenizerConfig.decoder_depths = VibeVoiceAcousticTokenizerConfig.decoder_depths.setter(lambda self, val: None)



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.VibeVoiceTTS")

TTS_MODEL_IDS = {
    "tts_1_5b": "microsoft/VibeVoice-1.5B",
    "tts_large": "aoi-ot/VibeVoice-Large",
}
TTS_MODEL_DISPLAY_NAMES = {
    "tts_1_5b": "VibeVoice-TTS-1.5B (microsoft/VibeVoice-1.5B)",
    "tts_large": "VibeVoice-Large (aoi-ot/VibeVoice-Large)",
}
SUPPORTED_LONGFORM_TTS_MODELS = set(TTS_MODEL_IDS)

_pipeline_model_keys = {"tts_1_5b"}
_direct_model_keys = {"tts_large"}

_tts_pipelines: Dict[str, Any] = {}
_direct_processors: Dict[str, Any] = {}
_direct_models: Dict[str, Any] = {}

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
    """Backwards-compatible helper for the Transformers TTS pipeline."""
    return _get_transformers_pipeline(model_key)


def _get_transformers_pipeline(model_key: str):
    if model_key not in _pipeline_model_keys:
        return None
    if model_key in _tts_pipelines:
        return _tts_pipelines[model_key]

    model_id = TTS_MODEL_IDS[model_key]
    try:
        if torch.cuda.is_available():
            from services.resource_arbiter import arbiter
            arbiter.prepare_load(model_key)
        with use_custom_transformers():
            from transformers import pipeline

            device = 0 if torch.cuda.is_available() else -1
            pipeline_kwargs = {
                "task": "text-to-speech",
                "model": model_id,
                "device": device,
                "trust_remote_code": True,
            }
            if torch.cuda.is_available():
                pipeline_kwargs["torch_dtype"] = torch.bfloat16

            logger.info("Carregando pipeline VibeVoice TTS (%s)...", model_id)
            _tts_pipelines[model_key] = pipeline(**pipeline_kwargs)
            logger.info("Pipeline VibeVoice TTS carregada: %s", model_id)
            return _tts_pipelines[model_key]
    except Exception as exc:
        logger.warning("Nao foi possivel carregar a pipeline %s: %s", model_id, exc)
        return None


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
        raise RuntimeError(
            "O VibeVoice-Large usa a biblioteca upstream 'vibevoice'. "
            "Instale-a em um ambiente local compativel ou use o VibeVoice-1.5B/Realtime-0.5B."
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

    processor = VibeVoiceProcessor.from_pretrained(model_id)
    model = VibeVoiceForConditionalGenerationInference.from_pretrained(
        model_id,
        **model_kwargs,
    )
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


def _run_transformers_pipeline(
    text: str,
    model_key: str,
    speed: float,
):
    tts_pipeline = _get_transformers_pipeline(model_key)
    if tts_pipeline is None:
        return None

    model_id = TTS_MODEL_IDS[model_key]
    try:
        with use_custom_transformers():
            output = tts_pipeline(text)
        if not isinstance(output, dict):
            raise RuntimeError("A pipeline TTS retornou um formato inesperado.")
        audio_array = output.get("audio")
        if audio_array is None:
            audio_array = output.get("waveform")
        if audio_array is None:
            raise RuntimeError("A pipeline TTS nao retornou audio.")
        sample_rate = output.get("sampling_rate") or output.get("sample_rate") or 24000
        return _voice_result(
            wav_bytes=_wav_bytes_from_array(audio_array, sample_rate=sample_rate, speed=speed),
            engine_key=model_key,
            engine_label=TTS_MODEL_DISPLAY_NAMES[model_key],
            fallback=False,
        )
    except Exception as exc:
        logger.error("Erro na pipeline VibeVoice TTS (%s): %s", model_id, exc)
        return None


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


def _fallback_sapi_or_sine(text: str, speaker_id: str, speed: float) -> Dict[str, Any]:
    logger.info("Executando fallback SAPI5 do Windows para sintese de voz.")
    try:
        import win32com.client

        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
        selected_voice = _select_sapi_voice(sapi_voice, speaker_id)
        if selected_voice:
            sapi_voice.Voice = selected_voice

        sapi_rate = int((float(speed) - 1.0) * 8.0)
        sapi_voice.Rate = max(-10, min(10, sapi_rate))

        fd, temp_wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
        file_stream.Open(temp_wav_path, 3, False)
        sapi_voice.AudioOutputStream = file_stream
        sapi_voice.Speak(text)
        file_stream.Close()

        with open(temp_wav_path, "rb") as wav_file:
            wav_bytes = wav_file.read()

        try:
            os.remove(temp_wav_path)
        except OSError:
            pass
        return _voice_result(
            wav_bytes=wav_bytes,
            engine_key="windows_sapi5",
            engine_label="Windows SAPI5 (fallback offline)",
            fallback=True,
        )
    except Exception as exc:
        logger.error("Erro ao usar SAPI5: %s. Usando fallback senoidal.", exc)

    sample_rate = 24000
    duration = max(2.0, min(15.0, len(text) * 0.08))
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    freq_carrier = 210 if speaker_id in {"speaker_2", "speaker_4"} else 120
    envelope = np.sin(np.pi * t / duration) ** 0.5
    signal = np.sin(2 * np.pi * freq_carrier * t)
    signal += 0.5 * np.sin(2 * np.pi * (freq_carrier * 2) * t)
    signal += 0.25 * np.sin(2 * np.pi * (freq_carrier * 3) * t)
    signal = signal * (0.5 * (1.0 + np.sin(2 * np.pi * 5 * t))) * envelope
    signal = signal / max(0.001, np.max(np.abs(signal)))
    return _voice_result(
        wav_bytes=_wav_bytes_from_array(signal, sample_rate=sample_rate, speed=speed),
        engine_key="synthetic_tone",
        engine_label="Sintese senoidal (fallback tecnico)",
        fallback=True,
    )


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
) -> Dict[str, Any]:
    if model_key not in TTS_MODEL_IDS:
        raise ValueError(f"Modelo TTS invalido: {model_key}")
    if not text or not text.strip():
        raise ValueError("Informe um texto para gerar voz.")

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

    pipeline_result = _run_transformers_pipeline(text=text, model_key=model_key, speed=speed)
    if pipeline_result:
        return pipeline_result

    return _fallback_sapi_or_sine(text=text, speaker_id=speaker_id, speed=speed)


def unload_tts_model():
    if _tts_pipelines or _direct_models:
        logger.info("Descarregando modelos VibeVoice TTS...")
    _tts_pipelines.clear()
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
    is_loaded=lambda: "tts_1_5b" in _tts_pipelines,
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

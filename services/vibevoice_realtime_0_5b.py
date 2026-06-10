import sys
import os
import gc
import torch

from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()

from services.transformers_loader import use_custom_transformers

with use_custom_transformers():
    from transformers import pipeline, AutoConfig, AutoModelForTextToWaveform
    from transformers.models.vibevoice_acoustic_tokenizer.configuration_vibevoice_acoustic_tokenizer import VibeVoiceAcousticTokenizerConfig
    VibeVoiceAcousticTokenizerConfig.decoder_depths = VibeVoiceAcousticTokenizerConfig.decoder_depths.setter(lambda self, val: None)


import logging
import numpy as np
import scipy.io.wavfile as wavfile
from typing import Dict, Any, Generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.VibeVoiceRealtime05B")

# Cache global da pipeline
_rt_pipeline = None
_model_id = "microsoft/VibeVoice-Realtime-0.5B"


def _engine_metadata(engine_key: str, engine_label: str, fallback: bool) -> Dict[str, Any]:
    return {
        "engine_key": engine_key,
        "engine_label": engine_label,
        "fallback": fallback,
    }


def get_rt_model_and_processor():
    """
    Carrega o VibeVoice-Realtime-0.5B via pipeline do Transformers quando disponível.
    """
    global _rt_pipeline
    
    if _rt_pipeline is not None:
        return _rt_pipeline
        
    try:
        if torch.cuda.is_available():
            from services.resource_arbiter import arbiter
            arbiter.prepare_load("tts_realtime")
        with use_custom_transformers():
            from transformers import pipeline
            device = 0 if torch.cuda.is_available() else -1
            logger.info(f"Carregando pipeline VibeVoice-Realtime-0.5B ({_model_id})...")
            _rt_pipeline = pipeline(
                "text-to-speech",
                model=_model_id,
                device=device,
                trust_remote_code=True,
            )
            logger.info("Pipeline VibeVoice-Realtime-0.5B carregada com sucesso!")
            return _rt_pipeline
    except Exception as e:
        logger.warning(f"Erro ao carregar pipeline VibeVoice-Realtime-0.5B (usando fallback offline de streaming): {e}")
        return None

def generate_voice_stream_0_5b(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0,
    status_callback=None
) -> Generator[bytes, None, None]:
    """
    Gera blocos de áudio PCM brutos (Raw PCM 16-bit, 24kHz) via gerador/streaming.
    Excelente para baixa latência.
    """
    rt_pipeline = get_rt_model_and_processor()
    
    # Se a pipeline existir, gera o áudio e entrega em blocos PCM.
    if rt_pipeline is not None:
        try:
            with use_custom_transformers():
                output = rt_pipeline(text)
            audio_array = output.get("audio")
            if audio_array is None:
                audio_array = output.get("waveform")
            if audio_array is None:
                raise RuntimeError("A pipeline realtime não retornou áudio.")
            audio_array = np.asarray(audio_array).squeeze()
            if np.issubdtype(audio_array.dtype, np.floating):
                audio_array = np.clip(audio_array, -1.0, 1.0)
                audio_array = (audio_array * 32767).astype(np.int16)
            else:
                audio_array = audio_array.astype(np.int16)
            if status_callback:
                status_callback(_engine_metadata(
                    "realtime_0_5b",
                    "VibeVoice-Realtime-0.5B (microsoft/VibeVoice-Realtime-0.5B)",
                    False
                ))
            pcm_bytes = audio_array.tobytes()
            chunk_size = 8192
            for i in range(0, len(pcm_bytes), chunk_size):
                yield pcm_bytes[i:i + chunk_size]
            return
        except Exception as e:
            logger.error(f"Erro na pipeline VibeVoice-Realtime-0.5B: {e}")
            
    # Fallback: Voz real e fluída utilizando o SAPI5 nativo do Windows em tempo real
    logger.info("Executando fallback SAPI5 do Windows para streaming de voz (Realtime-0.5B)...")
    try:
        import win32com.client
        
        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
        
        # Filtra a voz com base na seleção
        selected_voice = None
        voices = sapi_voice.GetVoices()
        is_female = speaker_id in ["speaker_2", "speaker_4"]
        
        for voice in voices:
            desc = voice.GetDescription()
            if "Portuguese" in desc or "Maria" in desc:
                selected_voice = voice
            elif not selected_voice:
                selected_voice = voice
                
        if is_female:
            for voice in voices:
                desc = voice.GetDescription()
                if "Maria" in desc or "Zira" in desc:
                    selected_voice = voice
                    break
        else:
            for voice in voices:
                desc = voice.GetDescription()
                if "Maria" not in desc and "Zira" not in desc:
                    selected_voice = voice
                    break
                    
        if selected_voice:
            sapi_voice.Voice = selected_voice
            
        sapi_rate = int((speed - 1.0) * 8.0)
        sapi_voice.Rate = max(-10, min(10, sapi_rate))
        if status_callback:
            status_callback(_engine_metadata(
                "windows_sapi5",
                "Windows SAPI5 (fallback offline)",
                True
            ))
        
        # Gera o áudio por frases ou parágrafos para simular streaming/baixa latência de retorno
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            mem_stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
            # 30 = SPSF_24kHz16BitMono
            mem_stream.Format.Type = 30
            sapi_voice.AudioOutputStream = mem_stream
            sapi_voice.Speak(sentence)
            
            # Obtém os bytes PCM do stream de memória
            pcm_data = bytes(mem_stream.GetData())
            
            # Envia em chunks menores de 8KB (para simular streaming de tempo real com baixa latência)
            chunk_size = 8192
            for i in range(0, len(pcm_data), chunk_size):
                yield pcm_data[i:i+chunk_size]
        return
        
    except Exception as e:
        logger.error(f"Erro ao usar streaming SAPI5: {e}. Usando fallback senoidal...")
        
    sample_rate = 24000
    
    # Geramos blocos curtos simulando cada palavra falada
    words = text.split(" ")
    freq_carrier = 135
    if speaker_id in ["speaker_2", "speaker_4"]:
        freq_carrier = 220
    if status_callback:
        status_callback(_engine_metadata(
            "synthetic_tone",
            "Sintese senoidal (fallback tecnico)",
            True
        ))
        
    for word in words:
        if not word:
            continue
        # Tamanho do bloco correspondente ao tamanho da palavra
        chunk_duration = max(0.2, min(0.6, len(word) * 0.08))
        num_samples = int(sample_rate * chunk_duration)
        t = np.linspace(0, chunk_duration, num_samples, endpoint=False)
        
        # Onda senoidal simples com modulação humana para voz simulada
        envelope = np.sin(np.pi * t / chunk_duration)
        signal = np.sin(2 * np.pi * freq_carrier * t) + 0.3 * np.sin(2 * np.pi * (freq_carrier * 2.1) * t)
        signal = signal * envelope * 0.7
        
        # Converte para PCM 16-bit bruto
        pcm_bytes = (signal * 32767).astype(np.int16).tobytes()
        yield pcm_bytes

def generate_voice_realtime_wav(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0
) -> bytes:
    """Gera um WAV completo a partir do mesmo motor realtime usado no WebSocket."""
    return generate_voice_realtime_wav_with_metadata(
        text=text,
        speaker_id=speaker_id,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repetition_penalty=repetition_penalty,
        speed=speed
    )["wav_bytes"]


def generate_voice_realtime_wav_with_metadata(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0
) -> Dict[str, Any]:
    """Gera WAV completo e informa qual motor realmente produziu o audio."""
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
        status_callback=capture_engine
    ))
    audio = np.frombuffer(pcm_bytes, dtype=np.int16)
    import io
    wav_io = io.BytesIO()
    wavfile.write(wav_io, 24000, audio)
    return {
        "wav_bytes": wav_io.getvalue(),
        "engine_key": engine_info.get("engine_key", "realtime_0_5b"),
        "engine_label": engine_info.get(
            "engine_label",
            "VibeVoice-Realtime-0.5B (microsoft/VibeVoice-Realtime-0.5B)"
        ),
        "fallback": bool(engine_info.get("fallback", False)),
    }

def unload_realtime_model():
    global _rt_pipeline
    if _rt_pipeline is not None:
        logger.info("Descarregando VibeVoice-Realtime-0.5B...")
        _rt_pipeline = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Registro no árbitro de VRAM (ver services/resource_arbiter.py)
from services.resource_arbiter import arbiter as _arbiter

_arbiter.register_engine(
    engine="tts_realtime",
    label="VibeVoice Realtime 0.5B",
    is_loaded=lambda: _rt_pipeline is not None,
    unload=unload_realtime_model,
    est_vram_mb=lambda: 1500.0,
    current_model=lambda: _model_id,
)

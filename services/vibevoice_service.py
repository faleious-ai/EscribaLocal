import os
import gc
import torch

from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()

import logging
from typing import Dict, Any, List, Generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.VibeVoice")

# Cache global do modelo
_vibevoice_model = None
_vibevoice_processor = None
_vibevoice_model_id = "microsoft/VibeVoice-ASR-HF"

def get_vibevoice_model_and_processor():
    """
    Carrega o modelo VibeVoice-ASR-HF de forma otimizada para o hardware do usuário.
    Usa BitsAndBytesConfig para carregar em 4-bit (NF4) com exclusão de módulos
    de codificação de áudio para não quebrar a diarização.
    """
    global _vibevoice_model, _vibevoice_processor
    
    if _vibevoice_model is not None and _vibevoice_processor is not None:
        logger.info("Usando VibeVoice em cache.")
        return _vibevoice_model, _vibevoice_processor

    from services.transformers_loader import use_standard_transformers

    with use_standard_transformers():
        from transformers import AutoProcessor, VibeVoiceAsrForConditionalGeneration
        from services.model_manager import get_hf_cache_dir

        logger.info(f"Carregando VibeVoice-ASR-HF ({_vibevoice_model_id})...")
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            from services.resource_arbiter import arbiter
            arbiter.prepare_load("vibevoice_asr")
        model_dtype = torch.bfloat16 if cuda_available else torch.float32
        model_kwargs = {
            "torch_dtype": model_dtype,
            "trust_remote_code": True,
        }

        if cuda_available:
            model_kwargs["device_map"] = "cuda"
            try:
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                    llm_int8_enable_fp32_cpu_offload=True,
                )
            except Exception as quant_err:
                logger.warning(f"Quantização 4-bit indisponível; carregando VibeVoice sem quantização: {quant_err}")

        hf_cache_dir = str(get_hf_cache_dir())
        _vibevoice_processor = AutoProcessor.from_pretrained(
            _vibevoice_model_id,
            trust_remote_code=True,
            cache_dir=hf_cache_dir,
        )
        _vibevoice_model = VibeVoiceAsrForConditionalGeneration.from_pretrained(
            _vibevoice_model_id,
            cache_dir=hf_cache_dir,
            **model_kwargs
        )
        if not cuda_available:
            _vibevoice_model = _vibevoice_model.to("cpu")
        _vibevoice_model.eval()
        logger.info("VibeVoice carregado com sucesso!")
        return _vibevoice_model, _vibevoice_processor

def _get_model_device_and_dtype(model):
    try:
        param = next(model.parameters())
        return param.device, param.dtype
    except StopIteration:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu"), torch.bfloat16 if torch.cuda.is_available() else torch.float32

def _tokenizer_chunk_size_from_seconds(seconds: float, sampling_rate: int) -> int:
    # O VibeVoice ASR recomenda múltiplos do hop length 3200 para reduzir uso de memória.
    hop_length = 3200
    samples = max(hop_length, int(float(seconds) * sampling_rate))
    return max(hop_length, (samples // hop_length) * hop_length)

def _normalize_parsed_output(parsed_output, diarization: bool, duration: float) -> List[Dict[str, Any]]:
    if isinstance(parsed_output, list) and parsed_output:
        parsed_output = parsed_output[0]

    if isinstance(parsed_output, str):
        text = parsed_output.strip()
        return [{
            "start": 0.0,
            "end": duration,
            "speaker": "Principal" if diarization else None,
            "text": text
        }] if text else []

    normalized = []
    if isinstance(parsed_output, list):
        for seg in parsed_output:
            if isinstance(seg, dict):
                text = str(seg.get("Content", "")).strip()
                if not text or text.lower() == "[silence]":
                    continue
                normalized.append({
                    "start": float(seg.get("Start", 0.0)),
                    "end": float(seg.get("End", 0.0)),
                    "speaker": str(seg.get("Speaker", "Desconhecido")) if diarization else None,
                    "text": text
                })
            elif isinstance(seg, str):
                text = seg.strip()
                if text:
                    normalized.append({
                        "start": 0.0,
                        "end": duration,
                        "speaker": "Principal" if diarization else None,
                        "text": text
                    })
    return normalized

def unload_vibevoice_model():
    """Descarrega o modelo VibeVoice para liberar RAM/VRAM."""
    global _vibevoice_model, _vibevoice_processor
    if _vibevoice_model is not None:
        logger.info("Descarregando VibeVoice para liberar memória...")
        _vibevoice_model = None
        _vibevoice_processor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


# Registro no árbitro de VRAM (ver services/resource_arbiter.py)
from services.resource_arbiter import arbiter as _arbiter

_arbiter.register_engine(
    engine="vibevoice_asr",
    label="VibeVoice ASR (diarização)",
    is_loaded=lambda: _vibevoice_model is not None,
    unload=unload_vibevoice_model,
    est_vram_mb=lambda: 4500.0,  # NF4 4-bit do modelo ~7B
    current_model=lambda: _vibevoice_model_id,
)

def transcribe_vibevoice_generator(
    file_path: str,
    prompt: str = None,
    diarization: bool = True,
    chunk_length_seconds: float = 45.0,
    temperature: float = 0.0,
    repetition_penalty: float = 1.1,
    top_p: float = 1.0,
    top_k: int = 50,
    num_beams: int = 1,
    max_new_tokens: int = 2048,
    cancel_event=None
) -> Generator[Dict[str, Any], None, None]:
    """
    Transcreve um arquivo de áudio usando o fluxo oficial do VibeVoice ASR:
    pedido único, diarização/timestamps preservados e chunking interno do tokenizer.

    `cancel_event` (threading.Event) habilita cancelamento cooperativo: como o
    generate é uma chamada única e longa, o evento é checado a cada passo de
    decodificação via StoppingCriteria; a saída parcial é descartada.
    """
    from services.transcriber import decode_audio_ffmpeg

    def _is_cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    model, processor = None, None
    yield {"type": "status", "message": "Carregando ou baixando o modelo VibeVoice ASR... (Isso pode levar alguns minutos na primeira execução)"}
    model, processor = get_vibevoice_model_and_processor()

    if _is_cancelled():
        yield {"type": "cancelled", "message": "Tarefa cancelada após o carregamento do modelo."}
        return
    target_device, target_dtype = _get_model_device_and_dtype(model)
    yield {
        "type": "model_status",
        "caption": "Modelo em uso",
        "engine_key": "vibevoice_asr",
        "engine_label": f"VibeVoice-ASR ({_vibevoice_model_id})",
        "device": str(target_device),
        "compute_type": str(target_dtype).replace("torch.", ""),
        "fallback": False,
    }

    # Obtém a taxa de amostragem esperada pelo processador
    sr = 24000
    if hasattr(processor, "feature_extractor") and hasattr(processor.feature_extractor, "sampling_rate"):
        sr = processor.feature_extractor.sampling_rate
    elif hasattr(processor, "sampling_rate"):
        sr = processor.sampling_rate

    yield {"type": "status", "message": "Decodificando áudio via FFmpeg..."}
    audio_data = decode_audio_ffmpeg(file_path, sampling_rate=sr)

    if _is_cancelled():
        yield {"type": "cancelled", "message": "Tarefa cancelada antes da transcrição."}
        return

    duration = len(audio_data) / sr if sr else 0.0
    yield {"type": "meta", "language": "auto", "language_probability": 1.0, "duration": duration}
    yield {"type": "status", "message": "Transcrevendo com VibeVoice ASR em passagem única..."}

    from services.transformers_loader import use_standard_transformers

    with use_standard_transformers():
        inputs = processor.apply_transcription_request(audio=audio_data, prompt=prompt)
        inputs.pop("tokenizer_chunk_size", None)
        
        if hasattr(inputs, "to"):
            inputs = inputs.to(target_device, target_dtype)
        else:
            inputs = {
                k: v.to(target_device, dtype=target_dtype) if isinstance(v, torch.Tensor) and torch.is_floating_point(v)
                else (v.to(target_device) if isinstance(v, torch.Tensor) else v)
                for k, v in inputs.items()
            }

        generation_kwargs = {
            "max_new_tokens": max_new_tokens,
            "num_beams": num_beams,
            "acoustic_tokenizer_chunk_size": _tokenizer_chunk_size_from_seconds(chunk_length_seconds, sr),
        }
        if temperature > 0.0:
            generation_kwargs["do_sample"] = True
            generation_kwargs["temperature"] = temperature
            if top_p < 1.0:
                generation_kwargs["top_p"] = top_p
            if top_k > 0:
                generation_kwargs["top_k"] = top_k
        else:
            generation_kwargs["do_sample"] = False

        if repetition_penalty != 1.0:
            generation_kwargs["repetition_penalty"] = repetition_penalty

        if cancel_event is not None:
            from transformers import StoppingCriteria, StoppingCriteriaList

            class _CancelGeneration(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs) -> bool:
                    return cancel_event.is_set()

            generation_kwargs["stopping_criteria"] = StoppingCriteriaList([_CancelGeneration()])

        with torch.no_grad():
            output_ids = model.generate(**inputs, **generation_kwargs)

        if _is_cancelled():
            # Saída parcial de um generate interrompido é inconsistente; descarta.
            yield {"type": "cancelled", "message": "Transcrição cancelada pelo usuário durante a geração."}
            return

        input_ids_length = inputs["input_ids"].shape[1]
        generated_ids = output_ids[:, input_ids_length:]
        decode_format = "parsed" if diarization else "transcription_only"
        parsed_output = processor.decode(generated_ids, return_format=decode_format)
        full_transcript = _normalize_parsed_output(parsed_output, diarization, duration)

    total_segments = max(1, len(full_transcript))
    for idx, seg in enumerate(full_transcript, 1):
        yield {
            "type": "progress",
            "progress": round((idx / total_segments) * 100.0, 1),
            "segment": seg
        }

    logger.info(f"Transcrição VibeVoice concluída com {len(full_transcript)} segmentos.")
    yield {"type": "done", "full_transcript": full_transcript}

import os
import gc
import torch
if not hasattr(torch, "float8_e8m0fnu"):
    setattr(torch, "float8_e8m0fnu", torch.float32)

try:
    import bitsandbytes as bnb
    original_new = bnb.nn.Params4bit.__new__
    def patched_new(cls, *args, **kwargs):
        kwargs.pop('_is_hf_initialized', None)
        return original_new(cls, *args, **kwargs)
    bnb.nn.Params4bit.__new__ = patched_new
except Exception as e:
    pass
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

    from transformers import AutoProcessor, VibeVoiceAsrForConditionalGeneration, BitsAndBytesConfig

    logger.info(f"Carregando VibeVoice-ASR-HF ({_vibevoice_model_id})...")
    
    # 1. Configurar quantização seletiva NF4 de 4 bits para a RTX 3050 (6GB VRAM)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        llm_int8_enable_fp32_cpu_offload=True,
        # Pulamos a quantização de camadas sensíveis de áudio para preservar a diarização/transcrição
        llm_int8_skip_modules=[
            "acoustic_tokenizer_encoder",
            "semantic_tokenizer_encoder",
            "acoustic_projection",
            "semantic_projection",
            "lm_head",
        ]
    )    # 2. Carregar o processador
    _vibevoice_processor = AutoProcessor.from_pretrained(_vibevoice_model_id, trust_remote_code=True)
    # 3. Carregar o modelo com device_map="cuda"
    _vibevoice_model = VibeVoiceAsrForConditionalGeneration.from_pretrained(
        _vibevoice_model_id,
        quantization_config=bnb_config,
        device_map="cuda",
        torch_dtype=torch.float16,
        low_cpu_mem_usage=False,
        trust_remote_code=True
    )
    logger.info("VibeVoice carregado com sucesso!")
    return _vibevoice_model, _vibevoice_processor

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
    max_new_tokens: int = 2048
) -> Generator[Dict[str, Any], None, None]:
    """
    Transcreve um arquivo de áudio utilizando VibeVoice ASR dividindo o áudio
    em fatias gerenciáveis para evitar gargalos de prefill e memória,
    gerando atualizações de progresso e streaming de tokens de texto.
    """
    import math
    from threading import Thread
    from transformers import TextIteratorStreamer
    from services.transcriber import decode_audio_ffmpeg

    model, processor = None, None
    yield {"type": "status", "message": "Carregando ou baixando o modelo VibeVoice (5.5 GB) na placa de vídeo... (Isso pode levar alguns minutos na primeira execução)"}
    model, processor = get_vibevoice_model_and_processor()
    
    # Obtém a taxa de amostragem esperada pelo processador
    sr = 16000
    if hasattr(processor, "feature_extractor") and hasattr(processor.feature_extractor, "sampling_rate"):
        sr = processor.feature_extractor.sampling_rate
    elif hasattr(processor, "sampling_rate"):
        sr = processor.sampling_rate
        
    yield {"type": "status", "message": "Decodificando áudio via FFmpeg..."}
    audio_data = decode_audio_ffmpeg(file_path, sampling_rate=sr)
    
    # Configura o tamanho de cada fatia dinamicamente
    chunk_samples = int(chunk_length_seconds * sr)
    total_samples = len(audio_data)
    total_chunks = math.ceil(total_samples / chunk_samples)
    
    logger.info(f"Iniciando transcrição VibeVoice com chunking: {total_chunks} fatias de {chunk_length_seconds}s.")
    
    full_transcript = []
    
    for chunk_idx in range(total_chunks):
        start_sample = chunk_idx * chunk_samples
        end_sample = min((chunk_idx + 1) * chunk_samples, total_samples)
        
        # Ignora fatias vazias ou extremamente curtas (menores que 0.5 segundos)
        if (end_sample - start_sample) < (0.5 * sr):
            continue
            
        chunk_data = audio_data[start_sample:end_sample]
        offset_seconds = chunk_idx * chunk_length_seconds
        
        yield {
            "type": "status",
            "message": f"Processando fatia {chunk_idx + 1} de {total_chunks} ({offset_seconds:.1f}s - {offset_seconds + len(chunk_data)/sr:.1f}s)..."
        }
        
        inputs = processor.apply_transcription_request(
            audio=chunk_data,
            prompt=prompt
        )
        
        # Move os inputs para o mesmo device do modelo e ajusta dtype
        inputs = {
            k: v.to(model.device, dtype=torch.float16) if isinstance(v, torch.Tensor) and torch.is_floating_point(v)
            else (v.to(model.device) if isinstance(v, torch.Tensor) else v)
            for k, v in inputs.items()
        }
        
        # Inicializa o streamer de texto para esta fatia se num_beams for 1 (TextStreamer não suporta batch size > 1)
        use_streamer = (num_beams == 1)
        streamer = TextIteratorStreamer(processor.tokenizer, skip_prompt=True, skip_special_tokens=True) if use_streamer else None
        
        outputs_container = {}
        
        def run_generate():
            try:
                with torch.no_grad():
                    generation_kwargs = {
                        "max_new_tokens": max_new_tokens,
                        "num_beams": num_beams,
                    }
                    if use_streamer:
                        generation_kwargs["streamer"] = streamer
                        
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
                        
                    output_ids = model.generate(**inputs, **generation_kwargs)
                    outputs_container["output_ids"] = output_ids
            except Exception as e:
                logger.error(f"Erro na thread de geracao do VibeVoice (chunk {chunk_idx}): {e}", exc_info=True)
                outputs_container["error"] = e
            finally:
                if use_streamer:
                    streamer.end()
                
        thread = Thread(target=run_generate)
        thread.start()
        
        # Consome os tokens gerados em tempo real e repassa para o frontend se o streamer estiver ativo
        if use_streamer:
            for new_text in streamer:
                yield {"type": "text_chunk", "text": new_text}
            
        thread.join()
        
        if "error" in outputs_container:
            raise outputs_container["error"]
            
        output_ids = outputs_container.get("output_ids")
        input_ids_length = inputs["input_ids"].shape[1]
        generated_ids = output_ids[:, input_ids_length:]
        
        decode_format = "parsed" if diarization else "transcription_only"
        parsed_output = processor.decode(generated_ids, return_format=decode_format)
        
        chunk_segments = []
        
        # Desencapsula do lote (batch) se necessario
        if isinstance(parsed_output, list) and len(parsed_output) > 0:
            if isinstance(parsed_output[0], list) or isinstance(parsed_output[0], str):
                parsed_output = parsed_output[0]
                
        if isinstance(parsed_output, str):
            chunk_segments.append({
                "start": 0.0,
                "end": len(chunk_data) / sr,
                "speaker": "Principal" if diarization else None,
                "text": parsed_output.strip()
            })
        elif isinstance(parsed_output, list):
            for seg in parsed_output:
                if isinstance(seg, dict):
                    # Não adiciona silêncio vazio se for apenas ruído
                    content_text = str(seg.get("Content", "")).strip()
                    if content_text.lower() == "[silence]":
                        continue
                    chunk_segments.append({
                        "start": float(seg.get("Start", 0.0)),
                        "end": float(seg.get("End", 0.0)),
                        "speaker": str(seg.get("Speaker", "Desconhecido")) if diarization else None,
                        "text": content_text
                    })
                elif isinstance(seg, str):
                    chunk_segments.append({
                        "start": 0.0,
                        "end": len(chunk_data) / sr,
                        "speaker": "Principal" if diarization else None,
                        "text": seg.strip()
                    })
                    
        # Ajusta carimbo de data/hora (timestamps) com base no offset da fatia
        for seg in chunk_segments:
            seg["start"] += offset_seconds
            seg["end"] += offset_seconds
            
            # Envia o segmento decodificado para o frontend atualizar em tempo real
            # Calculamos o progresso com base na fatia atual processada
            progress = ((chunk_idx + 1) / total_chunks) * 100.0
            yield {
                "type": "progress",
                "progress": round(progress, 1),
                "segment": seg
            }
            
            full_transcript.append(seg)
            
    logger.info(f"Transcrição VibeVoice concluída com {len(full_transcript)} segmentos.")
    yield {"type": "done", "full_transcript": full_transcript}

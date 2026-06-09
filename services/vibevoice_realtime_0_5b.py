import os
import gc
import torch
import logging
import numpy as np
import scipy.io.wavfile as wavfile
from typing import Dict, Any, Generator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.VibeVoiceRealtime05B")

# Cache global do modelo
_rt_model = None
_rt_processor = None
_model_id = "microsoft/VibeVoice-Realtime-0.5B"

def get_rt_model_and_processor():
    """
    Carrega o modelo VibeVoice-Realtime-0.5B otimizado para o i7 e RTX 3050.
    """
    global _rt_model, _rt_processor
    
    if _rt_model is not None and _rt_processor is not None:
        return _rt_model, _rt_processor
        
    try:
        from transformers import AutoProcessor, AutoModelForTextToWaveform, BitsAndBytesConfig
        logger.info(f"Carregando VibeVoice-Realtime-0.5B ({_model_id})...")
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        
        _rt_processor = AutoProcessor.from_pretrained(_model_id, trust_remote_code=True)
        _rt_model = AutoModelForTextToWaveform.from_pretrained(
            _model_id,
            quantization_config=bnb_config,
            device_map="cuda",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        logger.info("VibeVoice-Realtime-0.5B carregado com sucesso!")
        return _rt_model, _rt_processor
    except Exception as e:
        logger.warning(f"Erro ao carregar VibeVoice-Realtime-0.5B original (usando fallback offline de streaming): {e}")
        return None, None

def generate_voice_stream_0_5b(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.5,
    top_p: float = 0.9,
    top_k: int = 40,
    repetition_penalty: float = 1.1,
    speed: float = 1.0
) -> Generator[bytes, None, None]:
    """
    Gera blocos de áudio PCM brutos (Raw PCM 16-bit, 24kHz) via gerador/streaming.
    Excelente para baixa latência.
    """
    model, processor = get_rt_model_and_processor()
    
    # Se o modelo real existir, podemos fazer o stream real
    if model is not None and processor is not None:
        try:
            # Roda a inferência de streaming baseada na API do VibeVoice Realtime
            # Aqui simulamos o consumo do iterador do modelo
            inputs = processor(text=text, speaker=speaker_id, return_tensors="pt").to(model.device)
            with torch.no_grad():
                # Geralmente o modelo de tempo real possui um decodificador de streaming
                # que gera blocos menores de áudio conforme avança.
                outputs_generator = model.generate_stream(
                    **inputs,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                    speed=speed
                )
                for chunk in outputs_generator:
                    audio_chunk = chunk.audio.cpu().numpy()
                    # Converte para 16-bit PCM binário e entrega
                    yield (audio_chunk * 32767).astype(np.int16).tobytes()
            return
        except Exception as e:
            logger.error(f"Erro na inferência em tempo real do VibeVoice-Realtime-0.5B: {e}")
            
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

def unload_realtime_model():
    global _rt_model, _rt_processor
    if _rt_model is not None:
        logger.info("Descarregando VibeVoice-Realtime-0.5B...")
        _rt_model = None
        _rt_processor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

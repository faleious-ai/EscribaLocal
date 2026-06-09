import os
import gc
import torch
import logging
import numpy as np
import scipy.io.wavfile as wavfile
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.VibeVoiceTTS15B")

# Cache global do modelo
_tts_model = None
_tts_processor = None
_model_id = "microsoft/VibeVoice-1.5B"

def get_tts_model_and_processor():
    """
    Carrega o modelo VibeVoice-TTS-1.5B otimizado para a GPU RTX 3050 (NF4 4-bit).
    """
    global _tts_model, _tts_processor
    
    if _tts_model is not None and _tts_processor is not None:
        return _tts_model, _tts_processor
        
    try:
        from transformers import AutoProcessor, AutoModelForTextToWaveform, BitsAndBytesConfig
        logger.info(f"Carregando VibeVoice-TTS-1.5B ({_model_id})...")
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            llm_int8_enable_fp32_cpu_offload=True
        )
        
        _tts_processor = AutoProcessor.from_pretrained(_model_id, trust_remote_code=True)
        _tts_model = AutoModelForTextToWaveform.from_pretrained(
            _model_id,
            quantization_config=bnb_config,
            device_map="cuda",
            torch_dtype=torch.float16,
            trust_remote_code=True
        )
        logger.info("VibeVoice-TTS-1.5B carregado com sucesso!")
        return _tts_model, _tts_processor
    except Exception as e:
        logger.warning(f"Erro ao carregar VibeVoice-TTS-1.5B original (usando fallback offline simulado): {e}")
        return None, None

def generate_voice_1_5b(
    text: str,
    speaker_id: str = "speaker_1",
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.1,
    speed: float = 1.0
) -> bytes:
    """
    Gera áudio a partir do texto usando o VibeVoice-TTS-1.5B ou fallback offline.
    Retorna os bytes do arquivo WAV gerado.
    """
    model, processor = get_tts_model_and_processor()
    
    # Se o modelo original estiver disponível, roda a inferência real
    if model is not None and processor is not None:
        try:
            inputs = processor(text=text, speaker=speaker_id, return_tensors="pt").to(model.device)
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                    speed=speed
                )
            # Converte para bytes WAV
            audio_array = outputs.audio.cpu().numpy()
            sample_rate = outputs.sample_rate
            
            import io
            wav_io = io.BytesIO()
            wavfile.write(wav_io, sample_rate, (audio_array * 32767).astype(np.int16))
            return wav_io.getvalue()
        except Exception as e:
            logger.error(f"Erro na inferência real do VibeVoice-TTS-1.5B: {e}")
            
    # Fallback: Gera voz de verdade em português/inglês utilizando o SAPI5 nativo do Windows
    logger.info("Executando fallback SAPI5 do Windows para síntese de voz (TTS-1.5B)...")
    try:
        import win32com.client
        import tempfile
        
        sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
        
        # Filtra a voz com base na seleção
        selected_voice = None
        voices = sapi_voice.GetVoices()
        
        # Vamos mapear speaker_2 e speaker_4 como vozes femininas (Maria ou Zira se disponível)
        is_female = speaker_id in ["speaker_2", "speaker_4"]
        
        for voice in voices:
            desc = voice.GetDescription()
            # Prefere Português se possível
            if "Portuguese" in desc or "Maria" in desc:
                if not is_female and "Maria" in desc:
                    # Se for Maria, é feminina. Mas se temos poucas vozes no Windows, usamos a que tivermos.
                    selected_voice = voice
                else:
                    selected_voice = voice
            elif not selected_voice:
                selected_voice = voice
                
        # Se for speaker_2 ou speaker_4 e acharmos Maria ou Zira, prioriza
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
            
        # Define a velocidade de fala (-10 a 10) baseada no multiplicador speed (0.5 a 2.0)
        # SAPI5 speed default is 0. 1.0x -> 0. 1.5x -> 4. 2.0x -> 8. 0.5x -> -4.
        sapi_rate = int((speed - 1.0) * 8.0)
        sapi_voice.Rate = max(-10, min(10, sapi_rate))
        
        # Cria arquivo temporário WAV usando SAPI5
        fd, temp_wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        fs = win32com.client.Dispatch("SAPI.SpFileStream")
        # 3 = SSFMCreateForWrite
        fs.Open(temp_wav_path, 3, False)
        sapi_voice.AudioOutputStream = fs
        sapi_voice.Speak(text)
        fs.Close()
        
        # Lê o conteúdo do arquivo gerado
        with open(temp_wav_path, "rb") as f:
            wav_bytes = f.read()
            
        # Deleta arquivo temporário
        try:
            os.remove(temp_wav_path)
        except Exception:
            pass
            
        return wav_bytes
        
    except Exception as e:
        logger.error(f"Erro ao usar SAPI5: {e}. Usando fallback secundário senoidal...")
        
    sample_rate = 24000
    duration = max(2.0, min(15.0, len(text) * 0.08)) # duraçao proporcional ao tamanho do texto
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Gera uma modulação senoidal complexa que simula a fala/humano
    # (harmônicos simulando voz humana modulada)
    freq_carrier = 120  # frequência base da voz masculina/feminina (~120-200Hz)
    if speaker_id in ["speaker_2", "speaker_4"]:
        freq_carrier = 210  # voz feminina
        
    envelope = np.sin(np.pi * t / duration) ** 0.5  # subida e descida suave
    signal = np.sin(2 * np.pi * freq_carrier * t)
    # adiciona formantes/harmônicos
    signal += 0.5 * np.sin(2 * np.pi * (freq_carrier * 2) * t)
    signal += 0.25 * np.sin(2 * np.pi * (freq_carrier * 3) * t)
    # modulação de amplitude para simular ritmo de sílabas
    modulator = 0.5 * (1.0 + np.sin(2 * np.pi * 5 * t))
    signal = signal * modulator * envelope
    
    # normaliza e converte para 16-bit PCM WAV
    signal = signal / np.max(np.abs(signal))
    import io
    wav_io = io.BytesIO()
    wavfile.write(wav_io, sample_rate, (signal * 32767).astype(np.int16))
    return wav_io.getvalue()

def unload_tts_model():
    global _tts_model, _tts_processor
    if _tts_model is not None:
        logger.info("Descarregando VibeVoice-TTS-1.5B...")
        _tts_model = None
        _tts_processor = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

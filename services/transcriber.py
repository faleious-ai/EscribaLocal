import os
import gc
import logging
import threading
import subprocess
from typing import Dict, Any, Generator
import torch
import numpy as np
import imageio_ffmpeg

def decode_audio_ffmpeg(file_path: str, sampling_rate: int = 16000) -> np.ndarray:
    """
    Decodifica o arquivo de áudio para PCM de 16kHz em canal único (mono)
    utilizando a biblioteca imageio-ffmpeg empacotada.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_exe,
        "-v", "error",
        "-i", file_path,
        "-f", "s16le",
        "-ac", "1",
        "-ar", str(sampling_rate),
        "-"
    ]
    
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**6
    )
    
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="ignore")
        raise Exception(f"Erro no FFmpeg ao decodificar áudio: {err_msg}")
        
    audio = np.frombuffer(stdout, dtype=np.int16)
    return audio.astype(np.float32) / 32768.0


def decode_audio_bytes_ffmpeg(audio_bytes: bytes, sampling_rate: int = 16000) -> np.ndarray:
    """
    Decodifica bytes de áudio (em qualquer formato como webm, ogg, wav) para PCM 16kHz float32
    passando os bytes via stdin para o FFmpeg.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg_exe,
        "-v", "error",
        "-i", "pipe:0",  # lê de stdin
        "-f", "s16le",
        "-ac", "1",
        "-ar", str(sampling_rate),
        "-"
    ]
    
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**6
    )
    
    stdout, stderr = process.communicate(input=audio_bytes)
    
    if process.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="ignore")
        raise Exception(f"Erro no FFmpeg ao decodificar bytes de áudio: {err_msg}")
        
    audio = np.frombuffer(stdout, dtype=np.int16)
    return audio.astype(np.float32) / 32768.0



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EscribaLocal.Transcriber")

# Cache global para o modelo ativo evitar recargas desnecessárias
_current_model = None
_current_model_name = None
_current_device = None
_current_compute_type = None


def _whisper_status_payload(
    model_name: str,
    device: str,
    compute_type: str,
    requested_device: str = None,
    requested_compute_type: str = None,
    caption: str = "Modelo em uso"
) -> Dict[str, Any]:
    fallback = False
    if requested_device and requested_device != device:
        fallback = True
    if requested_compute_type and requested_compute_type != compute_type:
        fallback = True

    return {
        "type": "model_status",
        "caption": "Fallback em uso" if fallback else caption,
        "engine_key": model_name,
        "engine_label": f"Whisper {model_name} (faster-whisper)",
        "device": device,
        "compute_type": compute_type,
        "fallback": fallback,
    }


def get_whisper_runtime_status(
    requested_model: str = None,
    requested_device: str = None,
    requested_compute_type: str = None
) -> Dict[str, Any]:
    model_name = _current_model_name or requested_model or "Whisper"
    device = _current_device or requested_device or "auto"
    compute_type = _current_compute_type or requested_compute_type or "auto"
    return _whisper_status_payload(
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        requested_device=requested_device,
        requested_compute_type=requested_compute_type,
    )

def get_whisper_model(model_name: str, device: str, compute_type: str, cpu_threads: int = 4):
    """
    Carrega e gerencia a instância do WhisperModel utilizando cache.
    Libera memória RAM/VRAM de modelos anteriores caso as configurações mudem.
    """
    global _current_model, _current_model_name, _current_device, _current_compute_type
    
    # Se as configurações forem as mesmas, retorna o modelo em cache
    if (_current_model is not None 
            and _current_model_name == model_name 
            and _current_device == device 
            and _current_compute_type == compute_type):
        logger.info("Usando modelo Whisper em cache.")
        return _current_model

    # Libera memória se houver outro modelo carregado
    if _current_model is not None:
        logger.info("Descarregando modelo anterior para liberar memória.")
        _current_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    logger.info(f"Carregando WhisperModel: {model_name} no dispositivo {device} ({compute_type})")
    
    # Importação tardia do faster-whisper para inicialização rápida do backend
    from faster_whisper import WhisperModel
    
    # Validação do dispositivo solicitado
    if device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA solicitado mas não disponível. Revertendo para CPU.")
        device = "cpu"
        if compute_type in ["float16", "int8_float16"]:
            compute_type = "int8"

    # Inicializa o modelo
    # Para o Windows, passamos cpu_threads apropriadas
    model = WhisperModel(
        model_size_or_path=model_name,
        device=device,
        compute_type=compute_type,
        download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper-models"),
        num_workers=4,          # Permite rodar múltiplas decodificações concorrentes na GPU
        cpu_threads=cpu_threads # Distribui a carga de CPU nos núcleos disponíveis
    )

    # Armazena em cache
    _current_model = model
    _current_model_name = model_name
    _current_device = device
    _current_compute_type = compute_type

    return model

def transcribe_audio_generator(
    file_path: str,
    model_name: str,
    device: str,
    compute_type: str,
    beam_size: int = 5,
    language: str = None,
    vad_filter: bool = True,
    cpu_threads: int = 4,
    initial_prompt: str = None,
    temperature: float = 0.0,
    cancel_event: threading.Event = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Transcreve um arquivo de áudio gerando atualizações em tempo real do progresso.
    Retorna um Generator que faz streaming do status.

    O cancelamento é cooperativo: quando `cancel_event` é sinalizado, o gerador
    emite um evento {"type": "cancelled"} e retorna no próximo ponto de checagem
    (download, carga do modelo, decodificação ou entre segmentos).
    """
    def _is_cancelled() -> bool:
        return cancel_event is not None and cancel_event.is_set()

    try:
        # Garante o modelo no cache. O download (com limpeza de travas órfãs,
        # espelhos e progresso) é responsabilidade do model_manager, que emite
        # os mesmos eventos download_progress que o frontend sempre consumiu.
        from services.model_manager import ensure_whisper_model_events

        for event in ensure_whisper_model_events(model_name, cancel_event=cancel_event):
            yield event
            if event.get("type") == "cancelled":
                logger.info("Transcrição cancelada durante o download do modelo.")
                return

        if _is_cancelled():
            yield {"type": "cancelled", "message": "Tarefa cancelada antes do carregamento do modelo."}
            return

        yield {
            "type": "status",
            "message": f"Carregando o modelo '{model_name.upper()}' na memória RAM/VRAM... Por favor, aguarde."
        }

        model = get_whisper_model(model_name, device, compute_type, cpu_threads)
        yield get_whisper_runtime_status(
            requested_model=model_name,
            requested_device=device,
            requested_compute_type=compute_type,
        )

        
        logger.info(f"Iniciando decodificação de áudio via FFmpeg: {file_path}...")
        yield {
            "type": "status",
            "message": "Decodificando áudio via FFmpeg... Por favor, aguarde."
        }
        
        audio_data = decode_audio_ffmpeg(file_path)

        if _is_cancelled():
            yield {"type": "cancelled", "message": "Tarefa cancelada antes da transcrição."}
            return

        logger.info(f"Iniciando transcrição de {file_path} (Tamanho do array decodificado: {len(audio_data)})...")
        
        # O idioma nulo na biblioteca é interpretado como None (detecção automática)
        lang_arg = None if not language or language == "auto" else language

        # Transcrição usando faster-whisper (retorna gerador de segmentos + infos)
        segments, info = model.transcribe(
            audio_data,
            beam_size=beam_size,
            language=lang_arg,
            vad_filter=vad_filter,
            vad_parameters=dict(min_speech_duration_ms=250) if vad_filter else None,
            temperature=temperature,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False, # Evita propagar alucinações/repetições para os próximos blocos
        )
        
        total_duration = info.duration
        logger.info(f"Duração total do áudio detectada: {total_duration:.2f}s. Idioma detectado: {info.language} ({info.language_probability:.2f})")
        
        # Envia primeira mensagem com a metainformação
        yield {
            "type": "meta",
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": total_duration
        }

        transcribed_text_blocks = []
        
        # Iterar sobre segmentos gera a transcrição real e nos dá o progresso dinâmico.
        # A decodificação do CT2 é lazy: abortar o loop interrompe o restante.
        for segment in segments:
            if _is_cancelled():
                logger.info("Transcrição cancelada pelo usuário durante a decodificação.")
                yield {"type": "cancelled", "message": "Transcrição cancelada pelo usuário."}
                return

            # Cálculo matemático de progresso baseado no timestamp de término do segmento
            progress = min(100.0, (segment.end / total_duration) * 100.0) if total_duration > 0 else 0.0
            
            segment_data = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            }
            transcribed_text_blocks.append(segment_data)
            
            yield {
                "type": "progress",
                "progress": round(progress, 1),
                "segment": segment_data
            }
            
        logger.info("Transcrição concluída com sucesso.")
        yield {
            "type": "done",
            "full_transcript": transcribed_text_blocks
        }
        
    except Exception as e:
        logger.error(f"Erro na transcrição: {str(e)}", exc_info=True)
        yield {
            "type": "error",
            "message": str(e)
        }

import os
import gc
import logging
import queue
import threading
import time
import subprocess
from typing import Dict, Any, Generator
import torch
import tqdm
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

# Fila para compartilhar eventos de download
_download_queue = queue.Queue()

# Salva as referências originais dos métodos da classe tqdm.tqdm
_original_tqdm_update = tqdm.tqdm.update
_original_tqdm_init = tqdm.tqdm.__init__

def _patched_tqdm_init(self, *args, **kwargs):
    # Força a flag disable para False para contornar ambientes não-TTY (como processos de segundo plano)
    if "disable" in kwargs:
        kwargs["disable"] = False
    _original_tqdm_init(self, *args, **kwargs)
    self.disable = False

def _patched_tqdm_update(self, n=1):
    res = _original_tqdm_update(self, n)
    if self.total and self.total > 0:
        percent = (self.n / self.total) * 100
        elapsed = time.time() - self.start_t
        speed_mb = (self.n / (1024 * 1024)) / elapsed if elapsed > 0 else 0.0
        current_mb = self.n / (1024 * 1024)
        total_mb = self.total / (1024 * 1024)
        
        _download_queue.put({
            "type": "download_progress",
            "percent": round(percent, 1),
            "speed_mb": round(speed_mb, 2),
            "current_mb": round(current_mb, 1),
            "total_mb": round(total_mb, 1),
            "filename": self.desc or "Modelo Whisper"
        })
    return res

# Aplica os patches diretamente no objeto da classe global
tqdm.tqdm.__init__ = _patched_tqdm_init
tqdm.tqdm.update = _patched_tqdm_update



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
    temperature: float = 0.0
) -> Generator[Dict[str, Any], None, None]:
    """
    Transcreve um arquivo de áudio gerando atualizações em tempo real do progresso.
    Retorna um Generator que faz streaming do status.
    """
    try:
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper-models")
        
        # Procura de forma robusta se a pasta do modelo existe e possui o arquivo 'model.bin'
        model_exists = False
        if os.path.exists(cache_dir):
            for folder in os.listdir(cache_dir):
                # Aceita 'Systran' (large-v3, base, tiny) ou 'mobiuslabsgmbh' (large-v3-turbo)
                if model_name in folder:
                    folder_path = os.path.join(cache_dir, folder)
                    if os.path.isdir(folder_path):
                        for root, dirs, files in os.walk(folder_path):
                            if "model.bin" in files:
                                model_exists = True
                                break
        
        if not model_exists:
            # Remove travas (.lock) órfãs que impedem downloads após reloads do servidor
            import shutil
            locks_dir = os.path.join(cache_dir, ".locks")
            if os.path.exists(locks_dir):
                for folder in os.listdir(locks_dir):
                    if model_name in folder:
                        lock_folder_path = os.path.join(locks_dir, folder)
                        try:
                            shutil.rmtree(lock_folder_path)
                            logger.info(f"Limpo arquivo de trava (.lock) orfao em: {lock_folder_path}")
                        except Exception as lock_err:
                            logger.warning(f"Erro ao limpar arquivos de trava: {lock_err}")
        
        if not model_exists:
            # Esvazia a fila de eventos antes de começar
            while not _download_queue.empty():
                try:
                    _download_queue.get_nowait()
                except queue.Empty:
                    break

            from faster_whisper.utils import download_model

            def run_download_thread():
                try:
                    # O download agora usa a classe tqdm com o patch global de classe já aplicado
                    download_model(model_name, cache_dir=cache_dir)
                    _download_queue.put({"type": "download_done"})
                except Exception as err:
                    _download_queue.put({"type": "download_error", "message": str(err)})

            logger.info(f"Disparando thread de download do modelo {model_name}...")
            dl_thread = threading.Thread(target=run_download_thread)
            dl_thread.daemon = True
            dl_thread.start()

            # Loop de consumo da fila de progresso
            while dl_thread.is_alive() or not _download_queue.empty():
                try:
                    event = _download_queue.get(timeout=0.2)
                    if event["type"] == "download_error":
                        raise Exception(event["message"])
                    elif event["type"] == "download_done":
                        break
                    yield event
                except queue.Empty:
                    continue
            
            logger.info("Download do modelo concluído.")

        yield {
            "type": "status",
            "message": f"Carregando o modelo '{model_name.upper()}' na memória RAM/VRAM... Por favor, aguarde."
        }

        model = get_whisper_model(model_name, device, compute_type, cpu_threads)

        
        logger.info(f"Iniciando decodificação de áudio via FFmpeg: {file_path}...")
        yield {
            "type": "status",
            "message": "Decodificando áudio via FFmpeg... Por favor, aguarde."
        }
        
        audio_data = decode_audio_ffmpeg(file_path)
        
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
        
        # Iterar sobre segmentos gera a transcrição real e nos dá o progresso dinâmico
        for segment in segments:
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

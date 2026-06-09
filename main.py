# EscribaLocal Backend - Alta Performance
import os
import json
import uuid
import psutil
import shutil
import logging
import asyncio
import gc
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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

from services.transcriber import transcribe_audio_generator, get_whisper_model, decode_audio_bytes_ffmpeg
from services.vibevoice_service import transcribe_vibevoice_generator, unload_vibevoice_model
from services.summarizer import generate_structured_minutes, generate_narrative_summary
from services.vibevoice_tts_1_5b import generate_voice_1_5b, unload_tts_model
from services.vibevoice_realtime_0_5b import generate_voice_stream_0_5b, unload_realtime_model

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("EscribaLocal.Main")

app = FastAPI(title="EscribaLocal - Transcrição de Áudio de Alta Performance")

# Habilita CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cria a pasta de arquivos estáticos e uploads temporários
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "temp_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)

def get_gpu_vram_real():
    """
    Retorna (memoria_usada_mb, memoria_total_mb) da GPU NVIDIA via nvidia-smi.
    Retorna None se falhar.
    """
    import subprocess
    import shutil
    
    # Caminhos comuns e comando
    cmd = "nvidia-smi"
    nvsmi_path = r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if not shutil.which(cmd) and os.path.exists(nvsmi_path):
        cmd = nvsmi_path
        
    try:
        # startupinfo evita que uma janela preta do cmd pisque no Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
        output = subprocess.check_output(
            [cmd, "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            startupinfo=startupinfo,
            text=True
        )
        parts = output.strip().split(",")
        if len(parts) == 2:
            return float(parts[0].strip()), float(parts[1].strip())
    except Exception:
        pass
    return None

@app.get("/api/system-status")
async def get_system_status():
    """
    Retorna o status atual de uso do Processador, Memória RAM e GPU NVIDIA (se disponível).
    """
    status = {
        "cpu": {
            "percent": psutil.cpu_percent(interval=None),
            "cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
        },
        "ram": {
            "total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 1),
            "used_percent": psutil.virtual_memory().percent,
            "free_gb": round(psutil.virtual_memory().available / (1024 ** 3), 1),
        },
        "gpu": {
            "available": False,
            "name": "Nenhuma GPU detectada",
            "vram_total_mb": 0,
            "vram_allocated_mb": 0,
            "vram_cached_mb": 0
        }
    }

    if torch.cuda.is_available():
        try:
            device_id = torch.cuda.current_device()
            gpu_name = torch.cuda.get_device_name(device_id)
            
            # Tenta ler a VRAM real via nvidia-smi para mostrar o uso do sistema (ctranslate2 bypasses pytorch)
            real_vram = get_gpu_vram_real()
            if real_vram:
                used_mb, total_mb = real_vram
                status["gpu"] = {
                    "available": True,
                    "name": gpu_name,
                    "vram_allocated_mb": round(used_mb, 1),
                    "vram_cached_mb": 0.0,
                    "vram_total_mb": round(total_mb, 1)
                }
            else:
                # Fallback para PyTorch VRAM info
                allocated = torch.cuda.memory_allocated(device_id) / (1024 ** 2)
                cached = torch.cuda.memory_reserved(device_id) / (1024 ** 2)
                
                status["gpu"] = {
                    "available": True,
                    "name": gpu_name,
                    "vram_allocated_mb": round(allocated, 1),
                    "vram_cached_mb": round(cached, 1),
                    "vram_total_mb": round(torch.cuda.get_device_properties(device_id).total_memory / (1024 ** 2), 1)
                }
        except Exception as e:
            logger.warning(f"Erro ao ler informações detalhadas da GPU: {e}")
            status["gpu"]["available"] = True
            status["gpu"]["name"] = "NVIDIA GPU (CUDA Ativo)"

    return status

@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("large-v3-turbo"),
    device: str = Form("cuda"),
    compute_type: str = Form("float16"),
    beam_size: int = Form(5),
    language: str = Form("auto"),
    vad_filter: bool = Form(True),
    cpu_threads: int = Form(4),
    whisper_prompt: str = Form(None),
    whisper_temperature: float = Form(0.0)
):
    """
    Endpoint que recebe o áudio, salva temporariamente e faz streaming
    dos dados de progresso e transcrição em tempo real do Whisper via Server-Sent Events (SSE).
    """
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".mp3"
    temp_file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    
    # Salva o arquivo de upload no disco local
    try:
        # Move o ponteiro do arquivo para o início, garantindo leitura completa
        await file.seek(0)
        content = await file.read()
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content)
        file_size = os.path.getsize(temp_file_path)
        logger.info(f"Arquivo temporario Whisper salvo em: {temp_file_path} (Tamanho: {file_size} bytes)")
        if file_size == 0:
            raise Exception("O arquivo salvo tem 0 bytes.")
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo temporario Whisper: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo enviado: {str(e)}")

    # Definição do gerador assíncrono para streaming via SSE
    async def sse_generator():
        # Executa a tarefa pesada do Whisper em um pool de threads para não bloquear o event loop
        loop = asyncio.get_running_loop()
        
        sync_generator = transcribe_audio_generator(
            file_path=temp_file_path,
            model_name=model,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
            language=language,
            vad_filter=vad_filter,
            cpu_threads=cpu_threads,
            initial_prompt=whisper_prompt,
            temperature=whisper_temperature
        )
        
        full_segments = []
        
        try:
            while True:
                # Executa o next() do gerador síncrono em um thread pool para evitar congelamento
                chunk = await loop.run_in_executor(None, lambda: next(sync_generator, None))
                if chunk is None:
                    break
                
                # Se for o fim ou dados úteis, captura
                if chunk.get("type") == "done":
                    full_segments = chunk.get("full_transcript", [])
                    # Gera a evolução clínica no fim da transcrição do Whisper
                    structured_draft = generate_structured_minutes(full_segments)
                    narrative_draft = generate_narrative_summary(full_segments)
                    yield f"data: {json.dumps({'type': 'audio_summary', 'structured': structured_draft, 'narrative': narrative_draft})}\n\n"
                    await asyncio.sleep(0.01)

                # Formata a saída no protocolo Server-Sent Events (SSE)
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # Pausa rápida para ceder controle ao event loop
                await asyncio.sleep(0.01)
                
        except Exception as err:
            logger.error(f"Erro no streaming SSE Whisper: {err}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(err)})}\n\n"
        finally:
            # Remoção física e segura do arquivo de áudio temporário após transcrição
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Arquivo temporário Whisper removido: {temp_file_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Não foi possível remover o arquivo temporário Whisper: {cleanup_err}")

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.post("/api/transcribe-vibevoice")
async def transcribe_vibevoice(
    file: UploadFile = File(...),
    vibevoice_prompt: str = Form(None),
    vibevoice_diarization: bool = Form(True),
    vibevoice_chunk_size: float = Form(45.0),
    vibevoice_temperature: float = Form(0.0),
    vibevoice_repetition_penalty: float = Form(1.1),
    vibevoice_top_p: float = Form(1.0),
    vibevoice_top_k: int = Form(50),
    vibevoice_num_beams: int = Form(1),
    vibevoice_max_new_tokens: int = Form(2048)
):
    """
    Endpoint dedicado que recebe o áudio, salva temporariamente e faz streaming
    dos dados de progresso e transcrição em tempo real do VibeVoice via Server-Sent Events (SSE).
    """
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] or ".mp3"
    temp_file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
    
    # Salva o arquivo de upload no disco local
    try:
        await file.seek(0)
        content = await file.read()
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content)
        file_size = os.path.getsize(temp_file_path)
        logger.info(f"Arquivo temporario VibeVoice salvo em: {temp_file_path} (Tamanho: {file_size} bytes)")
        if file_size == 0:
            raise Exception("O arquivo salvo tem 0 bytes.")
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo temporario VibeVoice: {e}")
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo enviado: {str(e)}")

    async def sse_generator_vibevoice():
        loop = asyncio.get_running_loop()
        try:
            vibevoice_gen = transcribe_vibevoice_generator(
                file_path=temp_file_path,
                prompt=vibevoice_prompt,
                diarization=vibevoice_diarization,
                chunk_length_seconds=vibevoice_chunk_size,
                temperature=vibevoice_temperature,
                repetition_penalty=vibevoice_repetition_penalty,
                top_p=vibevoice_top_p,
                top_k=vibevoice_top_k,
                num_beams=vibevoice_num_beams,
                max_new_tokens=vibevoice_max_new_tokens
            )
            
            full_segments = []
            
            while True:
                chunk = await loop.run_in_executor(None, lambda: next(vibevoice_gen, None))
                if chunk is None:
                    break
                
                if chunk.get("type") == "done":
                    full_segments = chunk.get("full_transcript", [])
                    # Ao concluir a transcrição por fatias do VibeVoice, gera rascunho de evolução clínica
                    structured_draft = generate_structured_minutes(full_segments)
                    narrative_draft = generate_narrative_summary(full_segments)
                    yield f"data: {json.dumps({'type': 'audio_summary', 'structured': structured_draft, 'narrative': narrative_draft})}\n\n"
                    await asyncio.sleep(0.01)
                    
                    yield f"data: {json.dumps({'type': 'done', 'full_transcript': full_segments})}\n\n"
                else:
                    yield f"data: {json.dumps(chunk)}\n\n"
                
                await asyncio.sleep(0.01)
                
        except Exception as err:
            logger.error(f"Erro no streaming VibeVoice: {err}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(err)})}\n\n"
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Arquivo temporário VibeVoice removido: {temp_file_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Não foi possível remover o arquivo temporário VibeVoice: {cleanup_err}")

    return StreamingResponse(sse_generator_vibevoice(), media_type="text/event-stream")


@app.websocket("/api/live-transcribe")
async def websocket_live_transcribe(websocket: WebSocket):
    """
    Endpoint WebSocket que recebe chunks binários de áudio continuamente,
    decodifica via FFmpeg e devolve a transcrição em tempo real.
    """
    import numpy as np
    await websocket.accept()
    logger.info("Cliente WebSocket conectado para transcrição ao vivo.")
    
    audio_bytes_buffer = b""
    model = None
    
    try:
        # Recebe configuração inicial do cliente
        config_msg = await websocket.receive_text()
        config = json.loads(config_msg)
        
        model_name = config.get("model", "large-v3-turbo")
        device = config.get("device", "cuda")
        compute_type = config.get("compute_type", "float16")
        beam_size = int(config.get("beam_size", 5))
        language = config.get("language", "auto")
        vad_filter = config.get("vad_filter", True)
        cpu_threads = int(config.get("cpu_threads", 4))
        
        await websocket.send_text(json.dumps({
            "type": "status",
            "message": f"Carregando o modelo '{model_name.upper()}' na memória... Por favor, fale ao microfone."
        }))
        
        # Carrega o modelo Whisper em um thread pool para evitar bloqueios
        loop = asyncio.get_running_loop()
        model = await loop.run_in_executor(
            None,
            lambda: get_whisper_model(model_name, device, compute_type, cpu_threads)
        )
        
        await websocket.send_text(json.dumps({
            "type": "ready",
            "message": "Microfone Ativo. Transcrevendo em tempo real..."
        }))
        
        lang_arg = None if not language or language == "auto" else language
        
        while True:
            # Recebe a mensagem (pode ser texto ou binário)
            message = await websocket.receive()
            
            if "bytes" in message:
                audio_bytes = message["bytes"]
                if not audio_bytes or len(audio_bytes) == 0:
                    continue
                
                # Acumula os bytes do contêiner de áudio continuamente
                audio_bytes_buffer += audio_bytes
                
                # Decodifica o buffer inteiro acumulado via FFmpeg
                audio_data = await loop.run_in_executor(
                    None,
                    lambda: decode_audio_bytes_ffmpeg(audio_bytes_buffer)
                )
                
                if len(audio_data) == 0:
                    continue
                
                # Roda a transcrição na fila
                def run_whisper():
                    segments, info = model.transcribe(
                        audio_data,
                        beam_size=beam_size,
                        language=lang_arg,
                        vad_filter=vad_filter,
                        vad_parameters=dict(min_speech_duration_ms=250) if vad_filter else None,
                        temperature=0.0,
                        condition_on_previous_text=False
                    )
                    
                    segment_list = []
                    for s in segments:
                        segment_list.append({
                            "start": s.start,
                            "end": s.end,
                            "text": s.text.strip()
                        })
                    return segment_list
                
                segments_result = await loop.run_in_executor(None, run_whisper)
                
                # Envia de volta a lista atualizada de segmentos
                await websocket.send_text(json.dumps({
                    "type": "progress",
                    "segments": segments_result
                }))
                
            elif "text" in message:
                payload = json.loads(message["text"])
                if payload.get("action") == "stop":
                    logger.info("Cliente solicitou parada da transcrição ao vivo.")
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket de transcrição ao vivo desconectado.")
    except Exception as e:
        logger.error(f"Erro na conexão de transcrição ao vivo: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Erro interno: {str(e)}"
            }))
        except:
            pass
    finally:
        audio_buffer = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


@app.post("/api/tts/generate")
async def tts_generate(
    text: str = Form(...),
    speaker_id: str = Form("speaker_1"),
    temperature: float = Form(0.7),
    top_p: float = Form(0.95),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1),
    speed: float = Form(1.0)
):
    """
    Endpoint HTTP que gera áudio de longa duração a partir de um texto usando VibeVoice-TTS-1.5B.
    """
    import io
    try:
        # Executa no thread pool para não bloquear
        loop = asyncio.get_running_loop()
        wav_bytes = await loop.run_in_executor(
            None,
            lambda: generate_voice_1_5b(
                text=text,
                speaker_id=speaker_id,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                speed=speed
            )
        )
        return StreamingResponse(io.BytesIO(wav_bytes), media_type="audio/wav")
    except Exception as e:
        logger.error(f"Erro na geração de áudio TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/api/tts/stream")
async def websocket_tts_stream(websocket: WebSocket):
    """
    Endpoint WebSocket de baixa latência que recebe textos e envia buffers de áudio PCM brutos (VibeVoice-Realtime-0.5B).
    """
    await websocket.accept()
    logger.info("Cliente conectado para streaming de áudio (TTS Realtime).")
    try:
        while True:
            # Recebe o JSON com texto e configurações
            message = await websocket.receive_text()
            payload = json.loads(message)
            
            text = payload.get("text", "")
            if not text.strip():
                continue
                
            speaker_id = payload.get("speaker_id", "speaker_1")
            temperature = float(payload.get("temperature", 0.5))
            top_p = float(payload.get("top_p", 0.9))
            top_k = int(payload.get("top_k", 40))
            repetition_penalty = float(payload.get("repetition_penalty", 1.1))
            speed = float(payload.get("speed", 1.0))
            
            # Executa a geração em pedaços e envia imediatamente em binário
            loop = asyncio.get_running_loop()
            
            def run_stream():
                return list(generate_voice_stream_0_5b(
                    text=text,
                    speaker_id=speaker_id,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                    speed=speed
                ))
                
            audio_chunks = await loop.run_in_executor(None, run_stream)
            
            # Envia os chunks binários
            for chunk in audio_chunks:
                await websocket.send_bytes(chunk)
                await asyncio.sleep(0.01)
                
            # Envia um marcador especial sinalizando fim do bloco
            await websocket.send_text(json.dumps({"type": "stream_end"}))
            
    except WebSocketDisconnect:
        logger.info("WebSocket de TTS Realtime desconectado.")
    except Exception as e:
        logger.error(f"Erro no WebSocket de TTS: {e}")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass


# Rota padrão para servir a SPA HTML
@app.get("/")
async def get_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Bem-vindo ao EscribaLocal. Crie static/index.html para iniciar a interface."}

# Monta arquivos estáticos
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.mount("/pwa", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "escriba-pwa-standalone")), name="pwa")

if __name__ == "__main__":
    import uvicorn
    # Roda localmente na porta 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

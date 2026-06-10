# EscribaLocal Backend - Alta Performance
import os

import json
import uuid
import psutil
import shutil
import logging
import asyncio
import gc
import time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from services.app_logging import (
    APP_LOG_PATH,
    EVENT_LOG_PATH,
    configure_app_logging,
    get_log_paths,
    read_recent_log_lines,
    record_app_event,
    record_exception_event,
    reset_request_id,
    set_request_id,
)

configure_app_logging()

import torch
from services.runtime_patches import apply_runtime_patches
apply_runtime_patches()

from services.transcriber import (
    decode_audio_bytes_ffmpeg,
    get_whisper_model,
    get_whisper_runtime_status,
    transcribe_audio_generator,
)
from services.vibevoice_service import transcribe_vibevoice_generator
from services.vibevoice_tts_1_5b import SUPPORTED_LONGFORM_TTS_MODELS, generate_voice_1_5b_with_metadata
from services.vibevoice_realtime_0_5b import generate_voice_realtime_wav_with_metadata, generate_voice_stream_0_5b
from services.jobs import JobState, job_manager
from routers.jobs_routes import router as jobs_router
from routers.models_routes import router as models_router

logger = logging.getLogger("EscribaLocal.Main")

app = FastAPI(title="EscribaLocal - Transcrição de Áudio de Alta Performance")
SYSTEM_STATUS_LOG_INTERVAL_SECONDS = 60
_last_system_status_log_at = 0.0

# Habilita CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(models_router)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = set_request_id(request_id)
    started_at = time.perf_counter()
    path = request.url.path

    if path.startswith("/api"):
        record_app_event(
            "http_request_started",
            request_id=request_id,
            method=request.method,
            path=path,
            client_host=request.client.host if request.client else None,
        )

    try:
        response = await call_next(request)
        response.headers["X-Escriba-Request-ID"] = request_id
        if path.startswith("/api"):
            record_app_event(
                "http_request_finished",
                request_id=request_id,
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
            )
        return response
    except Exception as exc:
        record_exception_event(
            "http_request_error",
            exc,
            request_id=request_id,
            method=request.method,
            path=path,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
        )
        raise
    finally:
        reset_request_id(token)


@app.on_event("startup")
async def log_app_startup():
    record_app_event("app_startup", **get_log_paths())

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

    global _last_system_status_log_at
    now = time.monotonic()
    if now - _last_system_status_log_at >= SYSTEM_STATUS_LOG_INTERVAL_SECONDS:
        _last_system_status_log_at = now
        record_app_event(
            "system_status_snapshot",
            cpu_percent=status["cpu"]["percent"],
            ram_used_percent=status["ram"]["used_percent"],
            ram_free_gb=status["ram"]["free_gb"],
            gpu_available=status["gpu"]["available"],
            gpu_name=status["gpu"]["name"],
            gpu_vram_allocated_mb=status["gpu"]["vram_allocated_mb"],
            gpu_vram_total_mb=status["gpu"]["vram_total_mb"],
        )

    return status


@app.get("/api/logs/status")
async def get_logs_status():
    paths = get_log_paths()
    return {
        "paths": paths,
        "sizes_bytes": {
            "app_log": APP_LOG_PATH.stat().st_size if APP_LOG_PATH.exists() else 0,
            "event_log": EVENT_LOG_PATH.stat().st_size if EVENT_LOG_PATH.exists() else 0,
        }
    }


@app.get("/api/logs/recent")
async def get_recent_logs(kind: str = "events", max_lines: int = 250):
    log_path = EVENT_LOG_PATH if kind == "events" else APP_LOG_PATH
    lines = [line.rstrip("\n") for line in read_recent_log_lines(log_path, max_lines=max_lines)]
    return {
        "kind": "events" if kind == "events" else "app",
        "path": str(log_path),
        "lines": lines,
    }


@app.post("/api/client-log")
async def client_log(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {"event_type": "client_log_parse_error"}

    record_app_event(
        "client_event",
        client_event_type=payload.get("event_type", "client_event"),
        severity=payload.get("severity", "info"),
        message=payload.get("message"),
        source=payload.get("source"),
        page=payload.get("page"),
        model=payload.get("model"),
        details=payload.get("details", {}),
    )
    return {"ok": True}

def _transcription_sse_response(request: Request, job, make_generator, engine: str, model_label: str, temp_file_path: str):
    """Envolve um gerador síncrono de transcrição num StreamingResponse SSE com job.

    Responsabilidades: evento inicial {"type":"job"} (ignorado por clientes
    antigos), fila de GPU (semáforo único — duas inferências pesadas
    simultâneas estouram 6GB de VRAM), cancelamento por desconexão do cliente
    e persistência do estado final no histórico.
    """

    async def sse_stream():
        loop = asyncio.get_running_loop()
        yield f"data: {json.dumps({'type': 'job', 'job_id': job.job_id})}\n\n"

        stop_watcher = asyncio.Event()

        async def watch_disconnect():
            # Rede de segurança: aborto do fetch/fechamento da aba cancela o
            # job mesmo com o worker bloqueado numa inferência longa.
            while not stop_watcher.is_set():
                if await request.is_disconnected():
                    job_manager.cancel(job.job_id, reason="cliente desconectou")
                    return
                try:
                    await asyncio.wait_for(stop_watcher.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

        watcher = asyncio.create_task(watch_disconnect())
        final_state = None
        error_message = None
        gpu_acquired = False
        try:
            queued_notified = False
            while not job.cancel_event.is_set():
                gpu_acquired = await loop.run_in_executor(None, job_manager.try_acquire_gpu, job.job_id, 0.5)
                if gpu_acquired:
                    break
                if not queued_notified:
                    queued_notified = True
                    waiting_event = {"type": "status", "message": "Na fila: aguardando outra tarefa pesada terminar..."}
                    job_manager.publish(job.job_id, waiting_event)
                    yield f"data: {json.dumps(waiting_event)}\n\n"

            if job.cancel_event.is_set():
                final_state = JobState.CANCELLED
                yield f"data: {json.dumps({'type': 'cancelled', 'message': 'Tarefa cancelada antes do início.'})}\n\n"
                return

            job_manager.start(job.job_id)
            sync_generator = make_generator(job.cancel_event)

            while True:
                chunk = await loop.run_in_executor(None, lambda: next(sync_generator, None))
                if chunk is None:
                    break
                chunk_type = chunk.get("type")
                job_manager.publish(job.job_id, chunk)

                if chunk_type == "model_status":
                    record_app_event("transcription_model_status", engine=engine, **chunk)
                elif chunk_type == "done":
                    final_state = JobState.COMPLETED
                    record_app_event(
                        "transcription_completed",
                        engine=engine,
                        model=model_label,
                        segment_count=len(chunk.get("full_transcript", [])),
                    )
                elif chunk_type == "error":
                    final_state = JobState.FAILED
                    error_message = chunk.get("message")
                    record_app_event("transcription_stream_error", engine=engine, message=chunk.get("message"))
                elif chunk_type == "cancelled":
                    final_state = JobState.CANCELLED
                    record_app_event("transcription_cancelled", engine=engine, model=model_label)

                yield f"data: {json.dumps(chunk)}\n\n"

                if chunk_type == "cancelled":
                    break
                await asyncio.sleep(0.01)

        except Exception as err:
            final_state = JobState.FAILED
            error_message = str(err)
            logger.error(f"Erro no streaming SSE {engine}: {err}", exc_info=True)
            record_exception_event("transcription_stream_exception", err, engine=engine, model=model_label)
            yield f"data: {json.dumps({'type': 'error', 'message': str(err)})}\n\n"
        finally:
            stop_watcher.set()
            watcher.cancel()
            if gpu_acquired:
                job_manager.release_gpu(job.job_id)
            if final_state is None:
                # Stream fechado sem desfecho (desconexão do cliente): garante
                # a parada do worker e registra como cancelado.
                job.cancel_event.set()
                final_state = JobState.CANCELLED
            job_manager.finish(job.job_id, final_state, error=error_message)
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    logger.info(f"Arquivo temporário removido: {temp_file_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Não foi possível remover o arquivo temporário: {cleanup_err}")

    return StreamingResponse(
        sse_stream(),
        media_type="text/event-stream",
        headers={"X-Escriba-Job-ID": job.job_id},
    )


@app.post("/api/transcribe")
async def transcribe_audio(
    request: Request,
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
        record_app_event(
            "transcription_request_received",
            engine="whisper",
            model=model,
            device=device,
            compute_type=compute_type,
            file_ext=ext,
            file_size_bytes=file_size,
            language=language,
            vad_filter=vad_filter,
        )
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo temporario Whisper: {e}")
        record_exception_event("transcription_upload_error", e, engine="whisper", file_ext=ext)
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo enviado: {str(e)}")

    job = job_manager.create(
        kind="transcribe_whisper",
        params={
            "model": model,
            "device": device,
            "compute_type": compute_type,
            "beam_size": beam_size,
            "language": language,
            "vad_filter": vad_filter,
            "cpu_threads": cpu_threads,
            "whisper_prompt": whisper_prompt,
            "temperature": whisper_temperature,
        },
        input_ref=temp_file_path,
    )

    def make_generator(cancel_event):
        return transcribe_audio_generator(
            file_path=temp_file_path,
            model_name=model,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
            language=language,
            vad_filter=vad_filter,
            cpu_threads=cpu_threads,
            initial_prompt=whisper_prompt,
            temperature=whisper_temperature,
            cancel_event=cancel_event
        )

    return _transcription_sse_response(
        request, job, make_generator,
        engine="whisper", model_label=model, temp_file_path=temp_file_path,
    )


@app.post("/api/transcribe-vibevoice")
async def transcribe_vibevoice(
    request: Request,
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
        record_app_event(
            "transcription_request_received",
            engine="vibevoice_asr",
            file_ext=ext,
            file_size_bytes=file_size,
            diarization=vibevoice_diarization,
            tokenizer_window_seconds=vibevoice_chunk_size,
            temperature=vibevoice_temperature,
        )
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo temporario VibeVoice: {e}")
        record_exception_event("transcription_upload_error", e, engine="vibevoice_asr", file_ext=ext)
        raise HTTPException(status_code=500, detail=f"Falha ao salvar arquivo enviado: {str(e)}")

    job = job_manager.create(
        kind="transcribe_vibevoice",
        params={
            "prompt": vibevoice_prompt,
            "diarization": vibevoice_diarization,
            "chunk_length_seconds": vibevoice_chunk_size,
            "temperature": vibevoice_temperature,
            "repetition_penalty": vibevoice_repetition_penalty,
            "top_p": vibevoice_top_p,
            "top_k": vibevoice_top_k,
            "num_beams": vibevoice_num_beams,
            "max_new_tokens": vibevoice_max_new_tokens,
        },
        input_ref=temp_file_path,
    )

    def make_generator(cancel_event):
        return transcribe_vibevoice_generator(
            file_path=temp_file_path,
            prompt=vibevoice_prompt,
            diarization=vibevoice_diarization,
            chunk_length_seconds=vibevoice_chunk_size,
            temperature=vibevoice_temperature,
            repetition_penalty=vibevoice_repetition_penalty,
            top_p=vibevoice_top_p,
            top_k=vibevoice_top_k,
            num_beams=vibevoice_num_beams,
            max_new_tokens=vibevoice_max_new_tokens,
            cancel_event=cancel_event
        )

    return _transcription_sse_response(
        request, job, make_generator,
        engine="vibevoice_asr", model_label="vibevoice_asr", temp_file_path=temp_file_path,
    )


@app.websocket("/api/live-transcribe")
async def websocket_live_transcribe(websocket: WebSocket):
    """
    Endpoint WebSocket que recebe chunks binários de áudio continuamente,
    decodifica via FFmpeg e devolve a transcrição em tempo real.
    """
    import numpy as np
    await websocket.accept()
    logger.info("Cliente WebSocket conectado para transcrição ao vivo.")
    
    model = None
    full_segments = []
    live_offset_seconds = 0.0
    
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
        record_app_event(
            "live_transcription_requested",
            model=model_name,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
            language=language,
            vad_filter=vad_filter,
            cpu_threads=cpu_threads,
        )
        
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
        model_status = get_whisper_runtime_status(
            requested_model=model_name,
            requested_device=device,
            requested_compute_type=compute_type
        )
        record_app_event("live_transcription_model_status", **model_status)
        await websocket.send_text(json.dumps(model_status))
        
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
                
                # Cada blob recebido do cliente é um trecho de áudio fechado.
                audio_data = await loop.run_in_executor(
                    None,
                    lambda: decode_audio_bytes_ffmpeg(audio_bytes)
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
                        text = s.text.strip()
                        if not text:
                            continue
                        segment_list.append({
                            "start": s.start + live_offset_seconds,
                            "end": s.end + live_offset_seconds,
                            "text": text
                        })
                    return segment_list
                
                segments_result = await loop.run_in_executor(None, run_whisper)
                full_segments.extend(segments_result)
                live_offset_seconds += len(audio_data) / 16000.0
                if segments_result:
                    record_app_event(
                        "live_transcription_chunk_processed",
                        new_segment_count=len(segments_result),
                        total_segment_count=len(full_segments),
                        offset_seconds=round(live_offset_seconds, 2),
                    )
                
                # Envia de volta a lista atualizada de segmentos
                await websocket.send_text(json.dumps({
                    "type": "progress",
                    "segments": full_segments
                }))
                
            elif "text" in message:
                payload = json.loads(message["text"])
                if payload.get("action") == "stop":
                    logger.info("Cliente solicitou parada da transcrição ao vivo.")
                    record_app_event(
                        "live_transcription_stopped",
                        total_segment_count=len(full_segments),
                        offset_seconds=round(live_offset_seconds, 2),
                    )
                    break
                    
    except WebSocketDisconnect:
        logger.info("WebSocket de transcrição ao vivo desconectado.")
    except Exception as e:
        logger.error(f"Erro na conexão de transcrição ao vivo: {e}", exc_info=True)
        record_exception_event("live_transcription_error", e)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Erro interno: {str(e)}"
            }))
        except:
            pass
    finally:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


@app.post("/api/tts/generate")
async def tts_generate(
    text: str = Form(...),
    tts_model: str = Form("tts_1_5b"),
    speaker_id: str = Form("speaker_1"),
    temperature: float = Form(0.7),
    top_p: float = Form(0.95),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.1),
    speed: float = Form(1.0)
):
    """
    Endpoint HTTP que gera áudio WAV a partir de texto usando o motor TTS selecionado.
    """
    import io
    if tts_model not in SUPPORTED_LONGFORM_TTS_MODELS | {"realtime_0_5b"}:
        raise HTTPException(status_code=400, detail="Modelo TTS inválido.")
    try:
        record_app_event(
            "tts_generate_requested",
            requested_model=tts_model,
            speaker_id=speaker_id,
            text_length=len(text or ""),
            temperature=temperature,
            speed=speed,
        )
        # Executa no thread pool para não bloquear
        loop = asyncio.get_running_loop()
        voice_result = await loop.run_in_executor(
            None,
            lambda: generate_voice_1_5b_with_metadata(
                text=text,
                speaker_id=speaker_id,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                speed=speed,
                model_key=tts_model
            ) if tts_model in SUPPORTED_LONGFORM_TTS_MODELS else generate_voice_realtime_wav_with_metadata(
                text=text,
                speaker_id=speaker_id,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                speed=speed
            )
        )
        headers = {
            "X-Escriba-TTS-Requested": tts_model,
            "X-Escriba-TTS-Engine-Key": str(voice_result.get("engine_key", tts_model)),
            "X-Escriba-TTS-Engine": str(voice_result.get("engine_label", tts_model)),
            "X-Escriba-TTS-Fallback": "true" if voice_result.get("fallback") else "false",
        }
        record_app_event(
            "tts_generate_completed",
            requested_model=tts_model,
            engine_key=voice_result.get("engine_key", tts_model),
            engine_label=voice_result.get("engine_label", tts_model),
            fallback=bool(voice_result.get("fallback")),
            output_bytes=len(voice_result["wav_bytes"]),
        )
        return StreamingResponse(io.BytesIO(voice_result["wav_bytes"]), media_type="audio/wav", headers=headers)
    except Exception as e:
        logger.error(f"Erro na geração de áudio TTS: {e}")
        record_exception_event("tts_generate_error", e, requested_model=tts_model)
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
            record_app_event(
                "tts_stream_requested",
                requested_model="realtime_0_5b",
                text_length=len(text),
                speaker_id=payload.get("speaker_id", "speaker_1"),
            )
                
            speaker_id = payload.get("speaker_id", "speaker_1")
            temperature = float(payload.get("temperature", 0.5))
            top_p = float(payload.get("top_p", 0.9))
            top_k = int(payload.get("top_k", 40))
            repetition_penalty = float(payload.get("repetition_penalty", 1.1))
            speed = float(payload.get("speed", 1.0))
            
            # Executa a geração em pedaços e envia imediatamente em binário
            loop = asyncio.get_running_loop()
            
            engine_info = {}
            engine_status_sent = False

            def capture_engine_status(info):
                engine_info.update(info)

            audio_iter = generate_voice_stream_0_5b(
                text=text,
                speaker_id=speaker_id,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                speed=speed,
                status_callback=capture_engine_status
            )
            
            # Envia os chunks binários
            while True:
                chunk = await loop.run_in_executor(None, lambda: next(audio_iter, None))
                if engine_info and not engine_status_sent:
                    record_app_event(
                        "tts_stream_engine_status",
                        engine_key=engine_info.get("engine_key", "realtime_0_5b"),
                        engine_label=engine_info.get("engine_label", "VibeVoice-Realtime-0.5B"),
                        fallback=bool(engine_info.get("fallback", False)),
                    )
                    await websocket.send_text(json.dumps({
                        "type": "engine_status",
                        "engine_key": engine_info.get("engine_key", "realtime_0_5b"),
                        "engine_label": engine_info.get("engine_label", "VibeVoice-Realtime-0.5B"),
                        "fallback": bool(engine_info.get("fallback", False))
                    }))
                    engine_status_sent = True
                if chunk is None:
                    break
                await websocket.send_bytes(chunk)
                await asyncio.sleep(0.01)
                
            # Envia um marcador especial sinalizando fim do bloco
            record_app_event("tts_stream_completed")
            await websocket.send_text(json.dumps({"type": "stream_end"}))
            
    except WebSocketDisconnect:
        logger.info("WebSocket de TTS Realtime desconectado.")
    except Exception as e:
        logger.error(f"Erro no WebSocket de TTS: {e}")
        record_exception_event("tts_stream_error", e)
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

# O PWA standalone é opcional; montar uma pasta inexistente derruba o servidor
# na inicialização (RuntimeError do StaticFiles).
_pwa_dir = os.path.join(os.path.dirname(__file__), "escriba-pwa-standalone")
if os.path.isdir(_pwa_dir):
    app.mount("/pwa", StaticFiles(directory=_pwa_dir), name="pwa")
else:
    logger.info("Pasta 'escriba-pwa-standalone' ausente; rota /pwa não montada.")

if __name__ == "__main__":
    import uvicorn
    # Roda localmente na porta 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

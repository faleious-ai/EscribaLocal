"""Rotas de jobs: listagem, snapshot, cancelamento, re-attach de eventos e histórico."""
import asyncio
import json
import queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.jobs import TERMINAL_STATES, job_manager

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs")
async def list_jobs(state: str | None = None, kind: str | None = None):
    return {"jobs": job_manager.list(state=state, kind=kind)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    snapshot = job_manager.get_snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    
    # Adiciona metadados de retenção seguros
    from services.input_retention import get_retention_metadata
    snapshot["retention"] = get_retention_metadata(job_id, snapshot.get("input_ref"))
    return snapshot


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    if job.state in TERMINAL_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Job já finalizado com estado '{job.state.value}'.",
        )
    snapshot = job_manager.cancel(job_id)
    return snapshot


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    # 1. Busca no histórico consolidado
    consolidated = job_manager.history(limit=1, kind=None, state=None)
    # Procuramos o job correspondente no histórico do gerenciador
    original_job_data = None
    
    # Tenta obter do history que consolida os jobs finalizados
    jobs_history = job_manager.history(limit=500, offset=0)
    for entry in jobs_history:
        if entry.get("job_id") == job_id:
            original_job_data = entry
            break
            
    # Se não achar no histórico, tenta ver se está em memória
    if not original_job_data:
        snapshot = job_manager.get_snapshot(job_id)
        if snapshot:
            original_job_data = snapshot
            
    if not original_job_data:
        raise HTTPException(status_code=404, detail="Job não encontrado no histórico.")

    kind = original_job_data.get("kind")
    if kind not in ("transcribe_whisper", "transcribe_vibevoice"):
        raise HTTPException(status_code=400, detail="Este tipo de job não suporta reexecução (retry).")

    # 2. Verifica se o arquivo físico de input ainda está disponível
    from services.input_retention import get_retention_metadata
    retention_meta = get_retention_metadata(job_id, original_job_data.get("input_ref"))
    if not retention_meta.get("input_available"):
        from services.app_logging import record_app_event
        record_app_event("retry_denied_file_missing", job_id=job_id)
        raise HTTPException(status_code=410, detail="O arquivo de áudio original não está mais disponível.")

    # 3. Cria um novo job duplicando os parâmetros técnicos preservados
    params = original_job_data.get("params", {})
    
    # 4. Avisa no retorno se prompts ou conteúdos sensíveis originais não foram aplicados
    prompt_warn = False
    cleaned_params = dict(params)
    for sensitive_key in ("whisper_prompt", "prompt"):
        if sensitive_key in cleaned_params and cleaned_params[sensitive_key]:
            # Foi sanitizado no log ou histórico, então não podemos repetir exatamente igual
            prompt_warn = True
            cleaned_params[sensitive_key] = None

    # O arquivo retido será a entrada do novo job
    import os
    ext = os.path.splitext(original_job_data.get("input_ref"))[1] or ".mp3"
    from services.input_retention import RETAINED_DIR
    retained_file = RETAINED_DIR / f"{job_id}{ext}"

    # Agenda a reexecução pelo fastapi chamando o worker de transcrição
    # Para reexecutar no servidor de maneira transparente, chamamos a criação de um novo job
    # e enviamos o job_id de volta. O frontend pode então se conectar a este novo job
    new_job = job_manager.create(
        kind=kind,
        params=cleaned_params,
        input_ref=str(retained_file)
    )

    from services.app_logging import record_app_event
    record_app_event("retry_created", original_job_id=job_id, new_job_id=new_job.job_id)

    # Note: O processamento de inferência do Whisper ou VibeVoice é disparado
    # de forma assíncrona pelos endpoints de transcrição. Para o retry funcionar,
    # precisamos iniciar o worker correspondente para o novo job.
    # Vamos disparar isso em uma task assíncrona em background usando o loop de eventos
    # para simular a transcrição a partir do arquivo retido.
    
    # Importações dinâmicas para evitar import circular
    from main import transcribe_audio_generator, transcribe_vibevoice_generator
    
    def run_retry_worker():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def run_task():
            gpu_acquired = False
            try:
                # Na fila
                queued_notified = False
                while not new_job.cancel_event.is_set():
                    gpu_acquired = await loop.run_in_executor(None, job_manager.try_acquire_gpu, new_job.job_id, 0.5)
                    if gpu_acquired:
                        break
                    if not queued_notified:
                        queued_notified = True
                        job_manager.publish(new_job.job_id, {"type": "status", "message": "Na fila: aguardando outra tarefa pesada terminar..."})
                
                if new_job.cancel_event.is_set():
                    job_manager.finish(new_job.job_id, JobState.CANCELLED)
                    return
                
                job_manager.start(new_job.job_id)
                
                if kind == "transcribe_whisper":
                    gen = transcribe_audio_generator(
                        file_path=str(retained_file),
                        model_name=cleaned_params.get("model", "large-v3-turbo"),
                        device=cleaned_params.get("device", "cuda"),
                        compute_type=cleaned_params.get("compute_type", "float16"),
                        beam_size=cleaned_params.get("beam_size", 5),
                        language=cleaned_params.get("language", "auto"),
                        vad_filter=cleaned_params.get("vad_filter", True),
                        cpu_threads=cleaned_params.get("cpu_threads", 4),
                        initial_prompt=None, # prompts sensíveis originais não reaplicados
                        temperature=cleaned_params.get("temperature", 0.0),
                        cancel_event=new_job.cancel_event
                    )
                else: # transcribe_vibevoice
                    gen = transcribe_vibevoice_generator(
                        file_path=str(retained_file),
                        prompt=None,
                        diarization=cleaned_params.get("diarization", True),
                        chunk_length_seconds=cleaned_params.get("chunk_length_seconds", 45.0),
                        temperature=cleaned_params.get("temperature", 0.0),
                        repetition_penalty=cleaned_params.get("repetition_penalty", 1.1),
                        top_p=cleaned_params.get("top_p", 1.0),
                        top_k=cleaned_params.get("top_k", 50),
                        num_beams=cleaned_params.get("num_beams", 1),
                        max_new_tokens=cleaned_params.get("max_new_tokens", 2048),
                        cancel_event=new_job.cancel_event
                    )
                
                final_state = JobState.COMPLETED
                error_msg = None
                
                while True:
                    chunk = await loop.run_in_executor(None, lambda: next(gen, None))
                    if chunk is None:
                        break
                    
                    job_manager.publish(new_job.job_id, chunk)
                    if chunk.get("type") == "error":
                        final_state = JobState.FAILED
                        error_msg = chunk.get("message")
                    elif chunk.get("type") == "cancelled":
                        final_state = JobState.CANCELLED
                        
                job_manager.finish(new_job.job_id, final_state, error=error_msg)
                
            except Exception as exc:
                job_manager.finish(new_job.job_id, JobState.FAILED, error=str(exc))
            finally:
                if gpu_acquired:
                    job_manager.release_gpu(new_job.job_id)
                # No retry, não apagamos o arquivo retido até que expire por TTL ou limite
        
        loop.run_until_complete(run_task())
        loop.close()

    import threading
    threading.Thread(target=run_retry_worker, daemon=True, name=f"retry-{new_job.job_id}").start()

    return {
        "ok": True,
        "job_id": new_job.job_id,
        "prompt_warning": prompt_warn,
        "message": "Reexecução agendada com sucesso. Parâmetros técnicos preservados. Conteúdos de prompts sensíveis não foram reaplicados." if prompt_warn else "Reexecução agendada com sucesso."
    }


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    """Re-attach: stream SSE dos eventos de um job em andamento.

    Sempre envia primeiro um snapshot do estado atual; se o job já terminou,
    encerra em seguida.
    """
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    subscriber = job_manager.subscribe(job_id)

    async def event_stream():
        loop = asyncio.get_running_loop()
        snapshot = job_manager.get_snapshot(job_id)
        yield f"data: {json.dumps({'type': 'job_snapshot', 'job': snapshot})}\n\n"
        if subscriber is None:
            return
        try:
            while True:
                try:
                    event = await loop.run_in_executor(None, subscriber.get, True, 0.5)
                except queue.Empty:
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            job_manager.unsubscribe(job_id, subscriber)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history")
async def get_history(limit: int = 50, offset: int = 0, kind: str | None = None, state: str | None = None):
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    history_entries = job_manager.history(limit=limit, offset=offset, kind=kind, state=state)
    
    # Enriquece o histórico com metadados seguros sobre o arquivo original
    from services.input_retention import get_retention_metadata
    for entry in history_entries:
        entry["retention"] = get_retention_metadata(entry.get("job_id"), entry.get("input_ref"))
        # Remove a referência absoluta do arquivo para manter privacidade
        entry.pop("input_ref", None)
        
    return {"history": history_entries}

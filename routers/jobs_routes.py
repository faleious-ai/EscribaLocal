"""Rotas de jobs: listagem, snapshot, cancelamento, re-attach de eventos e historico."""
import asyncio
import json
import queue

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from services.job_execution import run_sync_generator_job
from services.jobs import TERMINAL_STATES, JobState, job_manager

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs")
async def list_jobs(state: str | None = None, kind: str | None = None):
    jobs = job_manager.list(state=state, kind=kind)
    from services.input_retention import get_retention_metadata
    for j in jobs:
        j["retention"] = get_retention_metadata(j.get("job_id"), j.get("input_ref"))
        j.pop("input_ref", None)
    return {"jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    snapshot = job_manager.get_snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")

    # Adiciona metadados de retencao seguros
    from services.input_retention import get_retention_metadata
    snapshot["retention"] = get_retention_metadata(job_id, snapshot.get("input_ref"))
    snapshot.pop("input_ref", None)
    return snapshot


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    if job.state in TERMINAL_STATES:
        raise HTTPException(
            status_code=409,
            detail=f"Job ja finalizado com estado '{job.state.value}'.",
        )
    snapshot = job_manager.cancel(job_id)
    snapshot.pop("input_ref", None)
    return snapshot


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    # 1. Busca no historico completo persistido
    original_job_data = job_manager.find_history_job(job_id)

    # Se nao achar no historico, tenta ver se esta em memoria
    if not original_job_data:
        snapshot = job_manager.get_snapshot(job_id)
        if snapshot:
            original_job_data = snapshot

    if not original_job_data:
        raise HTTPException(status_code=404, detail="Job nao encontrado no historico.")

    kind = original_job_data.get("kind")
    if kind not in ("transcribe_whisper", "transcribe_vibevoice"):
        raise HTTPException(status_code=400, detail="Este tipo de job nao suporta reexecucao (retry).")

    # 2. Verifica se o arquivo fisico de input ainda esta disponivel
    from services.input_retention import get_retention_metadata
    retention_meta = get_retention_metadata(job_id, original_job_data.get("input_ref"))
    if not retention_meta.get("input_available"):
        from services.app_logging import record_app_event
        record_app_event("retry_denied_file_missing", job_id=job_id)
        raise HTTPException(status_code=410, detail="O arquivo de audio original nao esta mais disponivel.")

    # 3. Cria um novo job duplicando os parametros tecnicos preservados
    params = original_job_data.get("params", {})

    # 4. Avisa no retorno se prompts ou conteudos sensiveis originais nao foram aplicados
    prompt_warn = False
    cleaned_params = dict(params)
    for sensitive_key in ("whisper_prompt", "prompt"):
        if sensitive_key in cleaned_params and cleaned_params[sensitive_key]:
            # Foi sanitizado no log ou historico, entao nao podemos repetir exatamente igual
            prompt_warn = True
            cleaned_params[sensitive_key] = None

    # O arquivo retido sera a entrada do novo job
    import os
    ext = os.path.splitext(original_job_data.get("input_ref"))[1] or ".mp3"
    from services.input_retention import RETAINED_DIR
    retained_file = RETAINED_DIR / f"{job_id}{ext}"

    # Agenda a reexecucao pelo fastapi chamando o worker de transcricao
    # Para reexecutar no servidor de maneira transparente, chamamos a criacao de um novo job
    # e enviamos o job_id de volta. O frontend pode entao se conectar a este novo job
    new_job = job_manager.create(
        kind=kind,
        params=cleaned_params,
        input_ref=str(retained_file)
    )

    from services.app_logging import record_app_event
    record_app_event("retry_created", original_job_id=job_id, new_job_id=new_job.job_id)

    # Note: O processamento de inferencia do Whisper ou VibeVoice e disparado
    # de forma assincrona pelos endpoints de transcricao. Para o retry funcionar,
    # precisamos iniciar o worker correspondente para o novo job.
    # Vamos disparar isso em uma task assincrona em background usando o loop de eventos
    # para simular a transcricao a partir do arquivo retido.

    # Importacoes dinamicas para evitar import circular
    from services.transcriber import transcribe_audio_generator
    from services.vibevoice_service import transcribe_vibevoice_generator

    def make_retry_generator(cancel_event):
        if kind == "transcribe_whisper":
            return transcribe_audio_generator(
                file_path=str(retained_file),
                model_name=cleaned_params.get("model", "large-v3-turbo"),
                device=cleaned_params.get("device", "cuda"),
                compute_type=cleaned_params.get("compute_type", "float16"),
                beam_size=cleaned_params.get("beam_size", 5),
                language=cleaned_params.get("language", "auto"),
                vad_filter=cleaned_params.get("vad_filter", True),
                cpu_threads=cleaned_params.get("cpu_threads", 4),
                initial_prompt=None,
                temperature=cleaned_params.get("temperature", 0.0),
                cancel_event=cancel_event,
            )
        return transcribe_vibevoice_generator(
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
            cancel_event=cancel_event,
        )

    def run_retry_worker():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run_task():
            async for _event in run_sync_generator_job(
                new_job,
                make_retry_generator,
                unfinished_state=JobState.COMPLETED,
            ):
                pass
        loop.run_until_complete(run_task())
        loop.close()

    import threading
    threading.Thread(target=run_retry_worker, daemon=True, name=f"retry-{new_job.job_id}").start()

    return {
        "ok": True,
        "job_id": new_job.job_id,
        "prompt_warning": prompt_warn,
        "message": "Reexecucao agendada com sucesso. Parametros tecnicos preservados. Conteudos de prompts sensiveis nao foram reaplicados." if prompt_warn else "Reexecucao agendada com sucesso."
    }


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    """Re-attach: stream SSE dos eventos de um job em andamento.

    Sempre envia primeiro um snapshot do estado atual; se o job ja terminou,
    encerra em seguida.
    """
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")

    subscriber = job_manager.subscribe(job_id)

    async def event_stream():
        loop = asyncio.get_running_loop()
        snapshot = job_manager.get_snapshot(job_id)
        if snapshot:
            from services.input_retention import get_retention_metadata
            snapshot["retention"] = get_retention_metadata(job_id, snapshot.get("input_ref"))
            snapshot.pop("input_ref", None)
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

    # Enriquece o historico com metadados seguros sobre o arquivo original
    from services.input_retention import get_retention_metadata
    for entry in history_entries:
        entry["retention"] = get_retention_metadata(entry.get("job_id"), entry.get("input_ref"))
        # Remove a referencia absoluta do arquivo para manter privacidade
        entry.pop("input_ref", None)

    return {"history": history_entries}

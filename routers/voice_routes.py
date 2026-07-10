"""Rotas da biblioteca de vozes do VibeVoice TTS 1.5B.

Respostas públicas nunca expõem caminhos do disco; áudio (referência/prévia)
é servido por endpoints dedicados. Operações pesadas (prévia, validação,
reprocessamento) rodam no thread pool.
"""
import asyncio
import io
import os
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from services import voice_profiles
from services.app_logging import record_app_event

router = APIRouter(prefix="/api/tts", tags=["voices"])

PREVIEW_TEXT = "Olá, esta é uma demonstração da voz selecionada."
VALIDATION_TEXT = "Olá, mundo."


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, voice_profiles.VoiceNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, voice_profiles.VoiceInUse):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, voice_profiles.InvalidVoice):
        detail = {"message": str(exc)}
        if exc.analysis:
            detail["analysis"] = exc.analysis
        return HTTPException(status_code=422, detail=detail)
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/voices")
async def list_voices():
    return voice_profiles.list_voices()


@router.get("/realtime-worker/status")
async def realtime_worker_status():
    from services.vibevoice_realtime_0_5b import get_realtime_worker_status

    return get_realtime_worker_status()


async def _create_voice(file: UploadFile, name: str, consent_confirmed: bool,
                        language: str, source: str):
    content = await file.read()
    ext = os.path.splitext(file.filename or "")[1] or ".webm"
    loop = asyncio.get_running_loop()
    try:
        profile, analysis = await loop.run_in_executor(
            None,
            lambda: voice_profiles.create_voice(
                name=name, audio_bytes=content, original_ext=ext,
                source=source, consent_confirmed=consent_confirmed,
                language=language,
            ),
        )
    except Exception as exc:
        raise _http_error(exc)
    return {"voice": profile, "analysis": analysis}


@router.post("/voices/upload")
async def upload_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    consent_confirmed: bool = Form(False),
    language: str = Form("pt-BR"),
):
    return await _create_voice(file, name, consent_confirmed, language, source="upload")


@router.post("/voices/record")
async def record_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    consent_confirmed: bool = Form(False),
    language: str = Form("pt-BR"),
):
    return await _create_voice(file, name, consent_confirmed, language, source="recording")


@router.post("/voices/import")
async def import_voice(file: UploadFile = File(...)):
    content = await file.read()
    loop = asyncio.get_running_loop()
    try:
        profile = await loop.run_in_executor(None, voice_profiles.import_voice, content)
    except Exception as exc:
        raise _http_error(exc)
    return {"voice": profile}


@router.get("/voices/{voice_id}")
async def get_voice(voice_id: str):
    try:
        return voice_profiles.get_voice(voice_id)
    except Exception as exc:
        raise _http_error(exc)


class VoicePatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)


class StyleCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field("", max_length=500)
    aliases: list[str] = Field(default_factory=list)
    instruction: str = Field("", max_length=1000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    engine_compatibility: dict[str, str] = Field(default_factory=dict)


class StylePatchBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    aliases: Optional[list[str]] = None
    instruction: Optional[str] = Field(None, max_length=1000)
    parameters: Optional[dict[str, Any]] = None
    active: Optional[bool] = None
    order: Optional[int] = Field(None, ge=0)
    engine_compatibility: Optional[dict[str, str]] = None


class StyleDuplicateBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.patch("/voices/{voice_id}")
async def patch_voice(voice_id: str, body: VoicePatch):
    try:
        if body.name:
            return voice_profiles.rename_voice(voice_id, body.name)
        return voice_profiles.get_voice(voice_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/voices/{voice_id}/events")
async def list_events(voice_id: str):
    try:
        return {"items": voice_profiles.list_events(voice_id)}
    except Exception as exc:
        raise _http_error(exc)


@router.post("/voices/{voice_id}/events/{event_id}")
async def upload_event(
    voice_id: str,
    event_id: str,
    file: UploadFile = File(...),
    source: str = Form("upload"),
):
    content = await file.read()
    ext = os.path.splitext(file.filename or "")[1] or ".webm"
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: voice_profiles.set_event(
                voice_id,
                event_id,
                audio_bytes=content,
                original_ext=ext,
                source=source,
            ),
        )
    except Exception as exc:
        raise _http_error(exc)


@router.get("/voices/{voice_id}/events/{event_id}")
async def get_event_audio(voice_id: str, event_id: str):
    try:
        path = voice_profiles.event_audio_path(voice_id, event_id)
    except Exception as exc:
        raise _http_error(exc)
    return FileResponse(str(path), media_type="audio/wav")


@router.delete("/voices/{voice_id}/events/{event_id}")
async def delete_event(voice_id: str, event_id: str):
    try:
        return voice_profiles.delete_event(voice_id, event_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/voices/{voice_id}/styles")
async def list_styles(voice_id: str):
    try:
        return {"items": voice_profiles.get_voice(voice_id).get("styles", {}).get("items", [])}
    except Exception as exc:
        raise _http_error(exc)


@router.post("/voices/{voice_id}/styles")
async def create_style(voice_id: str, body: StyleCreateBody):
    try:
        return voice_profiles.create_style(
            voice_id,
            name=body.name,
            description=body.description,
            aliases=body.aliases,
            instruction=body.instruction,
            parameters=body.parameters,
            engine_compatibility=body.engine_compatibility,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.patch("/voices/{voice_id}/styles/{style_id}")
async def patch_style(voice_id: str, style_id: str, body: StylePatchBody):
    try:
        return voice_profiles.update_style(
            voice_id,
            style_id,
            name=body.name,
            description=body.description,
            aliases=body.aliases,
            instruction=body.instruction,
            parameters=body.parameters,
            active=body.active,
            order=body.order,
            engine_compatibility=body.engine_compatibility,
        )
    except Exception as exc:
        raise _http_error(exc)


@router.post("/voices/{voice_id}/styles/{style_id}/duplicate")
async def duplicate_style(voice_id: str, style_id: str, body: StyleDuplicateBody):
    try:
        return voice_profiles.duplicate_style(voice_id, style_id, name=body.name)
    except Exception as exc:
        raise _http_error(exc)


@router.delete("/voices/{voice_id}/styles/{style_id}")
async def delete_style(voice_id: str, style_id: str):
    try:
        return voice_profiles.delete_style(voice_id, style_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post("/voices/{voice_id}/styles/{style_id}/reference")
async def upload_style_reference(voice_id: str, style_id: str, file: UploadFile = File(...)):
    content = await file.read()
    ext = os.path.splitext(file.filename or "")[1] or ".webm"
    loop = asyncio.get_running_loop()
    try:
        style = await loop.run_in_executor(
            None,
            lambda: voice_profiles.set_style_reference(
                voice_id,
                style_id,
                audio_bytes=content,
                original_ext=ext,
            ),
        )
    except Exception as exc:
        raise _http_error(exc)
    return style


@router.get("/voices/{voice_id}/styles/{style_id}/reference")
async def get_style_reference_audio(voice_id: str, style_id: str):
    try:
        path = voice_profiles.style_reference_path(voice_id, style_id)
    except voice_profiles.VoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Referência de estilo não encontrada.")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/voices/{voice_id}/styles/{style_id}/original")
async def get_style_original_audio(voice_id: str, style_id: str):
    try:
        path = voice_profiles.style_original_path(voice_id, style_id)
    except voice_profiles.VoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Original de estilo nÃ£o encontrado.")
    return FileResponse(str(path), media_type="audio/wav")


@router.delete("/voices/{voice_id}/styles/{style_id}/reference")
async def delete_style_reference(voice_id: str, style_id: str):
    try:
        return voice_profiles.clear_style_reference(voice_id, style_id)
    except Exception as exc:
        raise _http_error(exc)


@router.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str):
    try:
        return voice_profiles.delete_voice(voice_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post("/voices/{voice_id}/set-default")
async def set_default(voice_id: str):
    try:
        return voice_profiles.set_default(voice_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post("/voices/{voice_id}/rebuild")
async def rebuild_voice(voice_id: str):
    """Reprocessa os embeddings; preserva a prévia anterior para comparação A/B."""
    loop = asyncio.get_running_loop()
    try:
        preview = voice_profiles.preview_path(voice_id)
        if preview.exists():
            os.replace(preview, voice_profiles.previous_preview_path(voice_id))
        status = await loop.run_in_executor(None, voice_profiles.build_embeddings, voice_id)
    except Exception as exc:
        raise _http_error(exc)
    return {"voice_id": voice_id, "embeddings": status}


@router.post("/voices/{voice_id}/preview")
async def generate_preview(voice_id: str):
    """Gera a prévia padrão em PT-BR com a própria voz (sem fallback)."""
    from services.vibevoice_tts_1_5b import VoiceUnavailableError, generate_voice_1_5b_with_metadata

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: generate_voice_1_5b_with_metadata(
                text=PREVIEW_TEXT, voice_id=voice_id, failure_policy="fail",
            ),
        )
        voice_profiles.preview_path(voice_id).write_bytes(result["wav_bytes"])
        record_app_event("voice_preview_generated", voice_id=voice_id,
                         output_bytes=len(result["wav_bytes"]))
    except VoiceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise _http_error(exc)
    return {
        "voice_id": voice_id,
        "engine_label": result["engine_label"],
        "fallback": result["fallback"],
        "params_used": result.get("params_used"),
        "duration_seconds": round(len(result["wav_bytes"]) / 2 / 24000, 2),
    }


@router.post("/voices/{voice_id}/validate")
async def validate_voice(voice_id: str):
    """Teste objetivo de INTELIGIBILIDADE (não de semelhança vocal): gera
    'Olá, mundo.' e transcreve com o Whisper turbo."""
    from services.vibevoice_tts_1_5b import VoiceUnavailableError, generate_voice_1_5b_with_metadata

    def _run():
        result = generate_voice_1_5b_with_metadata(
            text=VALIDATION_TEXT, voice_id=voice_id, failure_policy="fail",
        )
        import tempfile

        from faster_whisper import WhisperModel
        from services.model_manager import get_whisper_cache_dir

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(result["wav_bytes"])
            wav_path = tmp.name
        try:
            whisper = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8",
                                   download_root=str(get_whisper_cache_dir()))
            segments, info = whisper.transcribe(wav_path, beam_size=5,
                                                vad_filter=True, language="pt")
            transcript = " ".join(s.text.strip() for s in segments).strip()
        finally:
            os.unlink(wav_path)

        import re
        import unicodedata

        def norm(text):
            text = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                           if unicodedata.category(c) != "Mn")
            return set(re.sub(r"[^\w\s]", " ", text).split())

        expected, got = norm(VALIDATION_TEXT), norm(transcript)
        recovered = len(expected & got)
        status = "validada" if recovered >= len(expected) - 0 else (
            "parcial" if recovered >= 1 else "reprovada")
        return {
            "status": status,
            "expected": VALIDATION_TEXT,
            "transcript": transcript,
            "language": info.language,
            "language_probability": round(float(info.language_probability), 2),
            "validated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
            "note": "Valida inteligibilidade da síntese, não semelhança com a voz original.",
        }

    loop = asyncio.get_running_loop()
    try:
        validation = await loop.run_in_executor(None, _run)
        return {"voice": voice_profiles.record_validation(voice_id, validation),
                "validation": validation}
    except VoiceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise _http_error(exc)


@router.get("/voices/{voice_id}/reference")
async def get_reference_audio(voice_id: str):
    try:
        path = voice_profiles.reference_path(voice_id)
    except voice_profiles.VoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Referência não encontrada.")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/voices/{voice_id}/references/chatterbox")
async def get_chatterbox_reference_audio(voice_id: str):
    try:
        path = voice_profiles.chatterbox_reference_path(voice_id)
    except voice_profiles.VoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not path.exists():
        raise HTTPException(status_code=422, detail="Referência Chatterbox ainda não está utilizável.")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/voices/{voice_id}/preview")
async def get_preview_audio(voice_id: str, previous: bool = False):
    try:
        path = (voice_profiles.previous_preview_path(voice_id) if previous
                else voice_profiles.preview_path(voice_id))
    except voice_profiles.VoiceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Prévia ainda não gerada.")
    return FileResponse(str(path), media_type="audio/wav")


@router.get("/voices/{voice_id}/export")
async def export_voice(voice_id: str):
    try:
        payload = voice_profiles.export_voice(voice_id)
    except Exception as exc:
        raise _http_error(exc)
    return StreamingResponse(
        io.BytesIO(payload), media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=voz-{voice_id}.zip"},
    )

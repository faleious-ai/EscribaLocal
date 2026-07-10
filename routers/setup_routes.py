from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from services import config_store, env_check, presets, voice_profiles

router = APIRouter(prefix="/api/setup", tags=["setup"])
VOICE_REQUIRED_TTS_MODELS = {
    "tts_1_5b",
    "tts_large",
    "realtime_0_5b",
    "chatterbox-tts-pt-br",
}

class TtsSetupStatus(BaseModel):
    configured: bool
    requires_voice: bool
    ready: bool
    status: str
    custom_voice_count: int
    default_voice_id: Optional[str] = None
    action: str


class SetupStatusResponse(BaseModel):
    first_run_completed: bool
    environment_ok: bool
    setup_ready: bool
    suggested_preset: str
    retention: dict
    tts: TtsSetupStatus

@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status():
    settings = config_store.get_settings()
    env_report = env_check.run_all_checks()
    suggestion = presets.suggest_preset()
    voices = voice_profiles.list_voices()
    custom_voice_count = len(voices.get("custom", []))
    default_voice_id = voice_profiles.get_default_voice_id()
    tts_model = settings.defaults.tts.tts_model
    tts_configured = bool(tts_model)
    requires_voice = tts_model in VOICE_REQUIRED_TTS_MODELS
    # Uma voz existente, mas ainda não selecionada como padrão, não torna o
    # TTS utilizável pelo restante da aplicação.
    tts_ready = (not requires_voice) or bool(default_voice_id)
    environment_ok = env_report.get("overall") != "fail"
    
    return SetupStatusResponse(
        first_run_completed=settings.first_run_completed,
        environment_ok=environment_ok,
        setup_ready=environment_ok and tts_ready,
        suggested_preset=suggestion.get("preset_id", "baixa-memoria"),
        retention={
            "enabled": settings.retained_inputs_max_mb > 0,
            "max_mb": settings.retained_inputs_max_mb
        },
        tts=TtsSetupStatus(
            configured=tts_configured,
            requires_voice=requires_voice,
            ready=tts_ready,
            status="ready" if tts_ready else "pending_voice",
            custom_voice_count=custom_voice_count,
            default_voice_id=default_voice_id,
            action=(
                "tts_ready" if tts_ready
                else "create_or_import_voice"
            ),
        ),
    )

@router.post("/complete")
async def complete_setup():
    settings = config_store.get_settings()
    settings.first_run_completed = True
    config_store.save_settings(settings)
    return {"ok": True, "first_run_completed": True}

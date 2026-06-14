from fastapi import APIRouter
from pydantic import BaseModel
from services import config_store, env_check, presets

router = APIRouter(prefix="/api/setup", tags=["setup"])

class SetupStatusResponse(BaseModel):
    first_run_completed: bool
    environment_ok: bool
    suggested_preset: str
    retention: dict

@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status():
    settings = config_store.get_settings()
    env_report = env_check.run_all_checks()
    suggestion = presets.suggest_preset()
    
    return SetupStatusResponse(
        first_run_completed=settings.first_run_completed,
        environment_ok=(env_report.get("overall") != "fail"),
        suggested_preset=suggestion.get("preset_id", "baixa-memoria"),
        retention={
            "enabled": settings.retained_inputs_max_mb > 0,
            "max_mb": settings.retained_inputs_max_mb
        }
    )

@router.post("/complete")
async def complete_setup():
    settings = config_store.get_settings()
    settings.first_run_completed = True
    config_store.save_settings(settings)
    return {"ok": True, "first_run_completed": True}

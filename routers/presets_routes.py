"""Rotas de presets de configuração."""
import asyncio

from fastapi import APIRouter, HTTPException

from services import presets

router = APIRouter(prefix="/api", tags=["presets"])


@router.get("/presets")
async def list_presets():
    loop = asyncio.get_running_loop()
    enriched = await loop.run_in_executor(None, presets.get_presets_with_suitability)
    return {"presets": enriched}


@router.post("/presets/suggest")
async def suggest():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, presets.suggest_preset)


@router.post("/presets/{preset_id}/apply")
async def apply(preset_id: str):
    result = presets.apply_preset(preset_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Preset desconhecido: {preset_id}")
    settings, form_params = result
    return {"settings": settings.model_dump(), "form_params": form_params}

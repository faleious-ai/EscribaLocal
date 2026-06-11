"""Rotas de configuração persistente e perfis."""
from fastapi import APIRouter, HTTPException

from services import config_store
from services.config_store import ProfileBody, SettingsModel

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def get_config():
    return config_store.get_settings().model_dump()


@router.put("/config")
async def put_config(settings: SettingsModel):
    return config_store.save_settings(settings).model_dump()


@router.get("/profiles")
async def get_profiles():
    return {"profiles": config_store.list_profiles()}


@router.get("/profiles/{slug}")
async def get_profile(slug: str):
    try:
        profile = config_store.get_profile(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Perfil não encontrado: {slug}")
    return profile.model_dump()


@router.put("/profiles/{slug}")
async def put_profile(slug: str, body: ProfileBody):
    try:
        profile = config_store.save_profile(slug, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return profile.model_dump()


@router.delete("/profiles/{slug}")
async def delete_profile(slug: str):
    try:
        removed = config_store.delete_profile(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not removed:
        raise HTTPException(status_code=404, detail=f"Perfil não encontrado: {slug}")
    return {"deleted": slug}


@router.post("/profiles/{slug}/apply")
async def apply_profile(slug: str):
    try:
        settings = config_store.apply_profile(slug)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if settings is None:
        raise HTTPException(status_code=404, detail=f"Perfil não encontrado: {slug}")
    return settings.model_dump()

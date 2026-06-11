"""Rotas de configuração persistente e perfis."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import config_store
from services.config_store import EngineDefaults, ProfileBody, SettingsModel

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
    from services.presets import config_defaults_to_form_params

    payload = settings.model_dump()
    # form_params usa os nomes dos campos do formulário, prontos para a UI
    # preencher os controles sem mapear nada no cliente.
    payload["form_params"] = config_defaults_to_form_params(settings.defaults.model_dump())
    return payload


class ProfileFromFormBody(BaseModel):
    """Salvar perfil a partir dos valores atuais do formulário (nomes de
    formulário; a conversão para o shape do config store é feita aqui)."""
    name: str = Field(min_length=1, max_length=80)
    notes: str = Field("", max_length=2000)
    base_preset: Optional[str] = None
    engine_params_form: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


@router.post("/profiles/{slug}/save-from-form")
async def save_profile_from_form(slug: str, body: ProfileFromFormBody):
    from services.presets import form_params_to_config_defaults

    converted = form_params_to_config_defaults(body.engine_params_form)
    # Completa com os defaults atuais para campos não enviados pelo formulário.
    base = config_store.get_settings().defaults.model_dump()
    for engine, params in converted.items():
        base.setdefault(engine, {}).update(params)
    try:
        engine_defaults = EngineDefaults.model_validate(base)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Parâmetros inválidos: {exc}")

    profile_body = ProfileBody(
        name=body.name, notes=body.notes, base_preset=body.base_preset,
        engine_params=engine_defaults,
    )
    try:
        profile = config_store.save_profile(slug, profile_body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return profile.model_dump()

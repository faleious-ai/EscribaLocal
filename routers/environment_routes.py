"""Rotas do verificador de ambiente e da instalação controlada de pacotes."""
import asyncio
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import env_check

router = APIRouter(prefix="/api", tags=["environment"])


class InstallPlanRequest(BaseModel):
    packages: List[str] = Field(min_length=1, max_length=30)


class InstallRequest(InstallPlanRequest):
    confirm: bool = False
    confirm_hot: bool = False


@router.get("/environment")
async def environment_report(refresh: bool = False):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, env_check.run_all_checks, refresh)


@router.post("/environment/install/plan")
async def install_plan(payload: InstallPlanRequest):
    """Plano + dry-run: mostra o comando exato e o que o pip faria, sem
    alterar nada. Obrigatório antes de confirmar a instalação."""
    loop = asyncio.get_running_loop()
    try:
        plan = env_check.plan_install(payload.packages)
        dry_run = await loop.run_in_executor(None, env_check.run_dry_run, payload.packages)
    except env_check.InstallValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {**plan, "dry_run": dry_run}


@router.post("/environment/install")
async def install(payload: InstallRequest):
    try:
        result = env_check.start_install_job(
            payload.packages, confirm=payload.confirm, confirm_hot=payload.confirm_hot,
        )
    except env_check.InstallValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result

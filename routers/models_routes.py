"""Rotas do gestor de modelos: catálogo, download por job e remoção."""
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services import model_manager

router = APIRouter(prefix="/api", tags=["models"])


class DownloadRequest(BaseModel):
    model_id: str


@router.get("/models")
async def list_models():
    loop = asyncio.get_running_loop()
    catalog = await loop.run_in_executor(None, model_manager.get_catalog_with_status)
    return {"models": catalog}


@router.post("/models/download")
async def download_model(payload: DownloadRequest):
    try:
        job_id = model_manager.start_download_job(payload.model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Modelo desconhecido: {payload.model_id}")
    except model_manager.ModelAlreadyInstalled:
        raise HTTPException(status_code=409, detail="Este modelo já está instalado.")
    return {"job_id": job_id, "model_id": payload.model_id}


@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, model_manager.delete_model, model_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Modelo desconhecido: {model_id}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Este modelo não está instalado no disco.")
    except model_manager.ModelLoadedInMemory as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result

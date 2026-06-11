"""Rotas do registro central de parâmetros e validação."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.parameters_registry import get_engine_specs, get_registry, validate_params
from dataclasses import asdict

router = APIRouter(prefix="/api", tags=["parameters"])


class ValidateRequest(BaseModel):
    engine: str
    params: Dict[str, Any] = Field(default_factory=dict)


@router.get("/parameters")
async def list_parameters():
    return {"engines": get_registry()}


@router.get("/parameters/{engine}")
async def engine_parameters(engine: str):
    try:
        specs = get_engine_specs(engine)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Engine desconhecida: {engine}")
    return {"engine": engine, "parameters": [asdict(spec) for spec in specs]}


@router.post("/parameters/validate")
async def validate(payload: ValidateRequest):
    try:
        return validate_params(payload.engine, payload.params)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Engine desconhecida: {payload.engine}")

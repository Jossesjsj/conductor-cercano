"""Resultados de benchmarks reales generados por benchmark/ (solo lectura)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.configuracion.ajustes import RAIZ_PROYECTO

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])
DIRECTORIO = RAIZ_PROYECTO / "benchmark" / "resultados"


@router.get("")
def listar() -> dict[str, Any]:
    resultados: dict[str, Any] = {}
    for ruta in sorted(DIRECTORIO.glob("*.json")):
        try:
            resultados[ruta.stem] = json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return {"resultados": resultados, "graficos": sorted(p.name for p in DIRECTORIO.glob("*.png"))}


@router.get("/graficos/{nombre}")
def grafico(nombre: str) -> FileResponse:
    ruta = (DIRECTORIO / nombre).resolve()
    if ruta.parent != DIRECTORIO.resolve() or ruta.suffix != ".png" or not ruta.exists():
        raise HTTPException(404, "Gráfico no encontrado")
    return FileResponse(ruta, media_type="image/png")

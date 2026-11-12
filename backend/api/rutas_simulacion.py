"""Endpoints de configuración, control y consulta de la simulación."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Body, Depends, Query

from backend.api.dependencias import Contenedor, obtener_contenedor
from backend.api.esquemas import AccionControl, ConfiguracionEntrada, ParametrosEnCaliente

router = APIRouter(prefix="/api", tags=["simulacion"])


@router.get("/simulacion")
def estado(contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    return contenedor.simulacion.estado_simulacion()


@router.post("/simulacion/configurar")
async def configurar(entrada: ConfiguracionEntrada, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    return await contenedor.simulacion.configurar(entrada.model_dump())


@router.patch("/simulacion/parametros")
def parametros(entrada: ParametrosEnCaliente, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    return contenedor.simulacion.actualizar_parametros_en_caliente(entrada.model_dump(exclude_none=True))


@router.post("/simulacion/{accion}")
async def controlar(
    accion: Literal["iniciar", "pausar", "reanudar", "detener", "avanzar", "reiniciar", "acelerar", "desacelerar", "modo"],
    entrada: Optional[AccionControl] = Body(None),
    contenedor: Contenedor = Depends(obtener_contenedor),
) -> dict[str, Any]:
    return await contenedor.simulacion.controlar(accion, entrada.factor if entrada else None)


@router.get("/simulacion/configuraciones")
def configuraciones(contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    return contenedor.repositorio.listar_configuraciones()


@router.get("/simulacion/resultados")
def resultados(contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    return contenedor.repositorio.listar_resultados_simulacion()


@router.get("/estadisticas")
def estadisticas(contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    return contenedor.simulacion.estadisticas()


@router.get("/metricas")
def metricas(tipo: Optional[str] = None, contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    return contenedor.repositorio.listar_metricas(tipo)


@router.get("/conductores")
def conductores(
    limites: Optional[str] = Query(None, description="oeste,sur,este,norte"),
    estado: Optional[Literal["DISPONIBLE", "OCUPADO", "EN_SERVICIO", "INACTIVO"]] = None,
    limite: int = Query(500, ge=1, le=50_000),
    contenedor: Contenedor = Depends(obtener_contenedor),
) -> dict[str, Any]:
    caja = [float(v) for v in limites.split(",")] if limites else None
    return contenedor.simulacion.listar_conductores(caja, estado, limite)


@router.get("/conductores/{id_conductor}")
def conductor(id_conductor: int, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    return contenedor.simulacion.obtener_conductor(id_conductor)


@router.get("/servicios/activos")
def servicios_activos(contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    return contenedor.simulacion.servicios_activos()


@router.get("/seguimiento/{id_pasajero}")
def seguimiento(id_pasajero: int, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    """Estado en vivo de un viaje: conductor en camino, pasajero a bordo o llegada."""
    return contenedor.simulacion.seguimiento(id_pasajero)

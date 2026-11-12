"""Solicitudes de servicio, historial de asignaciones, mapas Folium y geocodificación."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from backend.api.dependencias import Contenedor, obtener_contenedor
from backend.api.esquemas import SolicitudCotizacion, SolicitudServicio
from backend.servicios.geocodificacion import ErrorGeocodificacion
from backend.servicios.mapas_folium import generar_mapa_asignacion

router = APIRouter(prefix="/api", tags=["solicitudes"])


@router.post("/solicitudes")
async def crear_solicitud(entrada: SolicitudServicio, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    o, d = entrada.origen, entrada.destino
    return await contenedor.simulacion.solicitar_servicio(o.latitud, o.longitud, d.latitud, d.longitud, o.direccion,
                                                          d.direccion, entrada.id_conductor)


@router.post("/solicitudes/cotizar")
async def cotizar(entrada: SolicitudCotizacion, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    """Conductores disponibles y los k candidatos con su ETA real, SIN asignar."""
    o, d = entrada.origen, entrada.destino
    return await contenedor.simulacion.cotizar(o.latitud, o.longitud, d.latitud, d.longitud)


@router.get("/solicitudes/rechazadas")
def rechazadas(contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    return contenedor.repositorio.listar_solicitudes_rechazadas()


@router.get("/asignaciones")
def listar_asignaciones(
    pagina: int = Query(1, ge=1), tamano: int = Query(25, ge=1, le=200),
    distrito: Optional[str] = None, estado: Optional[str] = None, origen: Optional[str] = None,
    contenedor: Contenedor = Depends(obtener_contenedor),
) -> dict[str, Any]:
    return contenedor.repositorio.listar_asignaciones(pagina, tamano, distrito, estado, origen)


@router.get("/asignaciones/{id_asignacion}")
def detalle_asignacion(id_asignacion: int, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    detalle = contenedor.repositorio.obtener_asignacion(id_asignacion)
    if detalle is None:
        raise HTTPException(404, f"Asignación {id_asignacion} no encontrada")
    return detalle


@router.get("/asignaciones/{id_asignacion}/mapa", response_class=HTMLResponse)
async def mapa_asignacion(id_asignacion: int, contenedor: Contenedor = Depends(obtener_contenedor)) -> HTMLResponse:
    detalle = contenedor.repositorio.obtener_asignacion(id_asignacion)
    if detalle is None:
        raise HTTPException(404, f"Asignación {id_asignacion} no encontrada")
    limite = contenedor.catalogo.geojson_distrito(detalle["id_distrito"])
    html = await asyncio.to_thread(generar_mapa_asignacion, detalle, limite)
    return HTMLResponse(html)


@router.get("/geocodificar")
async def geocodificar(q: str = Query(..., min_length=3, max_length=200),
                       contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    motor = contenedor.simulacion.motor
    limites = motor.grafo.limites.como_lista() if motor else None
    try:
        return await asyncio.to_thread(contenedor.geocodificador.buscar, q, limites)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except ErrorGeocodificacion as error:
        raise HTTPException(503, f"{error}. Alternativa: seleccione el punto en el mapa o ingrese coordenadas.") from error


@router.get("/geocodificar/inversa")
async def geocodificar_inversa(latitud: float = Query(..., ge=-90, le=90), longitud: float = Query(..., ge=-180, le=180),
                               contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(contenedor.geocodificador.inversa, latitud, longitud)
    except ErrorGeocodificacion as error:
        raise HTTPException(503, str(error)) from error

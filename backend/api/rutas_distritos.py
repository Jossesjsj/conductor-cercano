"""Endpoints de distritos y redes viales."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.api.dependencias import Contenedor, obtener_contenedor

router = APIRouter(prefix="/api/distritos", tags=["distritos"])


@router.get("")
def listar_distritos(contenedor: Contenedor = Depends(obtener_contenedor)) -> list[dict[str, Any]]:
    salida = []
    for distrito in contenedor.catalogo.listar():
        datos = distrito.resumen()
        progreso = contenedor.gestor_grafos.obtener_progreso(distrito.id_distrito)
        datos["estado_descarga"] = progreso.estado
        datos["descargado"] = contenedor.gestor_grafos.esta_descargado(distrito.id_distrito)
        meta = contenedor.gestor_grafos.leer_metadatos(distrito.id_distrito) if datos["descargado"] else None
        datos["nodos"] = meta["nodos"] if meta else None
        datos["aristas"] = meta["aristas"] if meta else None
        salida.append(datos)
    return salida


@router.get("/limites")
def limites_todos(contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    """Polígonos simplificados de todos los distritos (selector en el mapa)."""
    return {"type": "FeatureCollection", "features": [
        contenedor.catalogo.geojson_distrito(d.id_distrito, 0.0003) for d in contenedor.catalogo.listar()
    ]}


@router.get("/{id_distrito}")
def obtener_distrito(id_distrito: str, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    geo = contenedor.catalogo.geojson_distrito(id_distrito)
    if geo is None:
        raise HTTPException(404, f"Distrito desconocido: {id_distrito}")
    return {"distrito": geo["properties"], "limite": geo, "estado": contenedor.gestor_grafos.estado_como_diccionario(id_distrito)}


@router.get("/{id_distrito}/estado")
def estado_descarga(id_distrito: str, contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    if contenedor.catalogo.obtener(id_distrito) is None:
        raise HTTPException(404, f"Distrito desconocido: {id_distrito}")
    return contenedor.gestor_grafos.estado_como_diccionario(id_distrito)


@router.post("/{id_distrito}/descargar", status_code=202)
def descargar(id_distrito: str, forzar: bool = Query(False, description="Actualizar aunque exista localmente"),
              contenedor: Contenedor = Depends(obtener_contenedor)) -> dict[str, Any]:
    try:
        contenedor.gestor_grafos.solicitar_descarga(id_distrito, forzar)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return contenedor.gestor_grafos.estado_como_diccionario(id_distrito)


_cache_red: dict[str, dict[str, Any]] = {}


@router.get("/{id_distrito}/red-vial")
async def red_vial(id_distrito: str, contenedor: Contenedor = Depends(obtener_contenedor)) -> JSONResponse:
    """Calles (sentido único/doble) e intersecciones del grafo procesado."""
    if not contenedor.gestor_grafos.esta_descargado(id_distrito):
        raise HTTPException(409, "Red vial no descargada")
    if id_distrito not in _cache_red:
        grafo = await asyncio.to_thread(contenedor.gestor_grafos.cargar_grafo, id_distrito)
        _cache_red[id_distrito] = await asyncio.to_thread(grafo.a_geojson)
    return JSONResponse(_cache_red[id_distrito], headers={"Cache-Control": "public, max-age=3600"})

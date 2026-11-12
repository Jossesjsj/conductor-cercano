"""Contenedor de servicios compartidos por los routers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from backend.configuracion.ajustes import Ajustes
from backend.servicios.catalogo_distritos import CatalogoDistritos
from backend.servicios.geocodificacion import Geocodificador
from backend.servicios.gestor_grafos import GestorGrafos
from backend.servicios.repositorio import Repositorio
from backend.servicios.servicio_simulacion import ServicioSimulacion
from backend.servicios.tiempo_real import GestorTiempoReal


@dataclass
class Contenedor:
    ajustes: Ajustes
    catalogo: CatalogoDistritos
    gestor_grafos: GestorGrafos
    repositorio: Repositorio
    tiempo_real: GestorTiempoReal
    simulacion: ServicioSimulacion
    geocodificador: Geocodificador


def obtener_contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor

"""Punto de entrada FastAPI de CONDUCTOR CERCANO.

Ejecutar desde la raíz del proyecto:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.api import rutas_benchmark, rutas_distritos, rutas_simulacion, rutas_solicitudes, websocket
from backend.api.dependencias import Contenedor
from backend.configuracion.ajustes import Ajustes, obtener_ajustes
from backend.modelos.base_datos import BaseDatos
from backend.servicios.catalogo_distritos import CatalogoDistritos
from backend.servicios.geocodificacion import Geocodificador
from backend.servicios.gestor_grafos import EstadoDescarga, GestorGrafos
from backend.servicios.repositorio import Repositorio
from backend.servicios.servicio_simulacion import ErrorServicio, ServicioSimulacion
from backend.servicios.tiempo_real import GestorTiempoReal

logger = logging.getLogger("conductor_cercano")
VERSION = "1.0.0"


def construir_contenedor(ajustes: Ajustes) -> Contenedor:
    catalogo = CatalogoDistritos(ajustes)
    gestor_grafos = GestorGrafos(ajustes, catalogo)
    repositorio = Repositorio(BaseDatos(ajustes.url_sqlalchemy))
    tiempo_real = GestorTiempoReal(ajustes.maximo_conductores_por_mensaje)
    simulacion = ServicioSimulacion(catalogo, gestor_grafos, repositorio, tiempo_real)
    geocodificador = Geocodificador(ajustes.url_nominatim, ajustes.agente_usuario,
                                    ajustes.directorio_cache / "geocodificacion.json", ajustes.intervalo_minimo_nominatim_s)
    return Contenedor(ajustes, catalogo, gestor_grafos, repositorio, tiempo_real, simulacion, geocodificador)


async def precargar_simulacion(contenedor: Contenedor) -> None:
    """Deja lista una simulación (detenida) con el distrito por defecto o el último usado."""
    ajustes = contenedor.ajustes
    try:
        ultima = await asyncio.to_thread(contenedor.repositorio.ultima_configuracion)
        id_distrito = (ultima or {}).get("id_distrito") or ajustes.distrito_por_defecto
        await asyncio.to_thread(contenedor.catalogo.cargar)
        if not contenedor.gestor_grafos.esta_descargado(id_distrito):
            id_distrito = ajustes.distrito_por_defecto
            contenedor.gestor_grafos.solicitar_descarga(id_distrito)
            while contenedor.gestor_grafos.obtener_progreso(id_distrito).estado not in (EstadoDescarga.LISTO, EstadoDescarga.ERROR):
                await asyncio.sleep(1.0)
            if not contenedor.gestor_grafos.esta_descargado(id_distrito):
                logger.warning("No se pudo precargar %s", id_distrito)
                return
        datos = {k: v for k, v in (ultima or {}).items() if k not in ("id", "fecha")} if ultima else {}
        datos.update({"id_distrito": id_distrito})
        datos.setdefault("cantidad_conductores", ajustes.conductores_por_defecto)
        await contenedor.simulacion.configurar(datos)
        logger.info("Simulación precargada en %s", id_distrito)
    except Exception:
        logger.exception("Fallo en la precarga de la simulación")


def crear_aplicacion(ajustes: Optional[Ajustes] = None, contenedor: Optional[Contenedor] = None) -> FastAPI:
    ajustes = ajustes or obtener_ajustes()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def ciclo_vida(app: FastAPI):
        c = contenedor or construir_contenedor(ajustes)
        app.state.contenedor = c
        interrumpidos = await asyncio.to_thread(c.repositorio.marcar_servicios_interrumpidos)
        if interrumpidos:
            logger.info("%d servicios de una ejecución anterior marcados como INTERRUMPIDO", interrumpidos)
        c.simulacion.arrancar()
        tarea_precarga = asyncio.create_task(precargar_simulacion(c)) if ajustes.precargar_distrito else None
        yield
        if tarea_precarga is not None:
            tarea_precarga.cancel()
        await c.simulacion.apagar()

    app = FastAPI(title="CONDUCTOR CERCANO API", version=VERSION, lifespan=ciclo_vida,
                  description="Asignación de conductores con Quadtree, Haversine, heap y Dijkstra propios sobre OSM.")
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    app.add_middleware(CORSMiddleware, allow_origins=ajustes.lista_origenes_cors, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ErrorServicio)
    async def manejar_error_servicio(_: Request, error: ErrorServicio) -> JSONResponse:
        return JSONResponse(status_code=error.codigo_http, content={"detail": str(error)})

    @app.get("/api/salud", tags=["sistema"])
    def salud(request: Request) -> dict:
        c: Contenedor = request.app.state.contenedor
        motor = c.simulacion.motor
        return {
            "estado": "ok", "version": VERSION, "entorno": ajustes.entorno,
            "simulacion_configurada": motor is not None,
            "distrito": motor.configuracion.id_distrito if motor else None,
            "grafos_descargados": c.gestor_grafos.listar_descargados(),
            "clientes_ws": len(c.tiempo_real.clientes),
        }

    for modulo in (rutas_distritos, rutas_simulacion, rutas_solicitudes, rutas_benchmark, websocket):
        app.include_router(modulo.router)

    _montar_frontend(app, ajustes.directorio_frontend)
    return app


def _montar_frontend(app: FastAPI, directorio: Path) -> None:
    """Sirve el build de React (si existe) con *fallback* SPA. En desarrollo se usa Vite."""
    indice = directorio / "index.html"
    if not indice.exists():
        return
    raiz = directorio.resolve()

    @app.get("/{ruta:path}", include_in_schema=False)
    async def spa(ruta: str):
        if ruta.startswith(("api/", "ws/")):
            return JSONResponse({"detail": "No encontrado"}, status_code=404)
        archivo = (directorio / ruta).resolve()
        if ruta and archivo.is_file() and raiz in archivo.parents:
            return FileResponse(archivo)
        return FileResponse(indice)


app = crear_aplicacion()

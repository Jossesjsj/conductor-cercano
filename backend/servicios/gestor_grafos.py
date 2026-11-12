"""Descarga, procesamiento, almacenamiento y reutilización de redes viales por distrito.

Flujo de obtención (``fuente_osm``):
  1. ``overpass``: OSMnx ``graph_from_polygon(network_type="drive")`` contra la API Overpass.
  2. ``extracto``: extracto PBF de OSM (BBBike Lima) recortado localmente al polígono del distrito.
  ``auto`` intenta 1 y, si Overpass no responde a tiempo, usa 2.
Los grafos se guardan en ``datos/grafos/<distrito>.graphml`` y no se vuelven a descargar
salvo actualización manual (``forzar=True``).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as TimeoutFuturo
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

from backend.configuracion.ajustes import Ajustes
from backend.servicios.catalogo_distritos import CatalogoDistritos, Distrito
from backend.servicios.fuente_osm import extraer_red_vial_a_xml
from estructuras.grafo_vial import GrafoVial

logger = logging.getLogger(__name__)


class EstadoDescarga:
    NO_DESCARGADO = "NO_DESCARGADO"
    EN_COLA = "EN_COLA"
    DESCARGANDO = "DESCARGANDO"
    PROCESANDO = "PROCESANDO"
    LISTO = "LISTO"
    ERROR = "ERROR"


@dataclass
class ProgresoDistrito:
    id_distrito: str
    estado: str = EstadoDescarga.NO_DESCARGADO
    mensaje: str = ""
    error: str = ""
    fuente: str = ""
    actualizado: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def actualizar(self, estado: str, mensaje: str = "", error: str = "") -> None:
        self.estado, self.mensaje, self.error = estado, mensaje, error
        self.actualizado = datetime.now(timezone.utc).isoformat()


class ErrorDescargaGrafo(RuntimeError):
    pass


class GestorGrafos:
    def __init__(self, ajustes: Ajustes, catalogo: CatalogoDistritos) -> None:
        self.ajustes = ajustes
        self.catalogo = catalogo
        self._progreso: dict[str, ProgresoDistrito] = {}
        self._grafos_en_memoria: dict[str, GrafoVial] = {}
        self._cerrojo = threading.Lock()
        self._cerrojo_descarga = threading.Lock()  # una descarga/proceso a la vez (memoria y cortesía con OSM)
        self._ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="grafos")

    # ------------------------------------------------------------ rutas
    def ruta_grafo(self, id_distrito: str) -> Path:
        return self.ajustes.directorio_grafos / f"{id_distrito}.graphml"

    def ruta_metadatos(self, id_distrito: str) -> Path:
        return self.ajustes.directorio_grafos / f"{id_distrito}.json"

    def esta_descargado(self, id_distrito: str) -> bool:
        return self.ruta_grafo(id_distrito).exists() and self.ruta_metadatos(id_distrito).exists()

    def leer_metadatos(self, id_distrito: str) -> Optional[dict[str, Any]]:
        ruta = self.ruta_metadatos(id_distrito)
        return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None

    # ------------------------------------------------------------ estado
    def obtener_progreso(self, id_distrito: str) -> ProgresoDistrito:
        with self._cerrojo:
            progreso = self._progreso.get(id_distrito)
            if progreso is None:
                progreso = ProgresoDistrito(id_distrito)
                if self.esta_descargado(id_distrito):
                    meta = self.leer_metadatos(id_distrito) or {}
                    progreso.actualizar(EstadoDescarga.LISTO, "Red vial almacenada localmente")
                    progreso.fuente = meta.get("fuente", "")
                self._progreso[id_distrito] = progreso
            return progreso

    def estado_como_diccionario(self, id_distrito: str) -> dict[str, Any]:
        datos = asdict(self.obtener_progreso(id_distrito))
        datos["descargado"] = self.esta_descargado(id_distrito)
        datos["metadatos"] = self.leer_metadatos(id_distrito)
        return datos

    # ------------------------------------------------------------ descarga
    def solicitar_descarga(self, id_distrito: str, forzar: bool = False) -> ProgresoDistrito:
        """Encola la descarga en segundo plano (no bloquea la API)."""
        distrito = self._validar_distrito(id_distrito)
        progreso = self.obtener_progreso(id_distrito)
        if progreso.estado in (EstadoDescarga.EN_COLA, EstadoDescarga.DESCARGANDO, EstadoDescarga.PROCESANDO):
            return progreso
        if self.esta_descargado(id_distrito) and not forzar:
            progreso.actualizar(EstadoDescarga.LISTO, "Red vial ya almacenada: se reutiliza sin descargar")
            return progreso
        progreso.actualizar(EstadoDescarga.EN_COLA, "Descarga en cola")
        self._ejecutor.submit(self._descargar_seguro, distrito, forzar)
        return progreso

    def _validar_distrito(self, id_distrito: str) -> Distrito:
        distrito = self.catalogo.obtener(id_distrito)
        if distrito is None:
            raise KeyError(f"Distrito desconocido: {id_distrito}")
        if not distrito.elegible:
            raise ValueError(
                f"{distrito.nombre} no es elegible (área {distrito.area_km2:.2f} km², mínimo "
                f"{self.ajustes.area_minima_distrito_km2} km², cobertura completa={distrito.cobertura_completa})"
            )
        return distrito

    def _descargar_seguro(self, distrito: Distrito, forzar: bool) -> None:
        progreso = self.obtener_progreso(distrito.id_distrito)
        try:
            self.descargar_y_guardar(distrito, forzar)
        except Exception as error:  # se informa al frontend
            logger.exception("Error descargando %s", distrito.id_distrito)
            progreso.actualizar(EstadoDescarga.ERROR, "La descarga falló", f"{type(error).__name__}: {error}")

    def descargar_y_guardar(self, distrito: Distrito, forzar: bool = False) -> dict[str, Any]:
        """Descarga síncrona (también usada por scripts)."""
        import osmnx as ox

        with self._cerrojo_descarga:
            if self.esta_descargado(distrito.id_distrito) and not forzar:
                return self.leer_metadatos(distrito.id_distrito) or {}
            progreso = self.obtener_progreso(distrito.id_distrito)
            inicio = time.perf_counter()
            grafo, fuente = self._obtener_grafo_networkx(distrito, progreso)
            progreso.actualizar(EstadoDescarga.PROCESANDO, "Guardando grafo GraphML")
            ox.save_graphml(grafo, self.ruta_grafo(distrito.id_distrito))
            metadatos = {
                "id_distrito": distrito.id_distrito,
                "nombre": distrito.nombre,
                "provincia": distrito.provincia,
                "fuente": fuente,
                "fecha_descarga": datetime.now(timezone.utc).isoformat(),
                "nodos": grafo.number_of_nodes(),
                "aristas": grafo.number_of_edges(),
                "area_km2": round(distrito.area_km2, 2),
                "segundos_procesamiento": round(time.perf_counter() - inicio, 1),
                "tipo_red": "drive (dirigida, sentidos de circulación de OSM)",
            }
            self.ruta_metadatos(distrito.id_distrito).write_text(json.dumps(metadatos, ensure_ascii=False, indent=2), encoding="utf-8")
            with self._cerrojo:
                self._grafos_en_memoria.pop(distrito.id_distrito, None)
            self._ruta_cache_binaria(distrito.id_distrito).unlink(missing_ok=True)
            progreso.fuente = fuente
            progreso.actualizar(EstadoDescarga.LISTO, f"Red vial lista: {metadatos['nodos']} nodos, {metadatos['aristas']} aristas")
            return metadatos

    def _obtener_grafo_networkx(self, distrito: Distrito, progreso: ProgresoDistrito):
        fuente = self.ajustes.fuente_osm.lower()
        errores: list[str] = []
        if fuente in ("auto", "overpass"):
            for url in self.ajustes.lista_urls_overpass:
                if not self._overpass_disponible(url):
                    errores.append(f"{url}: sin respuesta")
                    continue
                progreso.actualizar(EstadoDescarga.DESCARGANDO, f"Descargando red vial desde Overpass ({url})")
                try:
                    return self._descargar_overpass(distrito, url), f"overpass:{url}"
                except Exception as error:
                    errores.append(f"{url}: {type(error).__name__}: {error}")
                    logger.warning("Overpass falló (%s): %s", url, error)
            if fuente == "overpass":
                raise ErrorDescargaGrafo("Overpass no disponible: " + " | ".join(errores))
        progreso.actualizar(
            EstadoDescarga.DESCARGANDO,
            "Overpass no disponible; usando extracto OSM local" if errores else "Usando extracto OSM local",
        )
        return self._construir_desde_extracto(distrito, progreso), "extracto:" + self.ajustes.url_extracto_osm

    def _overpass_disponible(self, url: str) -> bool:
        try:
            r = requests.get(f"{url}/status", timeout=8, headers={"User-Agent": self.ajustes.agente_usuario})
            texto = r.text.lower()
            return r.status_code == 200 and ("slots available" in texto or "currently running" in texto)
        except requests.RequestException:
            return False

    def _descargar_overpass(self, distrito: Distrito, url: str):
        import osmnx as ox

        ox.settings.overpass_url = url
        ox.settings.requests_timeout = self.ajustes.tiempo_maximo_overpass_s
        ox.settings.http_user_agent = self.ajustes.agente_usuario
        ox.settings.use_cache = True
        ox.settings.cache_folder = str(self.ajustes.directorio_cache / "osmnx")
        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            futuro = ejecutor.submit(ox.graph_from_polygon, distrito.geometria, network_type="drive", simplify=True, retain_all=False)
            try:
                return futuro.result(timeout=self.ajustes.tiempo_maximo_overpass_s * 2)
            except TimeoutFuturo as error:
                raise ErrorDescargaGrafo("Tiempo de espera agotado en Overpass") from error

    def _construir_desde_extracto(self, distrito: Distrito, progreso: ProgresoDistrito):
        import networkx as nx
        import osmnx as ox
        from shapely import contains_xy

        ruta_pbf = self.catalogo.asegurar_extracto(lambda m: progreso.actualizar(EstadoDescarga.DESCARGANDO, m))
        progreso.actualizar(EstadoDescarga.PROCESANDO, "Filtrando vías conducibles del extracto OSM")
        # Margen de ~500 m para conservar las conexiones en el borde del distrito.
        oeste, sur, este, norte = distrito.geometria.bounds
        margen = 0.005
        ruta_xml = self.ajustes.directorio_cache / f"{distrito.id_distrito}.osm"
        extraer_red_vial_a_xml(ruta_pbf, (oeste - margen, sur - margen, este + margen, norte + margen), ruta_xml)

        progreso.actualizar(EstadoDescarga.PROCESANDO, "Construyendo grafo dirigido con OSMnx")
        grafo = ox.graph_from_xml(ruta_xml, bidirectional=False, simplify=False, retain_all=True)

        progreso.actualizar(EstadoDescarga.PROCESANDO, "Recortando al límite oficial del distrito")
        poligono = distrito.geometria.buffer(0.0008)  # ~90 m: evita cortar calles limítrofes
        identificadores = list(grafo.nodes)
        xs = [grafo.nodes[n]["x"] for n in identificadores]
        ys = [grafo.nodes[n]["y"] for n in identificadores]
        dentro = contains_xy(poligono, xs, ys)
        grafo = grafo.subgraph([n for n, d in zip(identificadores, dentro) if d]).copy()

        progreso.actualizar(EstadoDescarga.PROCESANDO, "Simplificando topología (intersecciones reales)")
        grafo = ox.simplify_graph(grafo)
        componente = max(nx.weakly_connected_components(grafo), key=len)
        grafo = grafo.subgraph(componente).copy()
        ruta_xml.unlink(missing_ok=True)
        return grafo

    # ------------------------------------------------------------ carga
    def cargar_grafo(self, id_distrito: str) -> GrafoVial:
        """Carga el grafo almacenado (sin descargar). Se mantiene en memoria."""
        import osmnx as ox

        with self._cerrojo:
            if id_distrito in self._grafos_en_memoria:
                return self._grafos_en_memoria[id_distrito]
        if not self.esta_descargado(id_distrito):
            raise FileNotFoundError(f"La red vial de {id_distrito} no está descargada")
        distrito = self.catalogo.obtener(id_distrito)
        grafo = self._leer_cache_binaria(id_distrito)
        if grafo is None:
            grafo_nx = ox.load_graphml(self.ruta_grafo(id_distrito))
            grafo = GrafoVial.desde_networkx(grafo_nx, distrito.nombre if distrito else id_distrito)
            self._escribir_cache_binaria(id_distrito, grafo)
        with self._cerrojo:
            self._grafos_en_memoria[id_distrito] = grafo
        return grafo

    def _ruta_cache_binaria(self, id_distrito: str) -> Path:
        return self.ajustes.directorio_cache / "grafos_procesados" / f"{id_distrito}.pickle"

    def _leer_cache_binaria(self, id_distrito: str) -> Optional[GrafoVial]:
        """Caché local del grafo ya procesado (generada por esta aplicación, nunca descargada).
        Se invalida si el GraphML es más reciente."""
        import pickle

        ruta = self._ruta_cache_binaria(id_distrito)
        if not ruta.exists() or ruta.stat().st_mtime < self.ruta_grafo(id_distrito).stat().st_mtime:
            return None
        try:
            with open(ruta, "rb") as archivo:
                grafo = pickle.load(archivo)
            return grafo if isinstance(grafo, GrafoVial) else None
        except Exception:  # caché corrupta o de otra versión: se regenera
            return None

    def _escribir_cache_binaria(self, id_distrito: str, grafo: GrafoVial) -> None:
        import pickle
        import sys

        ruta = self._ruta_cache_binaria(id_distrito)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        limite = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(max(limite, 20_000))
            temporal = ruta.with_suffix(".tmp")
            with open(temporal, "wb") as archivo:
                pickle.dump(grafo, archivo, protocol=pickle.HIGHEST_PROTOCOL)
            temporal.replace(ruta)
        except Exception as error:
            logger.warning("No se pudo escribir la caché del grafo %s: %s", id_distrito, error)
        finally:
            sys.setrecursionlimit(limite)

    def cargar_networkx(self, id_distrito: str):
        """Grafo NetworkX original (solo para benchmarks/validación y mapas)."""
        import osmnx as ox

        return ox.load_graphml(self.ruta_grafo(id_distrito))

    def listar_descargados(self) -> list[str]:
        return sorted(p.stem for p in self.ajustes.directorio_grafos.glob("*.graphml"))

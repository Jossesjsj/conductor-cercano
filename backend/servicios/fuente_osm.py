"""Acceso a datos de OpenStreetMap: extracto PBF local y red vial en formato .osm.

Se usa pyosmium para leer el extracto (lectura de datos geográficos); la red vial
resultante se carga con OSMnx (``graph_from_xml``) para obtener un grafo dirigido con
sentidos de circulación y longitudes en metros.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Callable, Optional
from xml.sax.saxutils import quoteattr

import requests

logger = logging.getLogger(__name__)

# Filtro equivalente a network_type="drive" de OSMnx 2.x.
EXCLUSION_HIGHWAY = re.compile(
    r"abandoned|bridleway|bus_guideway|construction|corridor|cycleway|elevator|escalator|footway|no|path|"
    r"pedestrian|planned|platform|proposed|raceway|razed|rest_area|service|services|steps|track"
)
EXCLUSION_SERVICE = re.compile(r"alley|driveway|emergency_access|parking|parking_aisle|private")
ETIQUETAS_CONSERVADAS = ("highway", "oneway", "name", "maxspeed", "lanes", "junction", "ref", "access", "bridge", "tunnel")


def crear_slug(nombre: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")


def es_via_conducible(etiquetas: dict[str, str]) -> bool:
    highway = etiquetas.get("highway")
    if not highway or etiquetas.get("area") == "yes":
        return False
    if EXCLUSION_HIGHWAY.search(highway):
        return False
    if "private" in etiquetas.get("access", ""):
        return False
    if "no" in etiquetas.get("motor_vehicle", "") or "no" in etiquetas.get("motorcar", ""):
        return False
    if EXCLUSION_SERVICE.search(etiquetas.get("service", "")):
        return False
    return True


def descargar_archivo(url: str, destino: Path, agente_usuario: str,
                      progreso: Optional[Callable[[str], None]] = None, tiempo_maximo: int = 600) -> Path:
    """Descarga con escritura atómica (archivo temporal + renombrado)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    with requests.get(url, stream=True, timeout=(15, tiempo_maximo), headers={"User-Agent": agente_usuario}) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        recibido = 0
        with open(temporal, "wb") as archivo:
            for bloque in r.iter_content(chunk_size=1 << 20):
                archivo.write(bloque)
                recibido += len(bloque)
                if progreso and total:
                    progreso(f"Descargando extracto OSM: {recibido / 1e6:.1f} / {total / 1e6:.1f} MB")
    temporal.replace(destino)
    return destino


def extraer_red_vial_a_xml(ruta_pbf: Path, limites: tuple[float, float, float, float], ruta_salida: Path) -> tuple[int, int]:
    """Escribe en ``ruta_salida`` (.osm XML) las vías conducibles que tocan el rectángulo
    (oeste, sur, este, norte). Devuelve (cantidad_nodos, cantidad_vias)."""
    import osmium

    oeste, sur, este, norte = limites
    nodos: dict[int, tuple[float, float]] = {}
    vias: list[tuple[int, list[int], dict[str, str]]] = []

    procesador = osmium.FileProcessor(str(ruta_pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations()
    procesador.with_filter(osmium.filter.EntityFilter(osmium.osm.WAY)).with_filter(osmium.filter.KeyFilter("highway"))
    for via in procesador:
        etiquetas = {e.k: e.v for e in via.tags}
        if not es_via_conducible(etiquetas):
            continue
        referencias: list[tuple[int, float, float]] = []
        toca_area = False
        for n in via.nodes:
            if not n.location.valid():
                continue
            lon, lat = n.location.lon, n.location.lat
            referencias.append((n.ref, lat, lon))
            if not toca_area and oeste <= lon <= este and sur <= lat <= norte:
                toca_area = True
        if not toca_area or len(referencias) < 2:
            continue
        for ref, lat, lon in referencias:
            nodos[ref] = (lat, lon)
        vias.append((via.id, [r[0] for r in referencias],
                     {k: v for k, v in etiquetas.items() if k in ETIQUETAS_CONSERVADAS}))

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as salida:
        salida.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="conductor-cercano">\n')
        for ref, (lat, lon) in nodos.items():
            salida.write(f'<node id="{ref}" lat="{lat:.7f}" lon="{lon:.7f}"/>\n')
        for id_via, refs, etiquetas in vias:
            salida.write(f'<way id="{id_via}">')
            salida.write("".join(f'<nd ref="{r}"/>' for r in refs))
            salida.write("".join(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in etiquetas.items()))
            salida.write("</way>\n")
        salida.write("</osm>\n")
    return len(nodos), len(vias)


def extraer_limites_administrativos(ruta_pbf: Path) -> list[dict]:
    """Polígonos de límites administrativos (niveles 6 y 8) contenidos en el extracto."""
    import osmium
    from shapely import wkb

    fabrica = osmium.geom.WKBFactory()
    resultados: list[dict] = []
    procesador = osmium.FileProcessor(str(ruta_pbf)).with_areas(osmium.filter.TagFilter(("boundary", "administrative")))
    for objeto in procesador:
        if not objeto.is_area() or objeto.from_way():
            continue
        etiquetas = {e.k: e.v for e in objeto.tags}
        if etiquetas.get("admin_level") not in ("6", "8") or "name" not in etiquetas:
            continue
        try:
            geometria = wkb.loads(fabrica.create_multipolygon(objeto), hex=True)
        except Exception as error:  # polígono incompleto en el extracto
            logger.warning("Límite %s incompleto: %s", etiquetas.get("name"), error)
            continue
        resultados.append({
            "osm_id": objeto.orig_id(),
            "nombre": etiquetas["name"],
            "nivel": int(etiquetas["admin_level"]),
            "ubigeo": etiquetas.get("ref:INEI") or etiquetas.get("ref") or "",
            "geometria": geometria,
        })
    return resultados

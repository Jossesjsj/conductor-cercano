"""Catálogo de distritos de Lima Metropolitana y Callao con límites oficiales de OSM."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from backend.configuracion.ajustes import Ajustes
from backend.servicios.fuente_osm import crear_slug, descargar_archivo, extraer_limites_administrativos

logger = logging.getLogger(__name__)

# Distritos oficiales (INEI): 43 de la provincia de Lima y 7 de la Provincia Constitucional del Callao.
DISTRITOS_LIMA_METROPOLITANA = {
    "Ancón", "Ate", "Barranco", "Breña", "Carabayllo", "Chaclacayo", "Chorrillos", "Cieneguilla", "Comas",
    "El Agustino", "Independencia", "Jesús María", "La Molina", "La Victoria", "Lima", "Lince", "Los Olivos",
    "Lurigancho", "Lurín", "Magdalena del Mar", "Miraflores", "Pachacámac", "Pucusana", "Pueblo Libre",
    "Puente Piedra", "Punta Hermosa", "Punta Negra", "Rímac", "San Bartolo", "San Borja", "San Isidro",
    "San Juan de Lurigancho", "San Juan de Miraflores", "San Luis", "San Martín de Porres", "San Miguel",
    "Santa Anita", "Santa María del Mar", "Santa Rosa", "Santiago de Surco", "Surquillo", "Villa El Salvador",
    "Villa María del Triunfo",
}
DISTRITOS_CALLAO = {"Bellavista", "Callao", "Carmen de La Legua-Reynoso", "La Perla", "La Punta", "Mi Perú", "Ventanilla"}
AREA_MINIMA_KM2 = 3.0


@dataclass
class Distrito:
    id_distrito: str
    nombre: str
    provincia: str
    osm_id: int
    area_km2: float
    limites: list[float]  # [oeste, sur, este, norte]
    centro: list[float]  # [longitud, latitud]
    cobertura_completa: bool
    geometria: BaseGeometry

    @property
    def elegible(self) -> bool:
        return self.cobertura_completa and self.area_km2 >= AREA_MINIMA_KM2

    def resumen(self) -> dict[str, Any]:
        return {
            "id_distrito": self.id_distrito,
            "nombre": self.nombre,
            "provincia": self.provincia,
            "osm_id": self.osm_id,
            "area_km2": round(self.area_km2, 2),
            "limites": self.limites,
            "centro": self.centro,
            "cobertura_completa": self.cobertura_completa,
            "elegible": self.elegible,
        }


def calcular_area_km2(geometria: BaseGeometry) -> float:
    """Área en km² proyectando a UTM 18S (EPSG:32718), la zona de Lima."""
    from pyproj import Transformer
    from shapely.ops import transform

    transformador = Transformer.from_crs("EPSG:4326", "EPSG:32718", always_xy=True)
    return transform(transformador.transform, geometria).area / 1e6


class CatalogoDistritos:
    def __init__(self, ajustes: Ajustes) -> None:
        global AREA_MINIMA_KM2
        AREA_MINIMA_KM2 = ajustes.area_minima_distrito_km2
        self.ajustes = ajustes
        self.ruta_catalogo = ajustes.directorio_cache / "distritos_lima_callao.geojson"
        self.ruta_extracto = ajustes.directorio_cache / "lima.osm.pbf"
        self._distritos: dict[str, Distrito] = {}
        self._cerrojo = threading.Lock()

    # ------------------------------------------------------------ carga
    def asegurar_extracto(self, progreso=None) -> Path:
        if not self.ruta_extracto.exists():
            logger.info("Descargando extracto OSM de Lima: %s", self.ajustes.url_extracto_osm)
            descargar_archivo(self.ajustes.url_extracto_osm, self.ruta_extracto, self.ajustes.agente_usuario, progreso)
        return self.ruta_extracto

    def cargar(self, forzar: bool = False) -> dict[str, Distrito]:
        with self._cerrojo:
            if self._distritos and not forzar:
                return self._distritos
            if self.ruta_catalogo.exists() and not forzar:
                self._distritos = self._leer_catalogo()
            else:
                self._distritos = self._construir_catalogo()
            return self._distritos

    def _leer_catalogo(self) -> dict[str, Distrito]:
        datos = json.loads(self.ruta_catalogo.read_text(encoding="utf-8"))
        distritos: dict[str, Distrito] = {}
        for f in datos["features"]:
            p = f["properties"]
            distritos[p["id_distrito"]] = Distrito(
                p["id_distrito"], p["nombre"], p["provincia"], p["osm_id"], p["area_km2"],
                p["limites"], p["centro"], p["cobertura_completa"], shape(f["geometry"]),
            )
        return distritos

    def _construir_catalogo(self) -> dict[str, Distrito]:
        import osmium

        ruta = self.asegurar_extracto()
        lector = osmium.io.Reader(str(ruta), osmium.osm.osm_entity_bits.NOTHING)
        caja = lector.header().box()
        lector.close()
        cobertura = (caja.bottom_left.lon, caja.bottom_left.lat, caja.top_right.lon, caja.top_right.lat)

        limites = extraer_limites_administrativos(ruta)
        distritos: dict[str, Distrito] = {}
        for b in limites:
            if b["nivel"] != 8:
                continue
            if b["nombre"] in DISTRITOS_LIMA_METROPOLITANA:
                provincia = "Lima Metropolitana"
            elif b["nombre"] in DISTRITOS_CALLAO:
                provincia = "Callao"
            else:
                continue
            oeste, sur, este, norte = b["geometria"].bounds
            completa = oeste >= cobertura[0] and sur >= cobertura[1] and este <= cobertura[2] and norte <= cobertura[3]
            slug = crear_slug(b["nombre"])
            if slug in distritos:
                slug = f"{slug}-{crear_slug(provincia)}"
            centro = b["geometria"].centroid
            distritos[slug] = Distrito(
                slug, b["nombre"], provincia, b["osm_id"], calcular_area_km2(b["geometria"]),
                [round(v, 6) for v in (oeste, sur, este, norte)], [round(centro.x, 6), round(centro.y, 6)],
                completa, b["geometria"],
            )
        self._escribir_catalogo(distritos)
        logger.info("Catálogo construido: %d distritos", len(distritos))
        return distritos

    def _escribir_catalogo(self, distritos: dict[str, Distrito]) -> None:
        caracteristicas = []
        for d in sorted(distritos.values(), key=lambda x: (x.provincia, x.nombre)):
            caracteristicas.append({"type": "Feature", "geometry": mapping(d.geometria), "properties": d.resumen()})
        self.ruta_catalogo.parent.mkdir(parents=True, exist_ok=True)
        self.ruta_catalogo.write_text(
            json.dumps({"type": "FeatureCollection", "features": caracteristicas}, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------------------------------------ consulta
    def obtener(self, id_distrito: str) -> Optional[Distrito]:
        return self.cargar().get(id_distrito)

    def listar(self) -> list[Distrito]:
        return sorted(self.cargar().values(), key=lambda d: (d.provincia != "Lima Metropolitana", d.nombre))

    def geojson_distrito(self, id_distrito: str, tolerancia: float = 0.00005) -> Optional[dict[str, Any]]:
        distrito = self.obtener(id_distrito)
        if distrito is None:
            return None
        return {
            "type": "Feature",
            "geometry": mapping(distrito.geometria.simplify(tolerancia, preserve_topology=True)),
            "properties": distrito.resumen(),
        }

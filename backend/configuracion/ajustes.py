"""Configuración central (variables de entorno con prefijo CC_)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CC_", env_file=RAIZ_PROYECTO / ".env", extra="ignore")

    entorno: str = "desarrollo"
    directorio_datos: Path = RAIZ_PROYECTO / "datos"
    url_base_datos: str = ""  # vacío => sqlite en datos/base_datos/conductor_cercano.db
    origenes_cors: str = "http://localhost:5173,http://127.0.0.1:5173"
    directorio_frontend: Path = RAIZ_PROYECTO / "frontend" / "dist"

    # Fuente de datos OSM: "auto" (Overpass y, si falla, extracto), "overpass" o "extracto".
    fuente_osm: str = "auto"
    urls_overpass: str = "https://overpass-api.de/api,https://overpass.private.coffee/api"
    tiempo_maximo_overpass_s: int = 90
    url_extracto_osm: str = "https://download.bbbike.org/osm/bbbike/Lima/Lima.osm.pbf"
    agente_usuario: str = "ConductorCercano/1.0 (proyecto academico de movilidad)"

    # Geocodificación (Nominatim; respeta 1 solicitud/segundo y caché local).
    url_nominatim: str = "https://nominatim.openstreetmap.org"
    intervalo_minimo_nominatim_s: float = 1.1

    area_minima_distrito_km2: float = 3.0
    distrito_por_defecto: str = "miraflores"
    conductores_por_defecto: int = 1500
    precargar_distrito: bool = True
    maximo_conductores_por_mensaje: int = 6000

    @property
    def directorio_grafos(self) -> Path:
        return self.directorio_datos / "grafos"

    @property
    def directorio_cache(self) -> Path:
        return self.directorio_datos / "cache"

    @property
    def url_sqlalchemy(self) -> str:
        if self.url_base_datos:
            return self.url_base_datos
        ruta = self.directorio_datos / "base_datos" / "conductor_cercano.db"
        return f"sqlite:///{ruta.as_posix()}"

    @property
    def lista_origenes_cors(self) -> list[str]:
        return [o.strip() for o in self.origenes_cors.split(",") if o.strip()]

    @property
    def lista_urls_overpass(self) -> list[str]:
        return [u.strip().rstrip("/") for u in self.urls_overpass.split(",") if u.strip()]

    def asegurar_directorios(self) -> None:
        for ruta in (self.directorio_grafos, self.directorio_cache, self.directorio_datos / "base_datos"):
            ruta.mkdir(parents=True, exist_ok=True)


@lru_cache
def obtener_ajustes() -> Ajustes:
    ajustes = Ajustes()
    ajustes.asegurar_directorios()
    return ajustes

"""Geocodificación con Nominatim (OpenStreetMap) respetando su política de uso:
- máximo 1 solicitud por segundo (cerrojo + espera),
- User-Agent identificativo de la aplicación,
- caché local persistente para no repetir consultas,
- resultados restringidos a Perú y priorizando el distrito activo.
Si el servicio no está disponible, el frontend permite seleccionar en el mapa o
introducir coordenadas directamente (alternativa documentada).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Optional

import requests


class ErrorGeocodificacion(RuntimeError):
    pass


class Geocodificador:
    def __init__(self, url_base: str, agente_usuario: str, ruta_cache: Path, intervalo_minimo_s: float = 1.1) -> None:
        self.url_base = url_base.rstrip("/")
        self.agente_usuario = agente_usuario
        self.ruta_cache = ruta_cache
        self.intervalo_minimo_s = intervalo_minimo_s
        self._cerrojo = threading.Lock()
        self._ultima_solicitud = 0.0
        self._cache: dict[str, Any] = {}
        if ruta_cache.exists():
            try:
                self._cache = json.loads(ruta_cache.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _guardar_cache(self) -> None:
        if len(self._cache) > 5000:
            self._cache = dict(list(self._cache.items())[-4000:])
        self.ruta_cache.parent.mkdir(parents=True, exist_ok=True)
        self.ruta_cache.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")

    def _solicitar(self, ruta: str, parametros: dict[str, Any]) -> Any:
        clave = ruta + "?" + "&".join(f"{k}={parametros[k]}" for k in sorted(parametros))
        if clave in self._cache:
            return self._cache[clave]
        with self._cerrojo:
            espera = self.intervalo_minimo_s - (time.monotonic() - self._ultima_solicitud)
            if espera > 0:
                time.sleep(espera)
            try:
                respuesta = requests.get(
                    f"{self.url_base}/{ruta}", params={**parametros, "format": "jsonv2"},
                    headers={"User-Agent": self.agente_usuario, "Accept-Language": "es"}, timeout=10,
                )
            except requests.RequestException as error:
                raise ErrorGeocodificacion(f"No se pudo contactar al servicio de geocodificación: {error}") from error
            finally:
                self._ultima_solicitud = time.monotonic()
            if respuesta.status_code == 429:
                raise ErrorGeocodificacion("Límite de solicitudes de Nominatim alcanzado; intente en unos segundos")
            if respuesta.status_code != 200:
                raise ErrorGeocodificacion(f"Nominatim respondió {respuesta.status_code}")
            datos = respuesta.json()
            self._cache[clave] = datos
            self._guardar_cache()
            return datos

    def buscar(self, texto: str, limites: Optional[list[float]] = None, limite: int = 6) -> list[dict[str, Any]]:
        texto = texto.strip()
        if len(texto) < 3:
            raise ValueError("La búsqueda debe tener al menos 3 caracteres")
        parametros: dict[str, Any] = {"q": texto, "countrycodes": "pe", "limit": limite, "addressdetails": 0}
        if limites:
            oeste, sur, este, norte = limites
            parametros["viewbox"] = f"{oeste:.5f},{norte:.5f},{este:.5f},{sur:.5f}"
            parametros["bounded"] = 0  # prioriza el distrito sin excluir resultados cercanos
        resultados = self._solicitar("search", parametros)
        return [{"nombre": r.get("display_name", ""), "latitud": float(r["lat"]), "longitud": float(r["lon"]),
                 "tipo": r.get("type", ""), "categoria": r.get("category", "")} for r in resultados]

    def inversa(self, latitud: float, longitud: float) -> dict[str, Any]:
        r = self._solicitar("reverse", {"lat": f"{latitud:.6f}", "lon": f"{longitud:.6f}", "zoom": 18})
        if "error" in r:
            return {"nombre": f"{latitud:.6f}, {longitud:.6f}", "latitud": latitud, "longitud": longitud}
        return {"nombre": r.get("display_name", ""), "latitud": latitud, "longitud": longitud}

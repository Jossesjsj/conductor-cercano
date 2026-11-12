"""Primitivas geográficas: rectángulos de límites, cálculo de rumbo e interpolación."""

from __future__ import annotations

import math
from dataclasses import dataclass

from algoritmos.haversine import RADIO_TERRESTRE_METROS


@dataclass(frozen=True, slots=True)
class LimitesGeograficos:
    """Rectángulo alineado con latitud/longitud (grados decimales)."""

    latitud_minima: float
    longitud_minima: float
    latitud_maxima: float
    longitud_maxima: float

    def __post_init__(self) -> None:
        if self.latitud_minima > self.latitud_maxima or self.longitud_minima > self.longitud_maxima:
            raise ValueError(f"Límites inválidos: {self}")

    @property
    def latitud_central(self) -> float:
        return (self.latitud_minima + self.latitud_maxima) / 2.0

    @property
    def longitud_central(self) -> float:
        return (self.longitud_minima + self.longitud_maxima) / 2.0

    def contiene_punto(self, latitud: float, longitud: float) -> bool:
        return (
            self.latitud_minima <= latitud <= self.latitud_maxima
            and self.longitud_minima <= longitud <= self.longitud_maxima
        )

    def intersecta(self, otro: "LimitesGeograficos") -> bool:
        return not (
            otro.latitud_minima > self.latitud_maxima
            or otro.latitud_maxima < self.latitud_minima
            or otro.longitud_minima > self.longitud_maxima
            or otro.longitud_maxima < self.longitud_minima
        )

    def contiene_rectangulo(self, otro: "LimitesGeograficos") -> bool:
        return (
            self.latitud_minima <= otro.latitud_minima
            and self.latitud_maxima >= otro.latitud_maxima
            and self.longitud_minima <= otro.longitud_minima
            and self.longitud_maxima >= otro.longitud_maxima
        )

    def ampliar(self, margen_grados: float) -> "LimitesGeograficos":
        return LimitesGeograficos(
            self.latitud_minima - margen_grados,
            self.longitud_minima - margen_grados,
            self.latitud_maxima + margen_grados,
            self.longitud_maxima + margen_grados,
        )

    def como_lista(self) -> list[float]:
        """Formato [oeste, sur, este, norte] usado por MapLibre/GeoJSON."""
        return [self.longitud_minima, self.latitud_minima, self.longitud_maxima, self.latitud_maxima]


def rectangulo_que_contiene_circulo(latitud: float, longitud: float, radio_metros: float) -> LimitesGeograficos:
    """Rectángulo mínimo que contiene TODOS los puntos a distancia ≤ radio (esfera).

    Δφ = δ  y  Δλ = asin(sin δ / cos φ), con δ = radio / R. Es exacto para la
    esfera, por lo que cualquier punto fuera del rectángulo está a distancia > radio.
    Esa propiedad es la cota inferior que garantiza la exactitud del k-NN.
    """
    if radio_metros < 0:
        raise ValueError("El radio debe ser no negativo")
    delta = radio_metros / RADIO_TERRESTRE_METROS
    delta_latitud = math.degrees(delta)
    latitud_minima = max(-90.0, latitud - delta_latitud)
    latitud_maxima = min(90.0, latitud + delta_latitud)

    coseno = math.cos(math.radians(latitud))
    if delta >= math.pi / 2 or math.sin(delta) >= coseno or latitud_maxima >= 90.0 or latitud_minima <= -90.0:
        return LimitesGeograficos(latitud_minima, -180.0, latitud_maxima, 180.0)
    delta_longitud = math.degrees(math.asin(math.sin(delta) / coseno))
    return LimitesGeograficos(
        latitud_minima,
        max(-180.0, longitud - delta_longitud),
        latitud_maxima,
        min(180.0, longitud + delta_longitud),
    )


def calcular_rumbo(latitud_inicial: float, longitud_inicial: float, latitud_final: float, longitud_final: float) -> float:
    """Rumbo inicial en grados (0 = norte, sentido horario)."""
    phi_1 = math.radians(latitud_inicial)
    phi_2 = math.radians(latitud_final)
    delta_lambda = math.radians(longitud_final - longitud_inicial)
    x = math.sin(delta_lambda) * math.cos(phi_2)
    y = math.cos(phi_1) * math.sin(phi_2) - math.sin(phi_1) * math.cos(phi_2) * math.cos(delta_lambda)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def interpolar_lineal(
    latitud_a: float, longitud_a: float, latitud_b: float, longitud_b: float, fraccion: float
) -> tuple[float, float]:
    """Interpolación lineal (válida para tramos cortos de calle)."""
    fraccion = min(1.0, max(0.0, fraccion))
    return (
        latitud_a + (latitud_b - latitud_a) * fraccion,
        longitud_a + (longitud_b - longitud_a) * fraccion,
    )

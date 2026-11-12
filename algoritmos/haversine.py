"""Fórmula de Haversine implementada desde cero.

Solo se usan funciones trigonométricas elementales del módulo ``math``;
no se recurre a ninguna biblioteca que calcule distancias geográficas.
"""

from __future__ import annotations

import math

# Radio medio terrestre (IUGG, R1 = (2a + b) / 3) en metros.
RADIO_TERRESTRE_METROS: float = 6_371_008.8


def _validar_coordenadas(latitud: float, longitud: float) -> None:
    if not (-90.0 <= latitud <= 90.0):
        raise ValueError(f"Latitud fuera de rango [-90, 90]: {latitud}")
    if not (-180.0 <= longitud <= 180.0):
        raise ValueError(f"Longitud fuera de rango [-180, 180]: {longitud}")


def calcular_haversine(
    latitud_inicial: float,
    longitud_inicial: float,
    latitud_final: float,
    longitud_final: float,
    validar: bool = True,
) -> float:
    """Distancia ortodrómica entre dos puntos en metros.

    d = 2R · asin( sqrt( sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2) ) )
    """
    if validar:
        _validar_coordenadas(latitud_inicial, longitud_inicial)
        _validar_coordenadas(latitud_final, longitud_final)

    phi_1 = math.radians(latitud_inicial)
    phi_2 = math.radians(latitud_final)
    delta_phi = phi_2 - phi_1
    delta_lambda = math.radians(longitud_final - longitud_inicial)

    termino = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Recorte numérico: errores de redondeo pueden dejar termino ligeramente > 1.
    termino = min(1.0, max(0.0, termino))
    return 2.0 * RADIO_TERRESTRE_METROS * math.asin(math.sqrt(termino))


def distancia_haversine_rapida(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Variante sin validación de rango para bucles calientes (misma fórmula)."""
    return calcular_haversine(lat1, lon1, lat2, lon2, validar=False)

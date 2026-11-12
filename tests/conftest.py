"""Utilidades compartidas por las pruebas."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from algoritmos.haversine import distancia_haversine_rapida
from estructuras.grafo_vial import GrafoVial
from simulacion.conductor import Conductor, EstadoConductor, Vehiculo
from simulacion.flota import Flota, ParametrosFlota

LATITUD_BASE, LONGITUD_BASE = -12.12, -77.03
RAIZ = Path(__file__).resolve().parents[1]


def desplazar(x_metros: float, y_metros: float) -> tuple[float, float]:
    """Convierte un desplazamiento local (este, norte) en metros a (lat, lon)."""
    lat = LATITUD_BASE + y_metros / 111_195.0
    lon = LONGITUD_BASE + x_metros / (111_195.0 * math.cos(math.radians(LATITUD_BASE)))
    return lat, lon


def crear_grafo(nodos_m: dict[int, tuple[float, float]], aristas: list[tuple[int, int]]) -> GrafoVial:
    nodos = {n: desplazar(x, y) for n, (x, y) in nodos_m.items()}
    lista = [(u, v, distancia_haversine_rapida(*nodos[u], *nodos[v]), None, f"Calle {u}-{v}") for u, v in aristas]
    return GrafoVial(nodos, lista, "Prueba")


def crear_conductor(grafo: GrafoVial, id_conductor: int, u: int, v: int, desplazamiento_m: float = 0.0,
                    velocidad: float = 30.0, estado: EstadoConductor = EstadoConductor.DISPONIBLE) -> Conductor:
    conductor = Conductor(
        id_conductor=id_conductor, nombre=f"Conductor {id_conductor}",
        vehiculo=Vehiculo(f"TST-{id_conductor:03d}", "Prueba", "X", "Blanco", 2024),
        velocidad=velocidad, nodo_actual=u, ruta_actual=[u, v], distancia_en_arista=desplazamiento_m, estado=estado,
    )
    conductor.sincronizar_posicion(grafo)
    return conductor


def crear_flota_vacia(grafo: GrafoVial) -> Flota:
    return Flota(grafo, ParametrosFlota(cantidad_conductores=0, variacion_velocidad=0.0, proporcion_inactivos=0.0))


def agregar(flota: Flota, conductor: Conductor) -> None:
    flota.conductores[conductor.id_conductor] = conductor
    flota.indice.insertar_conductor(conductor)


@pytest.fixture
def grafo_sentido_unico() -> GrafoVial:
    """El conductor más cercano en línea recta queda en una calle de sentido único que
    se aleja del pasajero (P = nodo 0) y debe dar un rodeo largo.

        3 ──▶ 4
        ▲     │
        │     ▼
        1     5
        ▲     │
    6 ◀─▶ 0 ◀─┘
    """
    nodos = {0: (0, 0), 1: (0, 40), 3: (0, 400), 4: (400, 400), 5: (400, 0), 6: (-300, 0)}
    aristas = [(0, 1), (1, 3), (3, 4), (4, 5), (5, 0), (6, 0), (0, 6)]
    return crear_grafo(nodos, aristas)


def ruta_grafo_miraflores() -> Path:
    return RAIZ / "datos" / "grafos" / "miraflores.graphml"

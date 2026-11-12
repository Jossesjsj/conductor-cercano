"""Pruebas del Quadtree propio."""

from __future__ import annotations

import random

import pytest

from algoritmos.haversine import calcular_haversine
from estructuras.quadtree import Quadtree
from estructuras.utilidades_geograficas import LimitesGeograficos

LIMITES = LimitesGeograficos(-12.20, -77.10, -12.00, -76.90)


class Punto:
    def __init__(self, identificador, latitud, longitud, disponible=True):
        self.id_conductor = identificador
        self.latitud, self.longitud = latitud, longitud
        self.disponible = disponible


def puntos_aleatorios(cantidad: int, semilla: int = 1) -> list[Punto]:
    g = random.Random(semilla)
    return [Punto(i, g.uniform(-12.19, -12.01), g.uniform(-77.09, -76.91), g.random() > 0.3) for i in range(cantidad)]


def test_insercion_en_quadtree_vacio():
    arbol = Quadtree(LIMITES, capacidad=4)
    assert len(arbol) == 0
    arbol.insertar_conductor(Punto(1, -12.1, -77.0))
    assert len(arbol) == 1 and 1 in arbol
    assert arbol.raiz.es_hoja() and arbol.raiz.cantidad == 1
    arbol.validar_consistencia()


def test_insercion_fuera_de_limites_rechazada():
    arbol = Quadtree(LIMITES)
    with pytest.raises(ValueError):
        arbol.insertar(1, -13.0, -77.0)


def test_eliminacion_de_un_conductor():
    arbol = Quadtree(LIMITES, capacidad=4)
    for p in puntos_aleatorios(200):
        arbol.insertar_conductor(p)
    nodos_antes = arbol.contar_nodos()
    assert arbol.eliminar_conductor(17) is True
    assert 17 not in arbol and len(arbol) == 199
    assert arbol.eliminar_conductor(17) is False  # ya no existe
    for i in range(200):
        arbol.eliminar(i)
    assert len(arbol) == 0
    assert arbol.contar_nodos() < nodos_antes  # los hijos vacíos se fusionan
    arbol.validar_consistencia()


def test_busqueda_en_rectangulo_coincide_con_fuerza_bruta():
    puntos = puntos_aleatorios(3000)
    arbol = Quadtree(LIMITES, capacidad=8)
    for p in puntos:
        arbol.insertar_conductor(p)
    g = random.Random(5)
    for _ in range(50):
        la, lb = sorted((g.uniform(-12.2, -12.0), g.uniform(-12.2, -12.0)))
        oa, ob = sorted((g.uniform(-77.1, -76.9), g.uniform(-77.1, -76.9)))
        rect = LimitesGeograficos(la, oa, lb, ob)
        esperado = {p.id_conductor for p in puntos if rect.contiene_punto(p.latitud, p.longitud)}
        obtenido = {e.identificador for e in arbol.buscar_en_rectangulo(rect)}
        assert obtenido == esperado


def test_actualizacion_de_posicion_sin_duplicados():
    arbol = Quadtree(LIMITES, capacidad=4)
    puntos = puntos_aleatorios(500)
    for p in puntos:
        arbol.insertar_conductor(p)
    g = random.Random(9)
    for _ in range(3000):
        p = puntos[g.randrange(len(puntos))]
        p.latitud, p.longitud = g.uniform(-12.19, -12.01), g.uniform(-77.09, -76.91)
        assert arbol.actualizar_posicion(p.id_conductor, p.latitud, p.longitud)
    assert len(arbol) == 500
    arbol.validar_consistencia()  # sin duplicados y cada elemento en la hoja correcta
    for p in puntos:
        entrada = arbol.obtener_entrada(p.id_conductor)
        assert (entrada.latitud, entrada.longitud) == (p.latitud, p.longitud)
    # Reinsertar un id existente no lo duplica: lo reubica.
    arbol.insertar(puntos[0].id_conductor, -12.1, -77.0)
    assert len(arbol) == 500


def test_conductores_en_el_mismo_punto_no_subdividen_infinitamente():
    arbol = Quadtree(LIMITES, capacidad=4, profundidad_maxima=12)
    for i in range(1000):
        arbol.insertar(i, -12.1, -77.0)
    assert len(arbol) == 1000
    assert arbol.obtener_profundidad() == 0  # puntos idénticos: no tiene sentido subdividir
    # Puntos casi idénticos: se detiene en la profundidad máxima.
    arbol2 = Quadtree(LIMITES, capacidad=2, profundidad_maxima=6)
    for i in range(200):
        arbol2.insertar(i, -12.1 + i * 1e-12, -77.0)
    assert arbol2.obtener_profundidad() <= 6
    resultado = arbol.buscar_k_mas_cercanos(-12.1, -77.0, k=5)
    assert len(resultado.candidatos) == 5 and all(d == 0 for d, _ in resultado.candidatos)
    arbol.validar_consistencia()
    arbol2.validar_consistencia()


@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_k_vecinos_exactos_globales(semilla):
    """El resultado coincide con la fuerza bruta (no son 'los primeros k del rectángulo')."""
    puntos = puntos_aleatorios(2500, semilla)
    arbol = Quadtree(LIMITES, capacidad=8)
    for p in puntos:
        arbol.insertar_conductor(p)
    g = random.Random(semilla * 13)
    filtro = lambda e: e.objeto.disponible  # noqa: E731
    for _ in range(40):
        lat, lon = g.uniform(-12.2, -12.0), g.uniform(-77.1, -76.9)
        k = g.choice([1, 5, 12])
        resultado = arbol.buscar_k_mas_cercanos(lat, lon, k=k, radio_inicial_metros=250, filtro=filtro)
        esperado = sorted(calcular_haversine(lat, lon, p.latitud, p.longitud) for p in puntos if p.disponible)[:k]
        obtenido = [d for d, _ in resultado.candidatos]
        assert obtenido == pytest.approx(esperado, abs=1e-9)
        assert all(e.objeto.disponible for _, e in resultado.candidatos)


def test_k_vecinos_con_menos_elementos_que_k():
    arbol = Quadtree(LIMITES)
    arbol.insertar(1, -12.1, -77.0)
    arbol.insertar(2, -12.19, -76.91)
    resultado = arbol.buscar_k_mas_cercanos(-12.0, -77.1, k=5)
    assert [e.identificador for _, e in resultado.candidatos] == [1, 2]
    assert resultado.cobertura_total

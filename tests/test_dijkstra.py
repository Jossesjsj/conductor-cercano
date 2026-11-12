"""Pruebas del Dijkstra propio y validación contra NetworkX (solo como referencia)."""

from __future__ import annotations

import math
import random

import networkx as nx
import pytest

from algoritmos.dijkstra import (
    ErrorNodoInexistente,
    calcular_dijkstra,
    calcular_eta_segundos,
    formatear_eta,
)
from tests.conftest import ruta_grafo_miraflores


def test_dijkstra_con_ruta_valida():
    grafo = {"A": [("B", 4.0), ("C", 1.0)], "B": [("D", 1.0)], "C": [("B", 2.0), ("D", 5.0)], "D": []}
    resultado = calcular_dijkstra(grafo, "A", "D")
    assert resultado.encontrada
    assert resultado.distancia_metros == pytest.approx(4.0)
    assert resultado.nodos == ["A", "C", "B", "D"]


def test_dijkstra_sin_conexion():
    grafo = {1: [(2, 10.0)], 2: [], 3: [(1, 5.0)]}
    resultado = calcular_dijkstra(grafo, 1, 3)
    assert not resultado.encontrada
    assert math.isinf(resultado.distancia_metros) and resultado.nodos == []


def test_dijkstra_respeta_sentido_de_las_aristas():
    grafo = {1: [(2, 100.0)], 2: [(3, 100.0)], 3: [(1, 100.0)]}
    assert calcular_dijkstra(grafo, 1, 3).distancia_metros == 200.0
    assert calcular_dijkstra(grafo, 3, 2).distancia_metros == 200.0  # no puede ir 3→2 directo


def test_dijkstra_destino_inexistente():
    with pytest.raises(ErrorNodoInexistente):
        calcular_dijkstra({1: []}, 1, 99)


def test_dijkstra_origen_igual_destino():
    resultado = calcular_dijkstra({1: [(2, 3.0)], 2: []}, 1, 1)
    assert resultado.encontrada and resultado.distancia_metros == 0 and resultado.nodos == [1]


@pytest.mark.parametrize("semilla", range(5))
def test_comparacion_con_networkx_grafos_aleatorios(semilla):
    g = random.Random(semilla)
    dirigido = nx.gnp_random_graph(120, 0.04, seed=semilla, directed=True)
    adyacencia = {n: [] for n in dirigido.nodes}
    for u, v in dirigido.edges:
        peso = round(g.uniform(1, 500), 3)
        dirigido[u][v]["length"] = peso
        adyacencia[u].append((v, peso))
    for _ in range(40):
        a, b = g.randrange(120), g.randrange(120)
        propio = calcular_dijkstra(adyacencia, a, b)
        try:
            referencia = nx.dijkstra_path_length(dirigido, a, b, weight="length")
        except nx.NetworkXNoPath:
            assert not propio.encontrada
            continue
        assert propio.distancia_metros == pytest.approx(referencia, rel=1e-9)


@pytest.mark.red
@pytest.mark.skipif(not ruta_grafo_miraflores().exists(), reason="Grafo de Miraflores no descargado")
def test_comparacion_con_networkx_red_real_miraflores():
    import osmnx as ox

    from estructuras.grafo_vial import GrafoVial

    grafo_nx = ox.load_graphml(ruta_grafo_miraflores())
    grafo = GrafoVial.desde_networkx(grafo_nx)
    # NetworkX sobre un DiGraph con la arista paralela más corta (igual que GrafoVial).
    simple = nx.DiGraph()
    for u, v, datos in grafo_nx.edges(data=True):
        if u != v and (not simple.has_edge(u, v) or simple[u][v]["length"] > datos["length"]):
            simple.add_edge(u, v, length=datos["length"])
    g = random.Random(11)
    nodos = grafo.lista_nodos_circulables
    for _ in range(60):
        a, b = nodos[g.randrange(len(nodos))], nodos[g.randrange(len(nodos))]
        propio = grafo.calcular_ruta(a, b)
        referencia = nx.dijkstra_path_length(simple, a, b, weight="length")
        assert propio.encontrada
        assert propio.distancia_metros == pytest.approx(referencia, rel=1e-9, abs=1e-6)


def test_conversion_a_eta():
    # 500 m a 30 km/h (8.333 m/s) = 60 s
    assert calcular_eta_segundos(500, 30) == pytest.approx(60.0)
    assert formatear_eta(125) == "2 min 05 s"
    assert math.isinf(calcular_eta_segundos(math.inf, 30))
    with pytest.raises(ValueError):
        calcular_eta_segundos(100, 0)

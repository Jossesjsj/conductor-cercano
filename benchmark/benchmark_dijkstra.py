"""Benchmark 16.2: Dijkstra propio frente a NetworkX (solo como referencia de validación).

Ambos se ejecutan sobre el mismo grafo dirigido (arista paralela más corta) y los mismos
pares de nodos. Se verifica que la distancia mínima coincida dentro de 1e-6 m.
"""

from __future__ import annotations

import random
import statistics
import time
from typing import Any

import networkx as nx

from estructuras.grafo_vial import GrafoVial

TOLERANCIA_M = 1e-6


def digrafo_equivalente(grafo: GrafoVial) -> nx.DiGraph:
    referencia = nx.DiGraph()
    for nodo, vecinos in grafo.adyacencia.items():
        referencia.add_node(nodo)
        for vecino, peso in vecinos:
            referencia.add_edge(nodo, vecino, length=peso)
    return referencia


def ejecutar_distrito(grafo: GrafoVial, nombre: str, pares: int = 100, semilla: int = 7) -> tuple[dict[str, Any], dict[str, list[float]]]:
    referencia = digrafo_equivalente(grafo)
    generador = random.Random(semilla)
    nodos = grafo.lista_nodos_circulables
    tiempos_propio: list[float] = []
    tiempos_nx: list[float] = []
    explorados: list[int] = []
    longitudes: list[int] = []
    diferencias: list[float] = []
    coincidencias = validos = longitud_igual = 0
    for _ in range(pares):
        a, b = nodos[generador.randrange(len(nodos))], nodos[generador.randrange(len(nodos))]
        t = time.perf_counter_ns()
        propio = grafo.calcular_ruta(a, b)
        tiempos_propio.append((time.perf_counter_ns() - t) / 1e6)
        t = time.perf_counter_ns()
        try:
            distancia_nx, ruta_nx = nx.single_source_dijkstra(referencia, a, b, weight="length")
        except nx.NetworkXNoPath:
            distancia_nx, ruta_nx = float("inf"), []
        tiempos_nx.append((time.perf_counter_ns() - t) / 1e6)
        if not propio.encontrada or not ruta_nx:
            coincidencias += (not propio.encontrada) and not ruta_nx
            continue
        validos += 1
        diferencia = abs(propio.distancia_metros - distancia_nx)
        diferencias.append(diferencia)
        coincidencias += diferencia <= TOLERANCIA_M
        longitud_igual += len(propio.nodos) == len(ruta_nx)
        explorados.append(propio.nodos_explorados)
        longitudes.append(len(propio.nodos))
    fila = {
        "distrito": nombre,
        "nodos": grafo.cantidad_nodos,
        "aristas": grafo.cantidad_aristas,
        "pares": pares,
        "pares_validos": validos,
        "coincidencias": coincidencias,
        "rutas_misma_longitud": longitud_igual,
        "diferencia_maxima_m": max(diferencias) if diferencias else 0.0,
        "propio_promedio_ms": statistics.fmean(tiempos_propio),
        "propio_desviacion_ms": statistics.pstdev(tiempos_propio),
        "networkx_promedio_ms": statistics.fmean(tiempos_nx),
        "networkx_desviacion_ms": statistics.pstdev(tiempos_nx),
        "nodos_explorados_promedio": statistics.fmean(explorados) if explorados else 0,
        "fraccion_explorada": (statistics.fmean(explorados) / grafo.cantidad_nodos) if explorados else 0,
        "longitud_ruta_promedio": statistics.fmean(longitudes) if longitudes else 0,
    }
    print(f"  {nombre:28s} propio {fila['propio_promedio_ms']:.2f} ms | networkx {fila['networkx_promedio_ms']:.2f} ms "
          f"| coinciden {coincidencias}/{pares} | dif. máx {fila['diferencia_maxima_m']:.2e} m")
    return fila, {"propio": tiempos_propio, "networkx": tiempos_nx}

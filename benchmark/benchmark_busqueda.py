"""Benchmark 16.1: búsqueda lineal frente a Quadtree (k vecinos disponibles más cercanos).

Ambas estrategias reciben EXACTAMENTE el mismo conjunto de conductores (ubicados sobre
calles reales mediante la Flota) y las mismas consultas (puntos de nodos viales reales).
"""

from __future__ import annotations

import heapq
import random
import statistics
import time
import tracemalloc
from typing import Any

from algoritmos.haversine import distancia_haversine_rapida
from estructuras.grafo_vial import GrafoVial
from estructuras.quadtree import Quadtree
from simulacion.conductor import EstadoConductor
from simulacion.flota import Flota, ParametrosFlota


def busqueda_lineal(conductores: list, latitud: float, longitud: float, k: int) -> tuple[list[int], int]:
    """Recorre todos los conductores: O(n) Haversine + heap de tamaño k."""
    examinados = 0
    candidatos = []
    for c in conductores:
        examinados += 1
        if c.estado is EstadoConductor.DISPONIBLE:
            candidatos.append((distancia_haversine_rapida(latitud, longitud, c.latitud, c.longitud), str(c.id_conductor), c.id_conductor))
    return [i for _, _, i in heapq.nsmallest(k, candidatos)], examinados


def _estadisticos(muestras_ms: list[float]) -> dict[str, float]:
    return {
        "promedio_ms": statistics.fmean(muestras_ms),
        "mediana_ms": statistics.median(muestras_ms),
        "minimo_ms": min(muestras_ms),
        "maximo_ms": max(muestras_ms),
        "desviacion_ms": statistics.pstdev(muestras_ms),
        "p95_ms": sorted(muestras_ms)[int(0.95 * (len(muestras_ms) - 1))],
    }


def medir_memoria_quadtree(flota: Flota, grafo: GrafoVial, capacidad: int) -> float:
    tracemalloc.start()
    antes = tracemalloc.take_snapshot()
    arbol = Quadtree(grafo.limites_ampliados, capacidad=capacidad)
    for c in flota:
        arbol.insertar_conductor(c)
    despues = tracemalloc.take_snapshot()
    tracemalloc.stop()
    total = sum(s.size_diff for s in despues.compare_to(antes, "filename"))
    del arbol
    return total / 1024


def ejecutar(grafo: GrafoVial, nombre_distrito: str, tamanos=(300, 3_000, 30_000), consultas: int = 200,
             repeticiones: int = 5, k: int = 5, semilla: int = 2024, capacidad: int = 16) -> dict[str, Any]:
    generador = random.Random(semilla)
    nodos = grafo.lista_nodos_circulables
    puntos = [grafo.coordenadas(nodos[generador.randrange(len(nodos))]) for _ in range(consultas)]
    filas = []
    muestras_por_tamano: dict[int, dict[str, list[float]]] = {}
    for n in tamanos:
        flota = Flota(grafo, ParametrosFlota(cantidad_conductores=n, semilla=semilla, proporcion_inactivos=0.0, capacidad_quadtree=capacidad))
        flota.generar_flota(random.Random(semilla + n))
        # 30 % ocupados: obliga a filtrar por disponibilidad en ambos métodos.
        g = random.Random(semilla * 3 + n)
        for c in flota:
            if g.random() < 0.3:
                c.estado = EstadoConductor.OCUPADO
        conductores = list(flota)
        arbol = flota.indice
        filtro = lambda e: e.objeto.estado is EstadoConductor.DISPONIBLE  # noqa: E731

        t0 = time.perf_counter()
        reconstruido = Quadtree(grafo.limites_ampliados, capacidad=capacidad)
        for c in conductores:
            reconstruido.insertar_conductor(c)
        construccion_ms = (time.perf_counter() - t0) * 1000

        tiempos_lineal: list[float] = []
        tiempos_qt: list[float] = []
        examinados_lineal: list[int] = []
        examinados_qt: list[int] = []
        coincidencias = 0
        for repeticion in range(repeticiones):
            for lat, lon in puntos:
                t = time.perf_counter_ns()
                ids_lineal, ex_l = busqueda_lineal(conductores, lat, lon, k)
                tiempos_lineal.append((time.perf_counter_ns() - t) / 1e6)
                t = time.perf_counter_ns()
                resultado = arbol.buscar_k_mas_cercanos(lat, lon, k=k, radio_inicial_metros=250, filtro=filtro)
                tiempos_qt.append((time.perf_counter_ns() - t) / 1e6)
                if repeticion == 0:
                    examinados_lineal.append(ex_l)
                    examinados_qt.append(resultado.elementos_examinados)
                    coincidencias += ids_lineal == [e.identificador for _, e in resultado.candidatos]

        # Coste de actualización: desplazamiento real de 1 turno (2 s) sobre la red vial.
        t = time.perf_counter()
        mover = random.Random(semilla + 7)
        for c in conductores:
            c.avanzar_por_ruta(c.velocidad / 3.6 * 2.0, grafo, mover)
            arbol.actualizar_posicion(c.id_conductor, c.latitud, c.longitud)
        actualizacion_us = (time.perf_counter() - t) / len(conductores) * 1e6
        arbol.validar_consistencia()

        lineal = _estadisticos(tiempos_lineal) | {"examinados_promedio": statistics.fmean(examinados_lineal)}
        quadtree = _estadisticos(tiempos_qt) | {"examinados_promedio": statistics.fmean(examinados_qt)}
        filas.append({
            "conductores": n,
            "consultas": consultas,
            "lineal": lineal,
            "quadtree": quadtree,
            "aceleracion": lineal["promedio_ms"] / quadtree["promedio_ms"],
            "coincidencias": coincidencias,
            "construccion_quadtree_ms": construccion_ms,
            "actualizacion_por_conductor_us": actualizacion_us,
            "nodos_quadtree": arbol.contar_nodos(),
            "profundidad_quadtree": arbol.obtener_profundidad(),
            "memoria_quadtree_kb": medir_memoria_quadtree(flota, grafo, capacidad),
        })
        muestras_por_tamano[n] = {"lineal": tiempos_lineal, "quadtree": tiempos_qt}
        print(f"  n={n:>6}: lineal {lineal['promedio_ms']:.3f} ms | quadtree {quadtree['promedio_ms']:.4f} ms "
              f"| x{filas[-1]['aceleracion']:.1f} | exactitud {coincidencias}/{consultas}")
    return {
        "parametros": {"distrito": nombre_distrito, "consultas": consultas, "repeticiones": repeticiones, "k": k,
                       "semilla": semilla, "capacidad_quadtree": capacidad, "proporcion_ocupados": 0.3,
                       "nodos_grafo": grafo.cantidad_nodos},
        "filas": filas,
        "muestras": {str(n): v for n, v in muestras_por_tamano.items()},
    }

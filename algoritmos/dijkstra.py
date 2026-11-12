"""Algoritmo de Dijkstra implementado desde cero sobre un grafo dirigido.

El grafo se recibe como lista de adyacencia ``{nodo: [(vecino, peso_metros), ...]}``.
La cola de prioridad se gestiona con ``heapq`` (permitido por el enunciado).
No se usa ninguna función de caminos mínimos de NetworkX ni de OSMnx.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Hashable, Mapping, Sequence

Nodo = Hashable
ListaAdyacencia = Mapping[Nodo, Sequence[tuple[Nodo, float]]]


@dataclass(slots=True)
class ResultadoRuta:
    """Resultado de una búsqueda de camino mínimo."""

    encontrada: bool
    distancia_metros: float
    nodos: list[Nodo] = field(default_factory=list)
    nodos_explorados: int = 0
    mensaje: str = ""

    @property
    def cantidad_tramos(self) -> int:
        return max(0, len(self.nodos) - 1)


class ErrorNodoInexistente(KeyError):
    """Se lanza cuando el nodo de origen o destino no pertenece al grafo."""


def reconstruir_ruta(predecesores: Mapping[Nodo, Nodo], origen: Nodo, destino: Nodo) -> list[Nodo]:
    """Reconstruye la ruta recorriendo los predecesores desde el destino."""
    ruta: list[Nodo] = [destino]
    actual = destino
    while actual != origen:
        actual = predecesores[actual]
        ruta.append(actual)
    ruta.reverse()
    return ruta


def calcular_dijkstra(
    adyacencia: ListaAdyacencia,
    nodo_inicial: Nodo,
    nodo_final: Nodo,
    distancia_maxima: float = math.inf,
) -> ResultadoRuta:
    """Camino mínimo dirigido entre ``nodo_inicial`` y ``nodo_final``.

    - Respeta el sentido de las aristas (solo recorre ``u -> v`` si existe).
    - Termina en cuanto el destino se extrae de la cola (evita recorridos
      innecesarios); también corta si se supera ``distancia_maxima``.
    - Usa *lazy deletion*: las entradas obsoletas del heap se descartan al salir.
    """
    if nodo_inicial not in adyacencia:
        raise ErrorNodoInexistente(f"El nodo inicial {nodo_inicial!r} no existe en el grafo")
    if nodo_final not in adyacencia:
        raise ErrorNodoInexistente(f"El nodo final {nodo_final!r} no existe en el grafo")

    if nodo_inicial == nodo_final:
        return ResultadoRuta(True, 0.0, [nodo_inicial], 1, "Origen y destino coinciden")

    distancias: dict[Nodo, float] = {nodo_inicial: 0.0}
    predecesores: dict[Nodo, Nodo] = {}
    visitados: set[Nodo] = set()
    # El contador evita comparar nodos cuando dos distancias empatan.
    contador = 0
    cola: list[tuple[float, int, Nodo]] = [(0.0, contador, nodo_inicial)]

    while cola:
        distancia_actual, _, nodo = heapq.heappop(cola)
        if nodo in visitados:
            continue
        visitados.add(nodo)

        if nodo == nodo_final:
            return ResultadoRuta(
                True,
                distancia_actual,
                reconstruir_ruta(predecesores, nodo_inicial, nodo_final),
                len(visitados),
                "Ruta encontrada",
            )
        if distancia_actual > distancia_maxima:
            break

        for vecino, peso in adyacencia.get(nodo, ()):
            if peso < 0:
                raise ValueError("Dijkstra no admite pesos negativos")
            if vecino in visitados:
                continue
            nueva_distancia = distancia_actual + peso
            if nueva_distancia < distancias.get(vecino, math.inf):
                distancias[vecino] = nueva_distancia
                predecesores[vecino] = nodo
                contador += 1
                heapq.heappush(cola, (nueva_distancia, contador, vecino))

    return ResultadoRuta(
        False,
        math.inf,
        [],
        len(visitados),
        "No existe una ruta dirigida entre los nodos indicados",
    )


def convertir_velocidad_a_mps(velocidad_kmh: float) -> float:
    if velocidad_kmh <= 0:
        raise ValueError("La velocidad debe ser positiva")
    return velocidad_kmh * 1000.0 / 3600.0


def calcular_eta_segundos(distancia_metros: float, velocidad_kmh: float) -> float:
    """ETA = distancia_en_metros / velocidad_en_metros_por_segundo."""
    if math.isinf(distancia_metros):
        return math.inf
    return distancia_metros / convertir_velocidad_a_mps(velocidad_kmh)


def formatear_eta(segundos: float) -> str:
    if math.isinf(segundos):
        return "sin ruta"
    minutos, resto = divmod(int(round(segundos)), 60)
    return f"{minutos} min {resto:02d} s"

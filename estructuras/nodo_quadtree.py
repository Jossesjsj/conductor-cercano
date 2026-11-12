"""Nodo del Quadtree propio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Hashable, Iterator, Optional

from estructuras.utilidades_geograficas import LimitesGeograficos

# Índices de los hijos: bit 1 = norte (latitud ≥ media), bit 0 = este (longitud ≥ media).
SUROESTE, SURESTE, NOROESTE, NORESTE = 0, 1, 2, 3


@dataclass(slots=True)
class EntradaEspacial:
    """Elemento almacenado: el árbol guarda su propia copia de las coordenadas
    para que la consistencia no dependa de objetos mutados externamente."""

    identificador: Hashable
    latitud: float
    longitud: float
    objeto: Any = None


class NodoQuadtree:
    """Región rectangular con hasta ``capacidad`` elementos o cuatro hijos."""

    __slots__ = ("limites", "capacidad", "profundidad", "elementos", "hijos", "padre", "cantidad",
                 "latitud_central", "longitud_central")

    def __init__(
        self,
        limites: LimitesGeograficos,
        capacidad: int,
        profundidad: int = 0,
        padre: Optional["NodoQuadtree"] = None,
    ) -> None:
        if capacidad < 1:
            raise ValueError("La capacidad del nodo debe ser al menos 1")
        self.limites = limites
        self.capacidad = capacidad
        self.profundidad = profundidad
        self.elementos: dict[Hashable, EntradaEspacial] = {}
        self.hijos: Optional[list[NodoQuadtree]] = None  # [SO, SE, NO, NE]
        self.padre = padre
        self.cantidad = 0  # elementos en todo el subárbol
        # Centros precalculados: se consultan millones de veces por segundo en la simulación.
        self.latitud_central = limites.latitud_central
        self.longitud_central = limites.longitud_central

    # ------------------------------------------------------------------ consulta
    def es_hoja(self) -> bool:
        return self.hijos is None

    def obtener_indice_hijo(self, latitud: float, longitud: float) -> int:
        return (2 if latitud >= self.latitud_central else 0) | (1 if longitud >= self.longitud_central else 0)

    def esta_sobrecargado(self) -> bool:
        return len(self.elementos) > self.capacidad

    def todos_en_mismo_punto(self) -> bool:
        """True si todos los elementos comparten coordenadas: subdividir no ayudaría."""
        iterador = iter(self.elementos.values())
        primero = next(iterador, None)
        if primero is None:
            return True
        return all(e.latitud == primero.latitud and e.longitud == primero.longitud for e in iterador)

    # ------------------------------------------------------------------ estructura
    def subdividir(self) -> None:
        """Crea los cuatro hijos y redistribuye los elementos del nodo."""
        if self.hijos is not None:
            return
        lim = self.limites
        lat_c, lon_c = self.latitud_central, self.longitud_central
        p = self.profundidad + 1
        self.hijos = [
            NodoQuadtree(LimitesGeograficos(lim.latitud_minima, lim.longitud_minima, lat_c, lon_c), self.capacidad, p, self),
            NodoQuadtree(LimitesGeograficos(lim.latitud_minima, lon_c, lat_c, lim.longitud_maxima), self.capacidad, p, self),
            NodoQuadtree(LimitesGeograficos(lat_c, lim.longitud_minima, lim.latitud_maxima, lon_c), self.capacidad, p, self),
            NodoQuadtree(LimitesGeograficos(lat_c, lon_c, lim.latitud_maxima, lim.longitud_maxima), self.capacidad, p, self),
        ]
        elementos = self.elementos
        self.elementos = {}
        for entrada in elementos.values():
            hijo = self.hijos[self.obtener_indice_hijo(entrada.latitud, entrada.longitud)]
            hijo.elementos[entrada.identificador] = entrada
            hijo.cantidad += 1

    def recolectar_elementos(self) -> Iterator[EntradaEspacial]:
        pila: list[NodoQuadtree] = [self]
        while pila:
            nodo = pila.pop()
            yield from nodo.elementos.values()
            if nodo.hijos is not None:
                pila.extend(nodo.hijos)

    def fusionar_hijos(self) -> list["NodoQuadtree"]:
        """Absorbe los elementos de los descendientes y elimina los hijos.

        Devuelve las hojas absorbidas para que el árbol actualice su índice."""
        if self.hijos is None:
            return []
        absorbidos: dict[Hashable, EntradaEspacial] = {}
        for hijo in self.hijos:
            for entrada in hijo.recolectar_elementos():
                absorbidos[entrada.identificador] = entrada
        self.hijos = None
        self.elementos = absorbidos
        return [self]

    def __repr__(self) -> str:
        tipo = "hoja" if self.es_hoja() else "interno"
        return f"NodoQuadtree({tipo}, prof={self.profundidad}, cantidad={self.cantidad})"

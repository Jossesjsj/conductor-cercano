"""Quadtree propio para indexación espacial de conductores (y de nodos viales).

Garantías:
- Sin duplicados: cada identificador vive en exactamente una hoja.
- Subdivisión al superar la capacidad, salvo profundidad máxima o puntos idénticos.
- Fusión de hijos cuando el subárbol vuelve a caber en un nodo.
- k vecinos más cercanos EXACTOS mediante expansión de radio con cota inferior.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Iterator, Optional

from algoritmos.haversine import distancia_haversine_rapida
from estructuras.nodo_quadtree import EntradaEspacial, NodoQuadtree
from estructuras.utilidades_geograficas import LimitesGeograficos, rectangulo_que_contiene_circulo

FiltroEntrada = Callable[[EntradaEspacial], bool]


@dataclass(slots=True)
class EstadisticasBusqueda:
    nodos_visitados: int = 0
    elementos_examinados: int = 0


@dataclass(slots=True)
class ResultadoVecinos:
    """Resultado de una búsqueda de k vecinos más cercanos."""

    candidatos: list[tuple[float, EntradaEspacial]] = field(default_factory=list)
    radio_final_metros: float = 0.0
    iteraciones: int = 0
    nodos_visitados: int = 0
    elementos_examinados: int = 0
    cobertura_total: bool = False  # True si se exploró todo el árbol


class Quadtree:
    """Índice espacial jerárquico sobre coordenadas geográficas."""

    def __init__(
        self,
        limites: LimitesGeograficos,
        capacidad: int = 16,
        profundidad_maxima: int = 20,
    ) -> None:
        if profundidad_maxima < 1:
            raise ValueError("La profundidad máxima debe ser al menos 1")
        self.limites = limites
        self.capacidad = capacidad
        self.profundidad_maxima = profundidad_maxima
        self.raiz = NodoQuadtree(limites, capacidad, 0, None)
        self._hoja_por_id: dict[Hashable, NodoQuadtree] = {}

    # ================================================================ básicos
    def __len__(self) -> int:
        return len(self._hoja_por_id)

    def __contains__(self, identificador: Hashable) -> bool:
        return identificador in self._hoja_por_id

    def contar_elementos(self) -> int:
        return len(self._hoja_por_id)

    def obtener_entrada(self, identificador: Hashable) -> Optional[EntradaEspacial]:
        hoja = self._hoja_por_id.get(identificador)
        return None if hoja is None else hoja.elementos.get(identificador)

    # ================================================================ inserción
    def insertar(self, identificador: Hashable, latitud: float, longitud: float, objeto: Any = None) -> None:
        """Inserta un elemento. Si el identificador ya existe se reubica (nunca se duplica)."""
        if not self.limites.contiene_punto(latitud, longitud):
            raise ValueError(
                f"Punto ({latitud:.6f}, {longitud:.6f}) fuera de los límites del Quadtree {self.limites}"
            )
        if identificador in self._hoja_por_id:
            self.actualizar_posicion(identificador, latitud, longitud, objeto)
            return
        self._insertar_desde(self.raiz, EntradaEspacial(identificador, latitud, longitud, objeto))

    def insertar_conductor(self, conductor: Any) -> None:
        self.insertar(conductor.id_conductor, conductor.latitud, conductor.longitud, conductor)

    def _insertar_desde(self, nodo: NodoQuadtree, entrada: EntradaEspacial) -> None:
        # Descenso hasta la hoja correspondiente, incrementando contadores.
        while True:
            nodo.cantidad += 1
            if nodo.hijos is None:
                break
            nodo = nodo.hijos[nodo.obtener_indice_hijo(entrada.latitud, entrada.longitud)]
        nodo.elementos[entrada.identificador] = entrada
        self._hoja_por_id[entrada.identificador] = nodo
        self._subdividir_si_corresponde(nodo)

    def _subdividir_si_corresponde(self, hoja: NodoQuadtree) -> None:
        pendientes = [hoja]
        while pendientes:
            nodo = pendientes.pop()
            if (
                not nodo.esta_sobrecargado()
                or nodo.profundidad >= self.profundidad_maxima
                or nodo.todos_en_mismo_punto()
            ):
                continue
            nodo.subdividir()
            assert nodo.hijos is not None
            for hijo in nodo.hijos:
                for identificador in hijo.elementos:
                    self._hoja_por_id[identificador] = hijo
                pendientes.append(hijo)

    # ================================================================ eliminación
    def eliminar(self, identificador: Hashable) -> bool:
        hoja = self._hoja_por_id.pop(identificador, None)
        if hoja is None:
            return False
        del hoja.elementos[identificador]
        nodo: Optional[NodoQuadtree] = hoja
        while nodo is not None:
            nodo.cantidad -= 1
            nodo = nodo.padre
        self._fusionar_ascendentes(hoja.padre)
        return True

    def eliminar_conductor(self, id_conductor: Hashable) -> bool:
        return self.eliminar(id_conductor)

    def _fusionar_ascendentes(self, nodo: Optional[NodoQuadtree]) -> None:
        """Colapsa el ancestro más alto cuyo subárbol cabe en un único nodo."""
        candidato: Optional[NodoQuadtree] = None
        while nodo is not None and nodo.cantidad <= self.capacidad:
            candidato = nodo
            nodo = nodo.padre
        if candidato is not None and candidato.hijos is not None:
            candidato.fusionar_hijos()
            for identificador in candidato.elementos:
                self._hoja_por_id[identificador] = candidato

    # ================================================================ actualización
    def _pertenece_a_hoja(self, hoja: NodoQuadtree, latitud: float, longitud: float) -> bool:
        """O(1): la región de una hoja es semiabierta [mín, máx) en cada eje (regla de
        descenso «≥ centro ⇒ norte/este»), salvo el borde máximo de la raíz, que es cerrado."""
        lim, raiz = hoja.limites, self.limites
        return (
            lim.latitud_minima <= latitud
            and (latitud < lim.latitud_maxima or (latitud == lim.latitud_maxima == raiz.latitud_maxima))
            and lim.longitud_minima <= longitud
            and (longitud < lim.longitud_maxima or (longitud == lim.longitud_maxima == raiz.longitud_maxima))
        )

    def _localizar_hoja(self, latitud: float, longitud: float) -> NodoQuadtree:
        nodo = self.raiz
        while nodo.hijos is not None:
            nodo = nodo.hijos[(2 if latitud >= nodo.latitud_central else 0) | (1 if longitud >= nodo.longitud_central else 0)]
        return nodo

    def actualizar_posicion(
        self, identificador: Hashable, latitud: float, longitud: float, objeto: Any = None
    ) -> bool:
        """Mueve un elemento. Si sigue en la misma hoja solo actualiza coordenadas;
        si cambia de región se elimina de la anterior y se reinserta."""
        hoja_actual = self._hoja_por_id.get(identificador)
        if hoja_actual is None:
            return False
        if not self.limites.contiene_punto(latitud, longitud):
            raise ValueError(f"Nueva posición fuera de los límites: ({latitud}, {longitud})")
        entrada = hoja_actual.elementos[identificador]
        if objeto is not None:
            entrada.objeto = objeto
        if self._pertenece_a_hoja(hoja_actual, latitud, longitud):
            entrada.latitud, entrada.longitud = latitud, longitud
            if len(hoja_actual.elementos) > self.capacidad:
                self._subdividir_si_corresponde(hoja_actual)
            return True
        self.eliminar(identificador)
        entrada.latitud, entrada.longitud = latitud, longitud
        self._insertar_desde(self.raiz, entrada)
        return True

    # ================================================================ búsquedas
    def buscar_en_rectangulo(
        self,
        rectangulo: LimitesGeograficos,
        filtro: Optional[FiltroEntrada] = None,
        estadisticas: Optional[EstadisticasBusqueda] = None,
    ) -> list[EntradaEspacial]:
        """Devuelve los elementos dentro del rectángulo (podando subárboles disjuntos)."""
        encontrados: list[EntradaEspacial] = []
        if not self.raiz.limites.intersecta(rectangulo):
            return encontrados
        pila = [self.raiz]
        lat_min, lat_max = rectangulo.latitud_minima, rectangulo.latitud_maxima
        lon_min, lon_max = rectangulo.longitud_minima, rectangulo.longitud_maxima
        nodos_visitados = examinados = 0
        while pila:
            nodo = pila.pop()
            nodos_visitados += 1
            if nodo.cantidad == 0:
                continue
            if nodo.hijos is not None:
                for hijo in nodo.hijos:
                    if hijo.cantidad and hijo.limites.intersecta(rectangulo):
                        pila.append(hijo)
                continue
            for entrada in nodo.elementos.values():
                examinados += 1
                if lat_min <= entrada.latitud <= lat_max and lon_min <= entrada.longitud <= lon_max:
                    if filtro is None or filtro(entrada):
                        encontrados.append(entrada)
        if estadisticas is not None:
            estadisticas.nodos_visitados += nodos_visitados
            estadisticas.elementos_examinados += examinados
        return encontrados

    def buscar_k_mas_cercanos(
        self,
        latitud: float,
        longitud: float,
        k: int = 5,
        radio_inicial_metros: float = 250.0,
        filtro: Optional[FiltroEntrada] = None,
        factor_expansion: float = 2.0,
    ) -> ResultadoVecinos:
        """k vecinos más cercanos (Haversine) con resultado globalmente exacto.

        En cada iteración se consulta el rectángulo R(r) que contiene al círculo de
        radio r. Todo punto no explorado (fuera de R(r)) está a distancia > r: esa es
        la cota inferior de las regiones no exploradas. Si ya hay k candidatos a
        distancia ≤ r, ningún punto no explorado puede mejorarlos y se termina. En otro
        caso r se multiplica por ``factor_expansion``. Los k mejores se eligen con heapq.
        """
        if k <= 0:
            return ResultadoVecinos()
        if radio_inicial_metros <= 0 or factor_expansion <= 1.0:
            raise ValueError("Radio inicial > 0 y factor de expansión > 1 requeridos")

        resultado = ResultadoVecinos()
        estadisticas = EstadisticasBusqueda()
        radio = radio_inicial_metros
        while True:
            resultado.iteraciones += 1
            rectangulo = rectangulo_que_contiene_circulo(latitud, longitud, radio)
            entradas = self.buscar_en_rectangulo(rectangulo, filtro, estadisticas)
            dentro_del_circulo: list[tuple[float, int, EntradaEspacial]] = []
            todas: list[tuple[float, int, EntradaEspacial]] = []
            for orden, entrada in enumerate(entradas):
                distancia = distancia_haversine_rapida(latitud, longitud, entrada.latitud, entrada.longitud)
                item = (distancia, orden, entrada)
                todas.append(item)
                if distancia <= radio:
                    dentro_del_circulo.append(item)

            cobertura_total = rectangulo.contiene_rectangulo(self.raiz.limites)
            if len(dentro_del_circulo) >= k or cobertura_total:
                fuente = dentro_del_circulo if len(dentro_del_circulo) >= k else todas
                mejores = heapq.nsmallest(k, fuente, key=lambda t: (t[0], str(t[2].identificador)))
                resultado.candidatos = [(d, e) for d, _, e in mejores]
                resultado.radio_final_metros = radio
                resultado.nodos_visitados = estadisticas.nodos_visitados
                resultado.elementos_examinados = estadisticas.elementos_examinados
                resultado.cobertura_total = cobertura_total
                return resultado
            radio *= factor_expansion

    def buscar_mas_cercano(
        self, latitud: float, longitud: float, radio_inicial_metros: float = 50.0
    ) -> Optional[tuple[float, EntradaEspacial]]:
        resultado = self.buscar_k_mas_cercanos(latitud, longitud, 1, radio_inicial_metros)
        return resultado.candidatos[0] if resultado.candidatos else None

    # ================================================================ diagnóstico
    def iterar_entradas(self) -> Iterator[EntradaEspacial]:
        return self.raiz.recolectar_elementos()

    def contar_nodos(self) -> int:
        total, pila = 0, [self.raiz]
        while pila:
            nodo = pila.pop()
            total += 1
            if nodo.hijos is not None:
                pila.extend(nodo.hijos)
        return total

    def obtener_profundidad(self) -> int:
        maxima, pila = 0, [self.raiz]
        while pila:
            nodo = pila.pop()
            maxima = max(maxima, nodo.profundidad)
            if nodo.hijos is not None:
                pila.extend(nodo.hijos)
        return maxima

    def validar_consistencia(self) -> None:
        """Verifica invariantes; lanza AssertionError si alguna falla (útil en pruebas)."""
        vistos: set[Hashable] = set()
        pila = [self.raiz]
        while pila:
            nodo = pila.pop()
            if nodo.hijos is not None:
                assert not nodo.elementos, "Un nodo interno no debe almacenar elementos"
                assert nodo.cantidad == sum(h.cantidad for h in nodo.hijos), "Contador inconsistente"
                for hijo in nodo.hijos:
                    assert hijo.padre is nodo
                    pila.append(hijo)
            else:
                assert nodo.cantidad == len(nodo.elementos), "Contador de hoja inconsistente"
                for identificador, entrada in nodo.elementos.items():
                    assert identificador not in vistos, f"Duplicado: {identificador}"
                    vistos.add(identificador)
                    assert self._hoja_por_id.get(identificador) is nodo, "Índice de hojas desactualizado"
                    assert self._localizar_hoja(entrada.latitud, entrada.longitud) is nodo, "Elemento en hoja incorrecta"
                    assert self._pertenece_a_hoja(nodo, entrada.latitud, entrada.longitud), "Región de hoja inconsistente"
        assert vistos == set(self._hoja_por_id), "Índice con identificadores huérfanos"

"""Representación compacta de la red vial dirigida para simulación y ruteo.

Se construye a partir de un ``networkx.MultiDiGraph`` generado por OSMnx. NetworkX
solo se usa aquí para leer nodos/aristas y obtener la componente fuertemente conexa
(gestión del grafo); el cálculo de rutas lo hace exclusivamente ``algoritmos.dijkstra``.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from algoritmos.dijkstra import ResultadoRuta, calcular_dijkstra
from algoritmos.haversine import distancia_haversine_rapida
from estructuras.quadtree import Quadtree
from estructuras.utilidades_geograficas import LimitesGeograficos, calcular_rumbo

Coordenada = tuple[float, float]  # (latitud, longitud)


@dataclass(slots=True)
class GeometriaArista:
    """Polilínea de una arista dirigida u→v, con distancias acumuladas en metros
    escaladas a la longitud oficial (atributo ``length`` de OSM)."""

    puntos: list[Coordenada]
    acumuladas: list[float]
    longitud: float
    nombre: str
    rumbos: list[float]  # rumbo precalculado de cada segmento (evita trigonometría por turno)

    def interpolar(self, distancia: float) -> tuple[float, float, float]:
        """Devuelve (latitud, longitud, rumbo) a ``distancia`` metros del inicio."""
        if distancia <= 0:
            a = self.puntos[0]
            return a[0], a[1], self.rumbos[0]
        if distancia >= self.longitud:
            b = self.puntos[-1]
            return b[0], b[1], self.rumbos[-1]
        i = bisect.bisect_right(self.acumuladas, distancia) - 1
        i = min(max(i, 0), len(self.puntos) - 2)
        tramo = self.acumuladas[i + 1] - self.acumuladas[i]
        fraccion = 0.0 if tramo <= 0 else (distancia - self.acumuladas[i]) / tramo
        a, b = self.puntos[i], self.puntos[i + 1]
        return a[0] + (b[0] - a[0]) * fraccion, a[1] + (b[1] - a[1]) * fraccion, self.rumbos[i]


class GrafoVial:
    """Grafo dirigido con coordenadas, pesos en metros y geometrías."""

    def __init__(
        self,
        nodos: dict[int, Coordenada],
        aristas: Iterable[tuple[int, int, float, Optional[list[Coordenada]], str]],
        nombre_distrito: str = "",
        distancia_maxima_ajuste_metros: float = 400.0,
        calcular_componente: bool = True,
    ) -> None:
        if not nodos:
            raise ValueError("El grafo vial no tiene nodos")
        self.nombre_distrito = nombre_distrito
        self.nodos = nodos
        self.adyacencia: dict[int, list[tuple[int, float]]] = {n: [] for n in nodos}
        self.predecesores: dict[int, list[int]] = {n: [] for n in nodos}
        self.geometrias: dict[tuple[int, int], GeometriaArista] = {}
        self.distancia_maxima_ajuste_metros = distancia_maxima_ajuste_metros

        for u, v, longitud, puntos, nombre in aristas:
            if u not in nodos or v not in nodos or u == v:
                continue
            longitud = float(longitud) if longitud and longitud > 0 else distancia_haversine_rapida(*nodos[u], *nodos[v])
            existente = self.geometrias.get((u, v))
            if existente is not None and existente.longitud <= longitud:
                continue  # aristas paralelas: se conserva la más corta
            self.geometrias[(u, v)] = self._crear_geometria(nodos[u], nodos[v], longitud, puntos, nombre)

        for (u, v), geometria in self.geometrias.items():
            self.adyacencia[u].append((v, geometria.longitud))
            self.predecesores[v].append(u)

        latitudes = [c[0] for c in nodos.values()]
        longitudes = [c[1] for c in nodos.values()]
        self.limites = LimitesGeograficos(min(latitudes), min(longitudes), max(latitudes), max(longitudes))
        self.limites_ampliados = self.limites.ampliar(0.02)

        self.nodos_circulables: set[int] = (
            self._componente_fuertemente_conexa_mayor() if calcular_componente else set(nodos)
        )
        self.lista_nodos_circulables: list[int] = sorted(self.nodos_circulables)
        self.indice_nodos = Quadtree(self.limites_ampliados, capacidad=24)
        for nodo in self.lista_nodos_circulables:
            lat, lon = nodos[nodo]
            self.indice_nodos.insertar(nodo, lat, lon)

    # ------------------------------------------------------------ construcción
    @staticmethod
    def _crear_geometria(
        origen: Coordenada, destino: Coordenada, longitud: float, puntos: Optional[list[Coordenada]], nombre: str
    ) -> GeometriaArista:
        if not puntos or len(puntos) < 2:
            puntos = [origen, destino]
        acumuladas = [0.0]
        for a, b in zip(puntos, puntos[1:]):
            acumuladas.append(acumuladas[-1] + distancia_haversine_rapida(a[0], a[1], b[0], b[1]))
        total_geometrico = acumuladas[-1]
        if total_geometrico > 0:
            escala = longitud / total_geometrico
            acumuladas = [d * escala for d in acumuladas]
        else:
            acumuladas = [longitud * i / (len(puntos) - 1) for i in range(len(puntos))]
        rumbos = [calcular_rumbo(a[0], a[1], b[0], b[1]) for a, b in zip(puntos, puntos[1:])]
        return GeometriaArista(list(puntos), acumuladas, longitud, nombre, rumbos)

    def _componente_fuertemente_conexa_mayor(self) -> set[int]:
        """Tarjan iterativo propio: componente donde ningún vehículo queda atrapado."""
        indice: dict[int, int] = {}
        bajo: dict[int, int] = {}
        en_pila: set[int] = set()
        pila: list[int] = []
        mejor: set[int] = set()
        contador = 0
        for raiz in self.nodos:
            if raiz in indice:
                continue
            trabajo: list[tuple[int, int]] = [(raiz, 0)]
            while trabajo:
                nodo, posicion = trabajo.pop()
                if posicion == 0:
                    indice[nodo] = bajo[nodo] = contador
                    contador += 1
                    pila.append(nodo)
                    en_pila.add(nodo)
                vecinos = self.adyacencia[nodo]
                recursion = False
                while posicion < len(vecinos):
                    vecino = vecinos[posicion][0]
                    posicion += 1
                    if vecino not in indice:
                        trabajo.append((nodo, posicion))
                        trabajo.append((vecino, 0))
                        recursion = True
                        break
                    if vecino in en_pila:
                        bajo[nodo] = min(bajo[nodo], indice[vecino])
                if recursion:
                    continue
                if bajo[nodo] == indice[nodo]:
                    componente: set[int] = set()
                    while True:
                        w = pila.pop()
                        en_pila.discard(w)
                        componente.add(w)
                        if w == nodo:
                            break
                    if len(componente) > len(mejor):
                        mejor = componente
                if trabajo:
                    padre = trabajo[-1][0]
                    bajo[padre] = min(bajo[padre], bajo[nodo])
        return mejor

    @classmethod
    def desde_networkx(cls, grafo: Any, nombre_distrito: str = "", **opciones: Any) -> "GrafoVial":
        nodos = {int(n): (float(d["y"]), float(d["x"])) for n, d in grafo.nodes(data=True)}
        aristas = []
        for u, v, datos in grafo.edges(data=True):
            geometria = datos.get("geometry")
            puntos = [(float(y), float(x)) for x, y in geometria.coords] if geometria is not None else None
            nombre = datos.get("name", "")
            if isinstance(nombre, list):
                nombre = " / ".join(str(n) for n in nombre)
            aristas.append((int(u), int(v), float(datos.get("length", 0.0)), puntos, str(nombre or "")))
        return cls(nodos, aristas, nombre_distrito, **opciones)

    # ------------------------------------------------------------ consultas
    @property
    def cantidad_nodos(self) -> int:
        return len(self.nodos)

    @property
    def cantidad_aristas(self) -> int:
        return len(self.geometrias)

    def coordenadas(self, nodo: int) -> Coordenada:
        return self.nodos[nodo]

    def obtener_sucesores(self, nodo: int) -> list[tuple[int, float]]:
        return self.adyacencia.get(nodo, [])

    def obtener_geometria(self, u: int, v: int) -> GeometriaArista:
        return self.geometrias[(u, v)]

    def localizar_nodo_cercano(
        self, latitud: float, longitud: float, distancia_maxima_metros: Optional[float] = None
    ) -> Optional[tuple[int, float]]:
        """Nodo circulable más cercano usando el Quadtree propio (sin índices de OSMnx).

        Devuelve ``None`` si no hay red vial a menos de ``distancia_maxima_metros``."""
        maximo = self.distancia_maxima_ajuste_metros if distancia_maxima_metros is None else distancia_maxima_metros
        if not self.limites_ampliados.contiene_punto(latitud, longitud):
            return None
        cercano = self.indice_nodos.buscar_mas_cercano(latitud, longitud, radio_inicial_metros=40.0)
        if cercano is None or cercano[0] > maximo:
            return None
        distancia, entrada = cercano
        return int(entrada.identificador), distancia

    def calcular_ruta(self, origen: int, destino: int) -> ResultadoRuta:
        return calcular_dijkstra(self.adyacencia, origen, destino)

    def coordenadas_de_ruta(self, nodos: list[int]) -> list[Coordenada]:
        """Polilínea detallada de una ruta (incluye la curvatura de cada calle)."""
        if not nodos:
            return []
        if len(nodos) == 1:
            return [self.nodos[nodos[0]]]
        puntos: list[Coordenada] = [self.nodos[nodos[0]]]
        for u, v in zip(nodos, nodos[1:]):
            geometria = self.geometrias.get((u, v))
            puntos.extend(geometria.puntos[1:] if geometria else [self.nodos[v]])
        return puntos

    def nombres_de_ruta(self, nodos: list[int], maximo: int = 6) -> list[str]:
        nombres: list[str] = []
        for u, v in zip(nodos, nodos[1:]):
            nombre = self.geometrias[(u, v)].nombre if (u, v) in self.geometrias else ""
            if nombre and (not nombres or nombres[-1] != nombre):
                nombres.append(nombre)
        return nombres[:maximo]

    def a_geojson(self, incluir_nodos: bool = True) -> dict[str, Any]:
        """Calles e intersecciones del grafo (para superponer en el mapa)."""
        caracteristicas: list[dict[str, Any]] = []
        vistas: set[tuple[int, int]] = set()
        for (u, v), geometria in self.geometrias.items():
            clave = (min(u, v), max(u, v))
            doble = (v, u) in self.geometrias
            if doble and clave in vistas:
                continue
            vistas.add(clave)
            caracteristicas.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[round(p[1], 6), round(p[0], 6)] for p in geometria.puntos]},
                "properties": {"nombre": geometria.nombre, "sentido_unico": not doble, "longitud": round(geometria.longitud, 1)},
            })
        if incluir_nodos:
            for nodo in self.lista_nodos_circulables:
                grado = len(self.adyacencia[nodo]) + len(self.predecesores[nodo])
                if grado >= 3:  # intersecciones reales
                    lat, lon = self.nodos[nodo]
                    caracteristicas.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                        "properties": {"nodo": nodo, "tipo": "interseccion"},
                    })
        return {"type": "FeatureCollection", "features": caracteristicas}


def crear_grafo_cuadricula(
    filas: int,
    columnas: int,
    latitud_origen: float = -12.12,
    longitud_origen: float = -77.03,
    separacion_metros: float = 100.0,
    bidireccional: bool = True,
) -> GrafoVial:
    """Grafo sintético en cuadrícula (pruebas y demostraciones sin red)."""
    paso_lat = separacion_metros / 111_195.0
    paso_lon = separacion_metros / (111_195.0 * math.cos(math.radians(latitud_origen)))
    nodos: dict[int, Coordenada] = {}
    for f in range(filas):
        for c in range(columnas):
            nodos[f * columnas + c] = (latitud_origen + f * paso_lat, longitud_origen + c * paso_lon)
    aristas = []
    for f in range(filas):
        for c in range(columnas):
            n = f * columnas + c
            vecinos = []
            if c + 1 < columnas:
                vecinos.append(n + 1)
            if f + 1 < filas:
                vecinos.append(n + columnas)
            for m in vecinos:
                d = distancia_haversine_rapida(*nodos[n], *nodos[m])
                aristas.append((n, m, d, None, f"Calle {f}-{c}"))
                if bidireccional:
                    aristas.append((m, n, d, None, f"Calle {f}-{c}"))
    return GrafoVial(nodos, aristas, "Cuadrícula de prueba")

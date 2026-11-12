"""Clase Conductor: vehículo que circula exclusivamente por aristas de la red vial."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from estructuras.grafo_vial import GrafoVial


class EstadoConductor(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    OCUPADO = "OCUPADO"  # asignado, se dirige a recoger al pasajero
    EN_SERVICIO = "EN_SERVICIO"  # transporta al pasajero hacia su destino
    INACTIVO = "INACTIVO"


CODIGO_ESTADO = {
    EstadoConductor.DISPONIBLE: 0,
    EstadoConductor.OCUPADO: 1,
    EstadoConductor.EN_SERVICIO: 2,
    EstadoConductor.INACTIVO: 3,
}

TRANSICIONES_VALIDAS: dict[EstadoConductor, set[EstadoConductor]] = {
    EstadoConductor.DISPONIBLE: {EstadoConductor.OCUPADO, EstadoConductor.INACTIVO},
    EstadoConductor.OCUPADO: {EstadoConductor.EN_SERVICIO, EstadoConductor.DISPONIBLE},
    EstadoConductor.EN_SERVICIO: {EstadoConductor.DISPONIBLE},
    EstadoConductor.INACTIVO: {EstadoConductor.DISPONIBLE},
}


class ErrorTransicionEstado(RuntimeError):
    pass


@dataclass(slots=True)
class Vehiculo:
    placa: str
    marca: str
    modelo: str
    color: str
    anio: int
    capacidad_pasajeros: int = 4


@dataclass(slots=True)
class EventoMovimiento:
    """Resultado de avanzar un turno."""

    llego_al_final_de_ruta: bool = False
    aristas_recorridas: int = 0


@dataclass
class Conductor:
    id_conductor: int
    nombre: str
    vehiculo: Vehiculo
    velocidad: float  # km/h
    nodo_actual: int  # último nodo por el que pasó (origen de la arista actual)
    latitud: float = 0.0
    longitud: float = 0.0
    rumbo: float = 0.0
    estado: EstadoConductor = EstadoConductor.DISPONIBLE
    ruta_actual: list[int] = field(default_factory=list)
    indice_ruta: int = 0  # índice de la arista ruta_actual[i] -> ruta_actual[i+1]
    distancia_en_arista: float = 0.0
    distancia_recorrida: float = 0.0
    en_ruta_de_servicio: bool = False
    id_pasajero_asignado: Optional[int] = None
    servicios_completados: int = 0

    # ------------------------------------------------------------ propiedades
    @property
    def id_vehiculo(self) -> str:
        return self.vehiculo.placa

    @property
    def identificador(self) -> int:
        return self.id_conductor

    @property
    def nodo_siguiente(self) -> int:
        return self.ruta_actual[self.indice_ruta + 1]

    def esta_disponible(self) -> bool:
        return self.estado is EstadoConductor.DISPONIBLE

    # ------------------------------------------------------------ estado
    def cambiar_estado(self, nuevo_estado: EstadoConductor) -> None:
        if nuevo_estado == self.estado:
            return
        if nuevo_estado not in TRANSICIONES_VALIDAS[self.estado]:
            raise ErrorTransicionEstado(f"Transición inválida {self.estado.value} -> {nuevo_estado.value}")
        self.estado = nuevo_estado

    def actualizar_posicion(self, latitud: float, longitud: float, rumbo: Optional[float] = None) -> None:
        self.latitud, self.longitud = latitud, longitud
        if rumbo is not None:
            self.rumbo = rumbo

    def sincronizar_posicion(self, grafo: GrafoVial) -> None:
        """Calcula lat/lon interpolando sobre la geometría de la arista actual."""
        u, v = self.ruta_actual[self.indice_ruta], self.ruta_actual[self.indice_ruta + 1]
        lat, lon, rumbo = grafo.obtener_geometria(u, v).interpolar(self.distancia_en_arista)
        self.actualizar_posicion(lat, lon, rumbo)

    # ------------------------------------------------------------ servicio
    def asignar_ruta_recogida(self, nodos_desde_siguiente: list[int], id_pasajero: int) -> None:
        """Pasa a OCUPADO y sigue la ruta: arista actual + ruta Dijkstra desde nodo_siguiente."""
        self.cambiar_estado(EstadoConductor.OCUPADO)
        self.id_pasajero_asignado = id_pasajero
        self._reemplazar_ruta_conservando_arista(nodos_desde_siguiente)

    def iniciar_servicio(self, ruta_viaje: list[int]) -> None:
        """Pasajero recogido: pasa a EN_SERVICIO y sigue la ruta del viaje.

        ``ruta_viaje`` comienza en el nodo de recogida, que es ``nodo_siguiente``."""
        self.cambiar_estado(EstadoConductor.EN_SERVICIO)
        self._reemplazar_ruta_conservando_arista(ruta_viaje)

    def finalizar_servicio(self) -> None:
        self.cambiar_estado(EstadoConductor.DISPONIBLE)
        self.id_pasajero_asignado = None
        self.en_ruta_de_servicio = False
        self.servicios_completados += 1

    def cancelar_asignacion(self) -> None:
        if self.estado is EstadoConductor.OCUPADO:
            self.cambiar_estado(EstadoConductor.DISPONIBLE)
        self.id_pasajero_asignado = None
        self.en_ruta_de_servicio = False
        u, v = self.ruta_actual[self.indice_ruta], self.ruta_actual[self.indice_ruta + 1]
        self.ruta_actual, self.indice_ruta = [u, v], 0

    def _reemplazar_ruta_conservando_arista(self, continuacion: list[int]) -> None:
        """Mantiene la arista en curso u→v (sin teletransporte) y anexa la
        continuación calculada por Dijkstra, que debe comenzar en v."""
        u, v = self.ruta_actual[self.indice_ruta], self.ruta_actual[self.indice_ruta + 1]
        if not continuacion or continuacion[0] != v:
            raise ValueError("La continuación de ruta debe comenzar en el nodo siguiente del conductor")
        self.ruta_actual = [u] + list(continuacion)
        self.indice_ruta = 0
        self.nodo_actual = u
        self.en_ruta_de_servicio = True

    # ------------------------------------------------------------ movimiento
    def elegir_siguiente_arista(self, grafo: GrafoVial, generador: random.Random) -> int:
        """Elige una arista saliente válida del grafo dirigido evitando el giro en U.

        Solo si el nodo es un callejón sin salida (única salida = volver) se permite
        regresar, que es la maniobra real en una calle ciega."""
        nodo = self.ruta_actual[self.indice_ruta + 1] if self.indice_ruta + 1 < len(self.ruta_actual) else self.nodo_actual
        anterior = self.ruta_actual[self.indice_ruta] if self.indice_ruta + 1 < len(self.ruta_actual) else None
        salidas = [v for v, _ in grafo.obtener_sucesores(nodo) if v in grafo.nodos_circulables]
        if not salidas:
            salidas = [v for v, _ in grafo.obtener_sucesores(nodo)]
        if not salidas:
            raise RuntimeError(f"Nodo {nodo} sin aristas salientes")
        sin_giro_u = [v for v in salidas if v != anterior]
        opciones = sin_giro_u or salidas
        return opciones[generador.randrange(len(opciones))]

    def avanzar_por_ruta(self, metros: float, grafo: GrafoVial, generador: random.Random) -> EventoMovimiento:
        """Avanza ``metros`` siguiendo las aristas. En la ruta de servicio se detiene
        al llegar al final; en circulación libre encadena aristas aleatorias válidas."""
        evento = EventoMovimiento()
        if self.estado is EstadoConductor.INACTIVO or metros <= 0:
            return evento
        restante = metros
        while restante > 0:
            u, v = self.ruta_actual[self.indice_ruta], self.ruta_actual[self.indice_ruta + 1]
            longitud = grafo.obtener_geometria(u, v).longitud
            hasta_fin = longitud - self.distancia_en_arista
            if restante < hasta_fin:
                self.distancia_en_arista += restante
                self.distancia_recorrida += restante
                restante = 0
                break
            restante -= hasta_fin
            self.distancia_recorrida += hasta_fin
            self.distancia_en_arista = 0.0
            evento.aristas_recorridas += 1
            if self.indice_ruta + 2 < len(self.ruta_actual):
                self.indice_ruta += 1
                self.nodo_actual = self.ruta_actual[self.indice_ruta]
                continue
            # Fin de la ruta actual.
            if self.en_ruta_de_servicio:
                # Se detiene exactamente en el nodo final: arista sintética terminada.
                self.distancia_en_arista = longitud
                self.nodo_actual = v
                evento.llego_al_final_de_ruta = True
                break
            siguiente = self.elegir_siguiente_arista(grafo, generador)
            self.ruta_actual, self.indice_ruta, self.nodo_actual = [v, siguiente], 0, v
        self.sincronizar_posicion(grafo)
        return evento

    def distancia_restante_en_arista(self, grafo: GrafoVial) -> float:
        u, v = self.ruta_actual[self.indice_ruta], self.ruta_actual[self.indice_ruta + 1]
        return max(0.0, grafo.obtener_geometria(u, v).longitud - self.distancia_en_arista)

    def distancia_restante_ruta(self, grafo: GrafoVial) -> float:
        """Metros que faltan para el final de la ruta actual (resto de arista + aristas siguientes)."""
        restante = self.distancia_restante_en_arista(grafo)
        for u, v in zip(self.ruta_actual[self.indice_ruta + 1:], self.ruta_actual[self.indice_ruta + 2:]):
            restante += grafo.obtener_geometria(u, v).longitud
        return restante

    def reanudar_circulacion_libre(self, grafo: GrafoVial, generador: random.Random) -> None:
        """Tras dejar al pasajero, toma una salida válida desde el nodo actual."""
        siguiente = self.elegir_siguiente_arista(grafo, generador)
        u = self.ruta_actual[self.indice_ruta + 1]
        self.ruta_actual, self.indice_ruta, self.nodo_actual = [u, siguiente], 0, u
        self.distancia_en_arista = 0.0
        self.en_ruta_de_servicio = False

    # ------------------------------------------------------------ información
    def obtener_informacion(self) -> dict[str, Any]:
        return {
            "id_conductor": self.id_conductor,
            "nombre": self.nombre,
            "latitud": round(self.latitud, 7),
            "longitud": round(self.longitud, 7),
            "rumbo": round(self.rumbo, 1),
            "nodo_actual": self.nodo_actual,
            "nodo_siguiente": self.nodo_siguiente,
            "estado": self.estado.value,
            "velocidad_kmh": round(self.velocidad, 1),
            "distancia_recorrida_m": round(self.distancia_recorrida, 1),
            "indice_ruta": self.indice_ruta,
            "longitud_ruta_nodos": len(self.ruta_actual),
            "id_pasajero_asignado": self.id_pasajero_asignado,
            "servicios_completados": self.servicios_completados,
            "id_vehiculo": self.id_vehiculo,
            "vehiculo": {
                "placa": self.vehiculo.placa,
                "marca": self.vehiculo.marca,
                "modelo": self.vehiculo.modelo,
                "color": self.vehiculo.color,
                "anio": self.vehiculo.anio,
                "capacidad_pasajeros": self.vehiculo.capacidad_pasajeros,
            },
        }

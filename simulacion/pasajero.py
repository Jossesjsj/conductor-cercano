"""Clase Pasajero: solicitud de transporte con origen y destino sobre la red vial."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EstadoPasajero(str, Enum):
    ESPERANDO = "ESPERANDO"
    CONDUCTOR_ASIGNADO = "CONDUCTOR_ASIGNADO"
    RECOGIDO = "RECOGIDO"
    VIAJANDO = "VIAJANDO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


ESTADOS_ACTIVOS = {
    EstadoPasajero.ESPERANDO,
    EstadoPasajero.CONDUCTOR_ASIGNADO,
    EstadoPasajero.RECOGIDO,
    EstadoPasajero.VIAJANDO,
}

TRANSICIONES_PASAJERO: dict[EstadoPasajero, set[EstadoPasajero]] = {
    EstadoPasajero.ESPERANDO: {EstadoPasajero.CONDUCTOR_ASIGNADO, EstadoPasajero.CANCELADO},
    EstadoPasajero.CONDUCTOR_ASIGNADO: {EstadoPasajero.RECOGIDO, EstadoPasajero.CANCELADO},
    EstadoPasajero.RECOGIDO: {EstadoPasajero.VIAJANDO},
    EstadoPasajero.VIAJANDO: {EstadoPasajero.FINALIZADO},
    EstadoPasajero.FINALIZADO: set(),
    EstadoPasajero.CANCELADO: set(),
}


@dataclass
class Pasajero:
    id_pasajero: int
    latitud_origen: float
    longitud_origen: float
    latitud_destino: float
    longitud_destino: float
    nodo_origen: Optional[int] = None
    nodo_destino: Optional[int] = None
    estado: EstadoPasajero = EstadoPasajero.ESPERANDO
    fecha_solicitud: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    direccion_origen: str = ""
    direccion_destino: str = ""
    id_conductor_asignado: Optional[int] = None
    motivo_cancelacion: str = ""
    turno_solicitud: int = 0
    # Hitos del viaje en tiempo simulado (segundos) y distancias planificadas (m).
    tiempo_asignacion_s: Optional[float] = None
    tiempo_recogida_s: Optional[float] = None
    tiempo_llegada_s: Optional[float] = None
    distancia_recogida_m: Optional[float] = None
    distancia_viaje_m: Optional[float] = None
    eta_recogida_s: Optional[float] = None

    @property
    def espera_real_s(self) -> Optional[float]:
        if self.tiempo_recogida_s is None or self.tiempo_asignacion_s is None:
            return None
        return self.tiempo_recogida_s - self.tiempo_asignacion_s

    @property
    def duracion_viaje_s(self) -> Optional[float]:
        if self.tiempo_llegada_s is None or self.tiempo_recogida_s is None:
            return None
        return self.tiempo_llegada_s - self.tiempo_recogida_s

    @property
    def ubicacion_origen(self) -> tuple[float, float]:
        return self.latitud_origen, self.longitud_origen

    @property
    def ubicacion_destino(self) -> tuple[float, float]:
        return self.latitud_destino, self.longitud_destino

    def esta_activo(self) -> bool:
        return self.estado in ESTADOS_ACTIVOS

    def cambiar_estado(self, nuevo_estado: EstadoPasajero) -> None:
        if nuevo_estado == self.estado:
            return
        if nuevo_estado not in TRANSICIONES_PASAJERO[self.estado]:
            raise ValueError(f"Transición de pasajero inválida {self.estado.value} -> {nuevo_estado.value}")
        self.estado = nuevo_estado

    def asignar_conductor(self, id_conductor: int) -> None:
        self.cambiar_estado(EstadoPasajero.CONDUCTOR_ASIGNADO)
        self.id_conductor_asignado = id_conductor

    def cancelar(self, motivo: str) -> None:
        self.cambiar_estado(EstadoPasajero.CANCELADO)
        self.motivo_cancelacion = motivo

    def obtener_informacion(self) -> dict[str, Any]:
        return {
            "id_pasajero": self.id_pasajero,
            "origen": {"latitud": self.latitud_origen, "longitud": self.longitud_origen, "direccion": self.direccion_origen},
            "destino": {"latitud": self.latitud_destino, "longitud": self.longitud_destino, "direccion": self.direccion_destino},
            "nodo_origen": self.nodo_origen,
            "nodo_destino": self.nodo_destino,
            "estado": self.estado.value,
            "fecha_solicitud": self.fecha_solicitud.isoformat(),
            "id_conductor_asignado": self.id_conductor_asignado,
            "motivo_cancelacion": self.motivo_cancelacion,
        }

"""Modelos SQLAlchemy (SQLite). Las posiciones por turno NO se persisten (solo eventos)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ConfiguracionGuardada(Base):
    __tablename__ = "configuraciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, index=True)
    id_distrito: Mapped[str] = mapped_column(String(80), index=True)
    semilla: Mapped[int] = mapped_column(Integer)
    cantidad_conductores: Mapped[int] = mapped_column(Integer)
    datos: Mapped[dict[str, Any]] = mapped_column(JSON)
    metadatos_grafo: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class ConductorRegistrado(Base):
    """Instantánea de la flota generada para una configuración (reproducible por semilla)."""

    __tablename__ = "conductores"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_configuracion: Mapped[int] = mapped_column(ForeignKey("configuraciones.id", ondelete="CASCADE"), index=True)
    id_conductor: Mapped[int] = mapped_column(Integer)
    nombre: Mapped[str] = mapped_column(String(80))
    placa: Mapped[str] = mapped_column(String(12))
    marca: Mapped[str] = mapped_column(String(30))
    modelo: Mapped[str] = mapped_column(String(30))
    color: Mapped[str] = mapped_column(String(20))
    anio: Mapped[int] = mapped_column(Integer)
    velocidad_kmh: Mapped[float] = mapped_column(Float)
    nodo_inicial: Mapped[int] = mapped_column(Integer)
    latitud_inicial: Mapped[float] = mapped_column(Float)
    longitud_inicial: Mapped[float] = mapped_column(Float)
    estado_inicial: Mapped[str] = mapped_column(String(20))


class Solicitud(Base):
    """Pasajero y su solicitud de transporte."""

    __tablename__ = "solicitudes"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_configuracion: Mapped[Optional[int]] = mapped_column(ForeignKey("configuraciones.id", ondelete="SET NULL"), index=True)
    id_pasajero: Mapped[int] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, index=True)
    id_distrito: Mapped[str] = mapped_column(String(80), index=True)
    origen: Mapped[str] = mapped_column(String(20), default="manual")  # manual | automatica | script
    latitud_origen: Mapped[float] = mapped_column(Float)
    longitud_origen: Mapped[float] = mapped_column(Float)
    latitud_destino: Mapped[float] = mapped_column(Float)
    longitud_destino: Mapped[float] = mapped_column(Float)
    direccion_origen: Mapped[str] = mapped_column(String(300), default="")
    direccion_destino: Mapped[str] = mapped_column(String(300), default="")
    nodo_origen: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nodo_destino: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String(24), index=True)
    codigo_resultado: Mapped[str] = mapped_column(String(40))
    mensaje: Mapped[str] = mapped_column(Text, default="")

    asignacion: Mapped[Optional["Asignacion"]] = relationship(back_populates="solicitud", uselist=False)


class Asignacion(Base):
    __tablename__ = "asignaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_solicitud: Mapped[int] = mapped_column(ForeignKey("solicitudes.id", ondelete="CASCADE"), unique=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, index=True)
    id_distrito: Mapped[str] = mapped_column(String(80), index=True)
    id_conductor: Mapped[int] = mapped_column(Integer, index=True)
    nombre_conductor: Mapped[str] = mapped_column(String(80))
    placa: Mapped[str] = mapped_column(String(12))
    velocidad_kmh: Mapped[float] = mapped_column(Float)
    candidatos: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    distancia_haversine_m: Mapped[float] = mapped_column(Float)
    distancia_ruta_m: Mapped[float] = mapped_column(Float)
    eta_segundos: Mapped[float] = mapped_column(Float)
    distancia_viaje_m: Mapped[float] = mapped_column(Float)
    duracion_viaje_s: Mapped[float] = mapped_column(Float)
    ruta_recogida: Mapped[list[list[float]]] = mapped_column(JSON)  # [[lon, lat], ...]
    ruta_viaje: Mapped[list[list[float]]] = mapped_column(JSON)
    calles_recogida: Mapped[list[str]] = mapped_column(JSON, default=list)
    conductores_contexto: Mapped[list[list[Any]]] = mapped_column(JSON, default=list)  # [id, lat, lon, estado]
    justificacion: Mapped[str] = mapped_column(Text)
    radio_busqueda_m: Mapped[float] = mapped_column(Float)
    iteraciones_busqueda: Mapped[int] = mapped_column(Integer)
    elementos_examinados: Mapped[int] = mapped_column(Integer)
    tiempos_ms: Mapped[dict[str, float]] = mapped_column(JSON)
    estado_servicio: Mapped[str] = mapped_column(String(24), default="CONDUCTOR_ASIGNADO", index=True)
    turno_asignacion: Mapped[int] = mapped_column(Integer, default=0)
    fecha_recogida: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_finalizacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    espera_real_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    solicitud: Mapped[Solicitud] = relationship(back_populates="asignacion")


class ResultadoSimulacion(Base):
    __tablename__ = "resultados_simulacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_configuracion: Mapped[Optional[int]] = mapped_column(ForeignKey("configuraciones.id", ondelete="SET NULL"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    motivo: Mapped[str] = mapped_column(String(40))
    turno: Mapped[int] = mapped_column(Integer)
    tiempo_simulado_s: Mapped[float] = mapped_column(Float)
    estadisticas: Mapped[dict[str, Any]] = mapped_column(JSON)


class MetricaRendimiento(Base):
    __tablename__ = "metricas_rendimiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc, index=True)
    tipo: Mapped[str] = mapped_column(String(30), index=True)  # turno | despacho | benchmark
    nombre: Mapped[str] = mapped_column(String(80))
    valor: Mapped[float] = mapped_column(Float)
    unidad: Mapped[str] = mapped_column(String(16))
    detalle: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

"""Esquemas Pydantic de entrada de la API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Coordenada(BaseModel):
    latitud: float = Field(..., ge=-90, le=90)
    longitud: float = Field(..., ge=-180, le=180)
    direccion: str = Field("", max_length=300)


class SolicitudServicio(BaseModel):
    origen: Coordenada
    destino: Coordenada
    # Conductor elegido por el pasajero tras la cotización (opcional; por defecto, el de menor ETA).
    id_conductor: Optional[int] = Field(None, ge=1)


class SolicitudCotizacion(BaseModel):
    origen: Coordenada
    destino: Coordenada


class ConfiguracionEntrada(BaseModel):
    id_distrito: str = Field(..., min_length=2, max_length=80)
    cantidad_conductores: int = Field(1500, ge=0, le=50_000)
    semilla: int = Field(42, ge=0, le=2**31 - 1)
    velocidad_promedio_kmh: float = Field(30.0, ge=5, le=120)
    variacion_velocidad: float = Field(0.15, ge=0, le=0.5)
    proporcion_inactivos: float = Field(0.03, ge=0, le=0.9)
    cantidad_candidatos: int = Field(5, ge=1, le=50)
    radio_inicial_metros: float = Field(250.0, ge=10, le=10_000)
    multiplicador_velocidad: float = Field(1.0, ge=0.1, le=64)
    intervalo_actualizacion_s: float = Field(0.5, ge=0.05, le=10)
    modo: Literal["AUTOMATICO", "MANUAL"] = "AUTOMATICO"
    solicitudes_por_minuto: float = Field(6.0, ge=0, le=600)
    tipo_visualizacion: Literal["2D", "3D"] = "2D"
    capacidad_quadtree: int = Field(16, ge=1, le=512)


class ParametrosEnCaliente(BaseModel):
    multiplicador_velocidad: Optional[float] = Field(None, ge=0.1, le=64)
    intervalo_actualizacion_s: Optional[float] = Field(None, ge=0.05, le=10)
    solicitudes_por_minuto: Optional[float] = Field(None, ge=0, le=600)
    modo: Optional[Literal["AUTOMATICO", "MANUAL"]] = None
    tipo_visualizacion: Optional[Literal["2D", "3D"]] = None
    cantidad_candidatos: Optional[int] = Field(None, ge=1, le=50)
    radio_inicial_metros: Optional[float] = Field(None, ge=10, le=10_000)


class AccionControl(BaseModel):
    factor: Optional[float] = Field(None, gt=1, le=8)

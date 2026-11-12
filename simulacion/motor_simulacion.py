"""Motor de simulación por turnos: movimiento, ciclo de servicio, demanda y estadísticas.

El motor es independiente de la API: produce eventos que la capa de servicios
persiste y transmite por WebSocket.
"""

from __future__ import annotations

import math
import random
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from algoritmos.haversine import distancia_haversine_rapida
from estructuras.grafo_vial import GrafoVial
from simulacion.conductor import Conductor, EstadoConductor
from simulacion.despachador import Despachador, ParametrosDespacho, ResultadoAsignacion
from simulacion.flota import Flota, ParametrosFlota
from simulacion.pasajero import ESTADOS_ACTIVOS, EstadoPasajero


class ModoSimulacion(str, Enum):
    AUTOMATICO = "AUTOMATICO"  # avance continuo y demanda generada automáticamente
    MANUAL = "MANUAL"  # el usuario controla los turnos y crea las solicitudes


class EstadoSimulacion(str, Enum):
    DETENIDA = "DETENIDA"
    EJECUTANDO = "EJECUTANDO"
    PAUSADA = "PAUSADA"


@dataclass
class ConfiguracionSimulacion:
    id_distrito: str = ""
    cantidad_conductores: int = 1000
    semilla: int = 42
    velocidad_promedio_kmh: float = 30.0
    variacion_velocidad: float = 0.15
    proporcion_inactivos: float = 0.03
    cantidad_candidatos: int = 5
    radio_inicial_metros: float = 250.0
    # Velocidad de simulación respecto al reloj real: ×1 = tiempo real.
    # Cada turno avanza intervalo_actualizacion_s × multiplicador_velocidad segundos simulados.
    multiplicador_velocidad: float = 1.0
    intervalo_actualizacion_s: float = 0.5
    modo: ModoSimulacion = ModoSimulacion.AUTOMATICO
    solicitudes_por_minuto: float = 6.0
    tipo_visualizacion: str = "2D"
    capacidad_quadtree: int = 16

    def validar(self) -> None:
        if not (0 <= self.cantidad_conductores <= 50_000):
            raise ValueError("La cantidad de conductores debe estar entre 0 y 50 000")
        if not (5 <= self.velocidad_promedio_kmh <= 120):
            raise ValueError("La velocidad promedio debe estar entre 5 y 120 km/h")
        if not (1 <= self.cantidad_candidatos <= 50):
            raise ValueError("El número de candidatos debe estar entre 1 y 50")
        if not (0.1 <= self.multiplicador_velocidad <= 64):
            raise ValueError("El multiplicador de velocidad debe estar entre 0.1 y 64")
        if not (0.05 <= self.intervalo_actualizacion_s <= 10):
            raise ValueError("El intervalo de actualización debe estar entre 0.05 y 10 s")
        if not (0 <= self.solicitudes_por_minuto <= 600):
            raise ValueError("La demanda automática debe estar entre 0 y 600 solicitudes/min")
        if self.tipo_visualizacion not in ("2D", "3D"):
            raise ValueError("Tipo de visualización inválido (2D o 3D)")

    def como_diccionario(self) -> dict[str, Any]:
        datos = asdict(self)
        datos["modo"] = self.modo.value
        return datos


@dataclass
class ResumenTurno:
    turno: int
    tiempo_simulado_s: float
    conductores_movidos: int
    cambios_estado: list[int] = field(default_factory=list)
    eventos: list[dict[str, Any]] = field(default_factory=list)
    duracion_ms: float = 0.0
    actualizaciones_quadtree: int = 0


@dataclass
class ServicioEnCurso:
    id_pasajero: int
    id_conductor: int
    id_asignacion: Optional[int]
    ruta_viaje: list[int]
    turno_asignacion: int
    tiempo_asignacion_s: float
    eta_recogida_s: float


class MotorSimulacion:
    def __init__(self, grafo: GrafoVial, configuracion: ConfiguracionSimulacion) -> None:
        configuracion.validar()
        self.grafo = grafo
        self.configuracion = configuracion
        self.cerrojo = threading.RLock()
        self.estado = EstadoSimulacion.DETENIDA
        # Observador invocado dentro del cerrojo justo después de cada despacho
        # (la capa de servicios lo usa para serializar rutas antes de que el conductor se mueva).
        self.observador_asignacion: Optional[Callable[[ResultadoAsignacion], None]] = None
        self._construir()

    # ================================================================ ciclo de vida
    def _construir(self) -> None:
        c = self.configuracion
        # Generadores independientes derivados de la semilla: las solicitudes manuales
        # no alteran la secuencia de movimiento ni la de demanda automática.
        self.generador_flota = random.Random(c.semilla)
        self.generador_movimiento = random.Random(c.semilla * 7919 + 1)
        self.generador_demanda = random.Random(c.semilla * 104729 + 2)
        self.flota = Flota(self.grafo, ParametrosFlota(
            cantidad_conductores=c.cantidad_conductores,
            semilla=c.semilla,
            velocidad_promedio_kmh=c.velocidad_promedio_kmh,
            variacion_velocidad=c.variacion_velocidad,
            proporcion_inactivos=c.proporcion_inactivos,
            capacidad_quadtree=c.capacidad_quadtree,
        ))
        self.flota.generar_flota(self.generador_flota)
        self.despachador = Despachador(
            self.grafo, self.flota,
            ParametrosDespacho(cantidad_candidatos=c.cantidad_candidatos, radio_inicial_metros=c.radio_inicial_metros),
            self.cerrojo,
        )
        self.turno = 0
        self.tiempo_simulado_s = 0.0
        self.servicios: dict[int, ServicioEnCurso] = {}  # por id_pasajero
        self.finalizados_recientes: deque[int] = deque(maxlen=300)
        self.estadisticas = {
            "solicitudes_totales": 0,
            "asignaciones_exitosas": 0,
            "asignaciones_fallidas": 0,
            "viajes_completados": 0,
            "suma_eta_s": 0.0,
            "suma_distancia_recogida_m": 0.0,
            "suma_distancia_haversine_m": 0.0,
            "suma_espera_real_s": 0.0,
            "recogidas": 0,
            "duracion_turno_ms_total": 0.0,
            "turnos_medidos": 0,
            "ultima_duracion_turno_ms": 0.0,
            "actualizaciones_quadtree": 0,
        }

    def reiniciar(self) -> None:
        with self.cerrojo:
            self.estado = EstadoSimulacion.DETENIDA
            self._construir()

    def iniciar(self) -> None:
        self.estado = EstadoSimulacion.EJECUTANDO

    def pausar(self) -> None:
        if self.estado is EstadoSimulacion.EJECUTANDO:
            self.estado = EstadoSimulacion.PAUSADA

    def reanudar(self) -> None:
        if self.estado is EstadoSimulacion.PAUSADA:
            self.estado = EstadoSimulacion.EJECUTANDO

    def detener(self) -> None:
        self.estado = EstadoSimulacion.DETENIDA

    def cambiar_multiplicador(self, factor: float) -> float:
        nuevo = min(64.0, max(0.25, self.configuracion.multiplicador_velocidad * factor))
        self.configuracion.multiplicador_velocidad = round(nuevo, 3)
        return self.configuracion.multiplicador_velocidad

    @property
    def segundos_por_turno(self) -> float:
        """Paso fijo (determinista) atado al reloj real: los turnos se ejecutan cada
        ``intervalo_actualizacion_s`` segundos reales, así que ×1 equivale a tiempo real."""
        return self.configuracion.intervalo_actualizacion_s * self.configuracion.multiplicador_velocidad

    # ================================================================ solicitudes
    def solicitar_servicio(
        self, latitud_origen: float, longitud_origen: float, latitud_destino: float, longitud_destino: float,
        direccion_origen: str = "", direccion_destino: str = "", id_conductor_preferido: Optional[int] = None,
    ) -> ResultadoAsignacion:
        with self.cerrojo:
            self.despachador.turno_actual = self.turno
            resultado = self.despachador.procesar_solicitud(
                latitud_origen, longitud_origen, latitud_destino, longitud_destino, direccion_origen, direccion_destino,
                id_conductor_preferido,
            )
            self.estadisticas["solicitudes_totales"] += 1
            if resultado.exito and resultado.conductor is not None:
                self.estadisticas["asignaciones_exitosas"] += 1
                self.estadisticas["suma_eta_s"] += resultado.eta_recogida_s
                self.estadisticas["suma_distancia_recogida_m"] += resultado.distancia_recogida_m
                self.estadisticas["suma_distancia_haversine_m"] += resultado.distancia_haversine_m
                pasajero = resultado.pasajero
                pasajero.tiempo_asignacion_s = self.tiempo_simulado_s
                pasajero.distancia_recogida_m = resultado.distancia_recogida_m
                pasajero.distancia_viaje_m = resultado.distancia_viaje_m
                pasajero.eta_recogida_s = resultado.eta_recogida_s
                self.servicios[resultado.pasajero.id_pasajero] = ServicioEnCurso(
                    resultado.pasajero.id_pasajero, resultado.conductor.id_conductor, None,
                    resultado.ruta_viaje_nodos, self.turno, self.tiempo_simulado_s, resultado.eta_recogida_s,
                )
            else:
                self.estadisticas["asignaciones_fallidas"] += 1
                self.finalizados_recientes.append(resultado.pasajero.id_pasajero)
            self._depurar_pasajeros()
            if self.observador_asignacion is not None:
                self.observador_asignacion(resultado)
            return resultado

    def vincular_asignacion(self, id_pasajero: int, id_asignacion: int) -> None:
        servicio = self.servicios.get(id_pasajero)
        if servicio is not None:
            servicio.id_asignacion = id_asignacion

    def generar_solicitud_aleatoria(self) -> Optional[tuple[float, float, float, float]]:
        nodos = self.grafo.lista_nodos_circulables
        g = self.generador_demanda
        for _ in range(20):
            a = nodos[g.randrange(len(nodos))]
            b = nodos[g.randrange(len(nodos))]
            (la, oa), (lb, ob) = self.grafo.coordenadas(a), self.grafo.coordenadas(b)
            if distancia_haversine_rapida(la, oa, lb, ob) >= 600:
                # Pequeño desplazamiento: el pasajero no está exactamente sobre el nodo.
                return (la + g.uniform(-1e-4, 1e-4), oa + g.uniform(-1e-4, 1e-4),
                        lb + g.uniform(-1e-4, 1e-4), ob + g.uniform(-1e-4, 1e-4))
        return None

    def _muestrear_poisson(self, media: float) -> int:
        """Algoritmo de Knuth con el generador de demanda (reproducible)."""
        if media <= 0:
            return 0
        limite, k, p = math.exp(-media), 0, 1.0
        while True:
            p *= self.generador_demanda.random()
            if p <= limite:
                return k
            k += 1

    # ================================================================ turnos
    def ejecutar_turno(self) -> tuple[ResumenTurno, list[ResultadoAsignacion]]:
        """Un turno: demanda automática, movimiento, actualización del Quadtree y estados."""
        inicio = time.perf_counter()
        asignaciones: list[ResultadoAsignacion] = []
        with self.cerrojo:
            self.turno += 1
            dt = self.segundos_por_turno
            self.tiempo_simulado_s += dt
            resumen = ResumenTurno(self.turno, self.tiempo_simulado_s, 0)

            if self.configuracion.modo is ModoSimulacion.AUTOMATICO:
                for _ in range(self._muestrear_poisson(self.configuracion.solicitudes_por_minuto * dt / 60.0)):
                    solicitud = self.generar_solicitud_aleatoria()
                    if solicitud is not None:
                        asignaciones.append(self.solicitar_servicio(*solicitud))

            for conductor in self.flota.conductores.values():
                if conductor.estado is EstadoConductor.INACTIVO:
                    continue
                metros = conductor.velocidad / 3.6 * dt
                evento = conductor.avanzar_por_ruta(metros, self.grafo, self.generador_movimiento)
                self.flota.actualizar_indice(conductor)
                resumen.conductores_movidos += 1
                if evento.llego_al_final_de_ruta:
                    self._procesar_llegada(conductor, resumen)
            resumen.actualizaciones_quadtree = resumen.conductores_movidos
            self.estadisticas["actualizaciones_quadtree"] += resumen.conductores_movidos

            resumen.duracion_ms = (time.perf_counter() - inicio) * 1000
            self.estadisticas["duracion_turno_ms_total"] += resumen.duracion_ms
            self.estadisticas["turnos_medidos"] += 1
            self.estadisticas["ultima_duracion_turno_ms"] = resumen.duracion_ms
        return resumen, asignaciones

    def ejecutar_turnos(self, cantidad: int) -> list[ResumenTurno]:
        """Ejecución sin intervención humana (miles de movimientos)."""
        return [self.ejecutar_turno()[0] for _ in range(cantidad)]

    def _procesar_llegada(self, conductor: Conductor, resumen: ResumenTurno) -> None:
        id_pasajero = conductor.id_pasajero_asignado
        servicio = self.servicios.get(id_pasajero) if id_pasajero is not None else None
        pasajero = self.despachador.pasajeros.get(id_pasajero) if id_pasajero is not None else None
        if servicio is None or pasajero is None:
            conductor.cancelar_asignacion()
            conductor.reanudar_circulacion_libre(self.grafo, self.generador_movimiento)
            return

        if conductor.estado is EstadoConductor.OCUPADO:
            # Llegó al punto de recogida.
            pasajero.cambiar_estado(EstadoPasajero.RECOGIDO)
            pasajero.tiempo_recogida_s = self.tiempo_simulado_s
            espera = self.tiempo_simulado_s - servicio.tiempo_asignacion_s
            self.estadisticas["suma_espera_real_s"] += espera
            self.estadisticas["recogidas"] += 1
            conductor.iniciar_servicio(servicio.ruta_viaje)
            pasajero.cambiar_estado(EstadoPasajero.VIAJANDO)
            resumen.cambios_estado.append(conductor.id_conductor)
            resumen.eventos.append({
                "tipo": "recogida", "id_pasajero": pasajero.id_pasajero, "id_conductor": conductor.id_conductor,
                "id_asignacion": servicio.id_asignacion, "espera_real_s": round(espera, 1),
                "eta_estimado_s": round(servicio.eta_recogida_s, 1), "turno": self.turno,
            })
        elif conductor.estado is EstadoConductor.EN_SERVICIO:
            pasajero.cambiar_estado(EstadoPasajero.FINALIZADO)
            pasajero.tiempo_llegada_s = self.tiempo_simulado_s
            conductor.finalizar_servicio()
            conductor.reanudar_circulacion_libre(self.grafo, self.generador_movimiento)
            self.estadisticas["viajes_completados"] += 1
            del self.servicios[pasajero.id_pasajero]
            self.finalizados_recientes.append(pasajero.id_pasajero)
            resumen.cambios_estado.append(conductor.id_conductor)
            resumen.eventos.append({
                "tipo": "finalizacion", "id_pasajero": pasajero.id_pasajero, "id_conductor": conductor.id_conductor,
                "id_asignacion": servicio.id_asignacion, "turno": self.turno,
                "duracion_total_s": round(self.tiempo_simulado_s - servicio.tiempo_asignacion_s, 1),
            })

    def _depurar_pasajeros(self) -> None:
        """Evita crecimiento ilimitado: conserva solo los últimos pasajeros finalizados."""
        pasajeros = self.despachador.pasajeros
        if len(pasajeros) <= 2000:
            return
        conservar = set(self.finalizados_recientes) | {p for p, x in pasajeros.items() if x.estado in ESTADOS_ACTIVOS}
        for id_pasajero in [p for p in pasajeros if p not in conservar]:
            del pasajeros[id_pasajero]

    # ================================================================ consultas
    def obtener_seguimiento(self, id_pasajero: int) -> Optional[dict[str, Any]]:
        """Estado en vivo de un viaje: fase, posición del conductor y lo que falta recorrer.

        Fases: ``recogida`` (conductor en camino), ``viaje`` (pasajero a bordo), ``finalizado``
        y ``cancelado``. Devuelve ``None`` si el pasajero no pertenece a esta simulación."""
        with self.cerrojo:
            pasajero = self.despachador.pasajeros.get(id_pasajero)
            if pasajero is None:
                return None
            fase = {
                EstadoPasajero.CONDUCTOR_ASIGNADO: "recogida",
                EstadoPasajero.RECOGIDO: "viaje",
                EstadoPasajero.VIAJANDO: "viaje",
                EstadoPasajero.FINALIZADO: "finalizado",
            }.get(pasajero.estado, "cancelado")
            datos: dict[str, Any] = {
                "fase": fase,
                "pasajero": pasajero.obtener_informacion(),
                "turno": self.turno,
                "tiempo_simulado_s": round(self.tiempo_simulado_s, 1),
                "estado_simulacion": self.estado.value,
                "modo": self.configuracion.modo.value,
                "multiplicador_velocidad": self.configuracion.multiplicador_velocidad,
                "distancia_recogida_m": pasajero.distancia_recogida_m,
                "distancia_viaje_m": pasajero.distancia_viaje_m,
                "eta_recogida_s": pasajero.eta_recogida_s,
                "espera_real_s": pasajero.espera_real_s,
                "duracion_viaje_s": pasajero.duracion_viaje_s,
                "transcurrido_s": (round(self.tiempo_simulado_s - pasajero.tiempo_asignacion_s, 1)
                                   if pasajero.tiempo_asignacion_s is not None else None),
                "conductor": None,
                "nodos_restantes": [],
                "nodos_viaje": [],
                "distancia_restante_m": 0.0,
                "eta_restante_s": 0.0,
            }
            conductor = self.flota.obtener_conductor(pasajero.id_conductor_asignado) if pasajero.id_conductor_asignado else None
            if conductor is not None:
                datos["conductor"] = conductor.obtener_informacion()
            servicio = self.servicios.get(id_pasajero)
            if conductor is not None and servicio is not None and fase in ("recogida", "viaje"):
                restante = conductor.distancia_restante_ruta(self.grafo)
                datos["distancia_restante_m"] = round(restante, 1)
                datos["eta_restante_s"] = round(restante / (conductor.velocidad / 3.6), 1)
                datos["nodos_restantes"] = conductor.ruta_actual[conductor.indice_ruta + 1:]
                if fase == "recogida":
                    datos["nodos_viaje"] = servicio.ruta_viaje
            return datos

    def obtener_estadisticas(self) -> dict[str, Any]:
        with self.cerrojo:
            conteo = self.flota.contar_por_estado()
            e = self.estadisticas
            exitosas = e["asignaciones_exitosas"]
            activos = sum(1 for p in self.despachador.pasajeros.values() if p.estado in ESTADOS_ACTIVOS)
            return {
                "estado_simulacion": self.estado.value,
                "modo": self.configuracion.modo.value,
                "distrito": self.configuracion.id_distrito,
                "turno": self.turno,
                "tiempo_simulado_s": round(self.tiempo_simulado_s, 1),
                "multiplicador_velocidad": self.configuracion.multiplicador_velocidad,
                "conductores_totales": len(self.flota),
                "conductores_disponibles": conteo["DISPONIBLE"],
                "conductores_ocupados": conteo["OCUPADO"] + conteo["EN_SERVICIO"],
                "conductores_en_recogida": conteo["OCUPADO"],
                "conductores_en_servicio": conteo["EN_SERVICIO"],
                "conductores_inactivos": conteo["INACTIVO"],
                "pasajeros_activos": activos,
                "solicitudes_realizadas": e["solicitudes_totales"],
                "asignaciones_exitosas": exitosas,
                "asignaciones_fallidas": e["asignaciones_fallidas"],
                "asignaciones_completadas": e["viajes_completados"],
                "eta_promedio_s": round(e["suma_eta_s"] / exitosas, 1) if exitosas else None,
                "distancia_promedio_recogida_m": round(e["suma_distancia_recogida_m"] / exitosas, 1) if exitosas else None,
                "distancia_promedio_haversine_m": round(e["suma_distancia_haversine_m"] / exitosas, 1) if exitosas else None,
                "espera_real_promedio_s": round(e["suma_espera_real_s"] / e["recogidas"], 1) if e["recogidas"] else None,
                "duracion_turno_promedio_ms": round(e["duracion_turno_ms_total"] / e["turnos_medidos"], 2) if e["turnos_medidos"] else None,
                "ultima_duracion_turno_ms": round(e["ultima_duracion_turno_ms"], 2),
                "actualizaciones_quadtree": e["actualizaciones_quadtree"],
                "nodos_quadtree": None,
                "nodos_grafo": self.grafo.cantidad_nodos,
                "aristas_grafo": self.grafo.cantidad_aristas,
            }

    def obtener_huella_estado(self) -> list[tuple[int, float, float, str]]:
        """Representación compacta para verificar reproducibilidad."""
        with self.cerrojo:
            return [(c.id_conductor, round(c.latitud, 9), round(c.longitud, 9), c.estado.value) for c in self.flota]

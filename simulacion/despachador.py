"""Despachador: coordina Quadtree + Haversine + heap + Dijkstra para asignar conductores."""

from __future__ import annotations

import itertools
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from algoritmos.dijkstra import calcular_eta_segundos, formatear_eta
from algoritmos.haversine import distancia_haversine_rapida
from estructuras.grafo_vial import GrafoVial
from estructuras.utilidades_geograficas import rectangulo_que_contiene_circulo
from estructuras.nodo_quadtree import EntradaEspacial
from simulacion.conductor import Conductor, EstadoConductor
from simulacion.flota import Flota
from simulacion.pasajero import EstadoPasajero, Pasajero


class CodigoResultado:
    ASIGNADO = "ASIGNADO"
    DATOS_INVALIDOS = "DATOS_INVALIDOS"
    ORIGEN_SIN_CONEXION_VIAL = "ORIGEN_SIN_CONEXION_VIAL"
    DESTINO_SIN_CONEXION_VIAL = "DESTINO_SIN_CONEXION_VIAL"
    SIN_CONDUCTORES_DISPONIBLES = "SIN_CONDUCTORES_DISPONIBLES"
    SIN_RUTA_DESDE_CANDIDATOS = "SIN_RUTA_DESDE_CANDIDATOS"
    DESTINO_INALCANZABLE = "DESTINO_INALCANZABLE"


@dataclass(slots=True)
class ParametrosDespacho:
    cantidad_candidatos: int = 5
    radio_inicial_metros: float = 250.0
    factor_expansion: float = 2.0
    distancia_maxima_ajuste_metros: float = 400.0
    lotes_maximos: int = 3  # si los k candidatos carecen de ruta, se evalúan k más (hasta 3 lotes)


@dataclass(slots=True)
class EvaluacionCandidato:
    id_conductor: int
    nombre: str
    placa: str
    velocidad_kmh: float
    distancia_haversine_m: float
    distancia_ruta_m: float = math.inf
    eta_segundos: float = math.inf
    nodos_explorados: int = 0
    valido: bool = False
    motivo: str = ""
    seleccionado: bool = False
    nodos_ruta: list[int] = field(default_factory=list)
    latitud: float = 0.0
    longitud: float = 0.0

    def como_diccionario(self) -> dict[str, Any]:
        return {
            "id_conductor": self.id_conductor,
            "nombre": self.nombre,
            "placa": self.placa,
            "velocidad_kmh": round(self.velocidad_kmh, 1),
            "latitud": self.latitud,
            "longitud": self.longitud,
            "distancia_haversine_m": round(self.distancia_haversine_m, 1),
            "distancia_ruta_m": None if math.isinf(self.distancia_ruta_m) else round(self.distancia_ruta_m, 1),
            "eta_segundos": None if math.isinf(self.eta_segundos) else round(self.eta_segundos, 1),
            "eta_texto": formatear_eta(self.eta_segundos),
            "nodos_explorados": self.nodos_explorados,
            "valido": self.valido,
            "motivo": self.motivo,
            "seleccionado": self.seleccionado,
        }


@dataclass
class ResultadoAsignacion:
    exito: bool
    codigo: str
    mensaje: str
    pasajero: Pasajero
    candidatos: list[EvaluacionCandidato] = field(default_factory=list)
    conductor: Optional[Conductor] = None
    ruta_recogida_nodos: list[int] = field(default_factory=list)
    ruta_viaje_nodos: list[int] = field(default_factory=list)
    distancia_recogida_m: float = math.inf
    distancia_haversine_m: float = math.inf
    eta_recogida_s: float = math.inf
    distancia_viaje_m: float = math.inf
    duracion_viaje_s: float = math.inf
    radio_busqueda_m: float = 0.0
    iteraciones_busqueda: int = 0
    elementos_examinados: int = 0
    justificacion: str = ""
    tiempos_ms: dict[str, float] = field(default_factory=dict)
    fecha: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    anexos: dict[str, Any] = field(default_factory=dict)  # datos añadidos por capas superiores
    id_conductor_recomendado: Optional[int] = None  # el de menor ETA según el algoritmo
    eleccion_usuario: bool = False  # True si el pasajero eligió explícitamente al conductor
    aviso: str = ""


@dataclass
class Cotizacion:
    """Vista previa sin efectos: candidatos con su ETA real, sin asignar a nadie."""

    exito: bool
    codigo: str
    mensaje: str
    nodo_origen: Optional[int] = None
    nodo_destino: Optional[int] = None
    candidatos: list[EvaluacionCandidato] = field(default_factory=list)
    id_conductor_recomendado: Optional[int] = None
    disponibles_totales: int = 0
    disponibles_cercanos: int = 0
    radio_cercania_m: float = 1000.0
    cercanos: list[tuple[int, float, float]] = field(default_factory=list)  # (id, lat, lon)
    nodos_viaje: list[int] = field(default_factory=list)
    distancia_viaje_m: float = math.inf
    radio_busqueda_m: float = 0.0
    elementos_examinados: int = 0
    tiempos_ms: dict[str, float] = field(default_factory=dict)


class Despachador:
    """Recibe solicitudes y asigna el conductor disponible con menor ETA de recogida."""

    def __init__(
        self,
        grafo: GrafoVial,
        flota: Flota,
        parametros: Optional[ParametrosDespacho] = None,
        cerrojo: Optional[threading.RLock] = None,
    ) -> None:
        self.grafo = grafo
        self.flota = flota
        self.parametros = parametros or ParametrosDespacho()
        # Cerrojo compartido con el motor: evita que dos solicitudes concurrentes
        # (o un turno de simulación) observen al mismo conductor como DISPONIBLE.
        self.cerrojo = cerrojo or threading.RLock()
        self.pasajeros: dict[int, Pasajero] = {}
        self._secuencia_pasajeros = itertools.count(1)
        self.turno_actual = 0

    # ------------------------------------------------------------ utilidades
    def reiniciar_secuencia(self, inicio: int = 1) -> None:
        self._secuencia_pasajeros = itertools.count(inicio)

    def localizar_nodo(self, latitud: float, longitud: float) -> Optional[tuple[int, float]]:
        return self.grafo.localizar_nodo_cercano(latitud, longitud, self.parametros.distancia_maxima_ajuste_metros)

    @staticmethod
    def _filtro_disponible(entrada: EntradaEspacial) -> bool:
        return entrada.objeto.estado is EstadoConductor.DISPONIBLE

    def buscar_candidatos(self, latitud: float, longitud: float, cantidad: int):
        """Pasos 4-5: Quadtree + Haversine + heapq (k más cercanos exactos, solo disponibles)."""
        return self.flota.indice.buscar_k_mas_cercanos(
            latitud,
            longitud,
            k=cantidad,
            radio_inicial_metros=self.parametros.radio_inicial_metros,
            filtro=self._filtro_disponible,
            factor_expansion=self.parametros.factor_expansion,
        )

    def evaluar_candidato(self, conductor: Conductor, distancia_haversine: float, nodo_recogida: int) -> EvaluacionCandidato:
        """Paso 6-7: Dijkstra desde la posición real del conductor y conversión a ETA."""
        evaluacion = EvaluacionCandidato(
            id_conductor=conductor.id_conductor,
            nombre=conductor.nombre,
            placa=conductor.vehiculo.placa,
            velocidad_kmh=conductor.velocidad,
            distancia_haversine_m=distancia_haversine,
            latitud=conductor.latitud,
            longitud=conductor.longitud,
        )
        try:
            restante = conductor.distancia_restante_en_arista(self.grafo)
            ruta = self.grafo.calcular_ruta(conductor.nodo_siguiente, nodo_recogida)
        except KeyError as error:
            evaluacion.motivo = f"Nodo inválido: {error}"
            return evaluacion
        evaluacion.nodos_explorados = ruta.nodos_explorados
        if not ruta.encontrada:
            evaluacion.motivo = "Sin ruta vial dirigida hasta el pasajero (descartado)"
            return evaluacion
        evaluacion.distancia_ruta_m = restante + ruta.distancia_metros
        evaluacion.eta_segundos = calcular_eta_segundos(evaluacion.distancia_ruta_m, conductor.velocidad)
        evaluacion.nodos_ruta = ruta.nodos
        evaluacion.valido = True
        evaluacion.motivo = "Ruta válida"
        return evaluacion

    def _evaluar_lotes(self, latitud: float, longitud: float, nodo_origen: int):
        """Pasos 4-7: k candidatos (Quadtree + Haversine + heap) y Dijkstra por candidato.
        Si ninguno del lote tiene ruta se evalúa el siguiente lote (hasta lotes_maximos)."""
        k = self.parametros.cantidad_candidatos
        evaluaciones: list[EvaluacionCandidato] = []
        busqueda = None
        t_busqueda = t_rutas = 0.0
        for lote in range(1, self.parametros.lotes_maximos + 1):
            t = time.perf_counter()
            busqueda = self.buscar_candidatos(latitud, longitud, k * lote)
            t_busqueda += time.perf_counter() - t
            nuevos = busqueda.candidatos[k * (lote - 1):]
            if not nuevos:
                break
            t = time.perf_counter()
            for distancia, entrada in nuevos:
                evaluaciones.append(self.evaluar_candidato(entrada.objeto, distancia, nodo_origen))
            t_rutas += time.perf_counter() - t
            if any(e.valido for e in evaluaciones) or len(busqueda.candidatos) < k * lote:
                break
        return evaluaciones, busqueda, t_busqueda * 1000, t_rutas * 1000

    @staticmethod
    def _mejor(validos: list[EvaluacionCandidato]) -> EvaluacionCandidato:
        """Menor ETA (desempate: distancia por calles, id)."""
        return min(validos, key=lambda e: (e.eta_segundos, e.distancia_ruta_m, e.id_conductor))

    def cotizar(self, latitud_origen: float, longitud_origen: float, latitud_destino: float, longitud_destino: float,
                radio_cercania_m: float = 1000.0, maximo_cercanos: int = 400) -> Cotizacion:
        """Muestra los conductores disponibles y los candidatos con su ETA real SIN asignar
        (no crea pasajero ni cambia estados). El usuario confirma después."""
        tiempos: dict[str, float] = {}
        inicio = time.perf_counter()
        if not all(map(math.isfinite, (latitud_origen, longitud_origen, latitud_destino, longitud_destino))):
            return Cotizacion(False, CodigoResultado.DATOS_INVALIDOS, "Coordenadas inválidas")
        with self.cerrojo:
            nodo_origen = self.localizar_nodo(latitud_origen, longitud_origen)
            nodo_destino = self.localizar_nodo(latitud_destino, longitud_destino)
            maximo = self.parametros.distancia_maxima_ajuste_metros
            if nodo_origen is None:
                return Cotizacion(False, CodigoResultado.ORIGEN_SIN_CONEXION_VIAL,
                                  f"El origen no tiene red vial circulable a menos de {maximo:.0f} m: no existe una ruta válida.")
            if nodo_destino is None:
                return Cotizacion(False, CodigoResultado.DESTINO_SIN_CONEXION_VIAL,
                                  f"El destino no tiene red vial circulable a menos de {maximo:.0f} m (¿está fuera del distrito?).")
            cotizacion = Cotizacion(True, "COTIZADO", "", nodo_origen[0], nodo_destino[0], radio_cercania_m=radio_cercania_m)
            cotizacion.disponibles_totales = self.flota.contar_por_estado()[EstadoConductor.DISPONIBLE.value]
            # Conteo exacto de disponibles dentro del círculo (Quadtree por rectángulo + Haversine);
            # el tope ``maximo_cercanos`` solo limita cuántos se devuelven para dibujar.
            entradas = self.flota.indice.buscar_en_rectangulo(
                rectangulo_que_contiene_circulo(latitud_origen, longitud_origen, radio_cercania_m), self._filtro_disponible)
            distancias = ((distancia_haversine_rapida(latitud_origen, longitud_origen, e.latitud, e.longitud), e) for e in entradas)
            dentro = sorted(((d, e) for d, e in distancias if d <= radio_cercania_m), key=lambda t: t[0])
            cotizacion.disponibles_cercanos = len(dentro)
            cotizacion.cercanos = [(e.identificador, e.latitud, e.longitud) for _, e in dentro[:maximo_cercanos]]

            evaluaciones, busqueda, t_busqueda, t_rutas = self._evaluar_lotes(latitud_origen, longitud_origen, nodo_origen[0])
            tiempos["busqueda_quadtree"], tiempos["dijkstra_candidatos"] = t_busqueda, t_rutas
            cotizacion.candidatos = evaluaciones
            if busqueda is not None:
                cotizacion.radio_busqueda_m = busqueda.radio_final_metros
                cotizacion.elementos_examinados = busqueda.elementos_examinados
            validos = [e for e in evaluaciones if e.valido]
            if not evaluaciones:
                cotizacion.exito, cotizacion.codigo = False, CodigoResultado.SIN_CONDUCTORES_DISPONIBLES
                cotizacion.mensaje = "No hay conductores disponibles en el distrito."
            elif not validos:
                cotizacion.exito, cotizacion.codigo = False, CodigoResultado.SIN_RUTA_DESDE_CANDIDATOS
                cotizacion.mensaje = "Ningún candidato tiene ruta vial válida hasta el pasajero."
            else:
                mejor = self._mejor(validos)
                mejor.seleccionado = True  # recomendado
                cotizacion.id_conductor_recomendado = mejor.id_conductor
                viaje = self.grafo.calcular_ruta(nodo_origen[0], nodo_destino[0])
                if not viaje.encontrada:
                    cotizacion.exito, cotizacion.codigo = False, CodigoResultado.DESTINO_INALCANZABLE
                    cotizacion.mensaje = "No existe ruta vial dirigida desde el origen hasta el destino."
                else:
                    cotizacion.nodos_viaje, cotizacion.distancia_viaje_m = viaje.nodos, viaje.distancia_metros
                    cotizacion.mensaje = f"{len(validos)} conductores evaluados; recomendado: {mejor.id_conductor}"
            tiempos["total"] = (time.perf_counter() - inicio) * 1000
            cotizacion.tiempos_ms = {k: round(v, 3) for k, v in tiempos.items()}
            return cotizacion

    # ------------------------------------------------------------ flujo principal
    def procesar_solicitud(
        self,
        latitud_origen: float,
        longitud_origen: float,
        latitud_destino: float,
        longitud_destino: float,
        direccion_origen: str = "",
        direccion_destino: str = "",
        id_conductor_preferido: Optional[int] = None,
    ) -> ResultadoAsignacion:
        """Asigna el conductor de menor ETA o, si el pasajero eligió uno (``id_conductor_preferido``)
        y sigue disponible con ruta válida, ese conductor. Si ya no está disponible se asigna el mejor."""
        tiempos: dict[str, float] = {}
        inicio_total = time.perf_counter()
        pasajero = Pasajero(
            id_pasajero=next(self._secuencia_pasajeros),
            latitud_origen=latitud_origen,
            longitud_origen=longitud_origen,
            latitud_destino=latitud_destino,
            longitud_destino=longitud_destino,
            direccion_origen=direccion_origen,
            direccion_destino=direccion_destino,
            turno_solicitud=self.turno_actual,
        )

        # 2. Validación de coordenadas.
        if not all(map(math.isfinite, (latitud_origen, longitud_origen, latitud_destino, longitud_destino))) or not (
            -90 <= latitud_origen <= 90 and -90 <= latitud_destino <= 90
            and -180 <= longitud_origen <= 180 and -180 <= longitud_destino <= 180
        ):
            return self._rechazar(pasajero, CodigoResultado.DATOS_INVALIDOS, "Coordenadas inválidas", tiempos)

        with self.cerrojo:
            self.pasajeros[pasajero.id_pasajero] = pasajero
            # 3. Localización de nodos viales (Quadtree de nodos).
            t = time.perf_counter()
            nodo_origen = self.localizar_nodo(latitud_origen, longitud_origen)
            nodo_destino = self.localizar_nodo(latitud_destino, longitud_destino)
            tiempos["localizacion_nodos"] = (time.perf_counter() - t) * 1000
            if nodo_origen is None:
                return self._rechazar(
                    pasajero, CodigoResultado.ORIGEN_SIN_CONEXION_VIAL,
                    f"El origen no tiene red vial circulable a menos de {self.parametros.distancia_maxima_ajuste_metros:.0f} m: "
                    "no existe una ruta válida.", tiempos)
            if nodo_destino is None:
                return self._rechazar(
                    pasajero, CodigoResultado.DESTINO_SIN_CONEXION_VIAL,
                    f"El destino no tiene red vial circulable a menos de {self.parametros.distancia_maxima_ajuste_metros:.0f} m.",
                    tiempos)
            pasajero.nodo_origen, pasajero.nodo_destino = nodo_origen[0], nodo_destino[0]

            # 4-7. Candidatos y evaluación por lotes.
            evaluaciones, busqueda, tiempos["busqueda_quadtree"], tiempos["dijkstra_candidatos"] = \
                self._evaluar_lotes(latitud_origen, longitud_origen, pasajero.nodo_origen)

            resultado = ResultadoAsignacion(False, "", "", pasajero, candidatos=evaluaciones)
            if busqueda is not None:
                resultado.radio_busqueda_m = busqueda.radio_final_metros
                resultado.iteraciones_busqueda = busqueda.iteraciones
                resultado.elementos_examinados = busqueda.elementos_examinados

            if not evaluaciones:
                return self._rechazar(pasajero, CodigoResultado.SIN_CONDUCTORES_DISPONIBLES,
                                      "No hay conductores disponibles en el distrito.", tiempos, resultado)
            validos = [e for e in evaluaciones if e.valido]
            if not validos:
                return self._rechazar(pasajero, CodigoResultado.SIN_RUTA_DESDE_CANDIDATOS,
                                      "Ningún candidato tiene ruta vial válida hasta el pasajero.", tiempos, resultado)

            # 8-9. Comparación y elección del menor ETA (desempate: distancia por calles, id).
            mejor = self._mejor(validos)
            resultado.id_conductor_recomendado = mejor.id_conductor
            elegido = mejor
            if id_conductor_preferido is not None and id_conductor_preferido != mejor.id_conductor:
                preferido = next((e for e in evaluaciones if e.id_conductor == id_conductor_preferido), None)
                if preferido is None:
                    candidato = self.flota.obtener_conductor(id_conductor_preferido)
                    if candidato is not None and candidato.estado is EstadoConductor.DISPONIBLE:
                        preferido = self.evaluar_candidato(candidato, distancia_haversine_rapida(
                            latitud_origen, longitud_origen, candidato.latitud, candidato.longitud), pasajero.nodo_origen)
                        evaluaciones.append(preferido)
                if preferido is not None and preferido.valido:
                    elegido = preferido
                    resultado.eleccion_usuario = True
                else:
                    resultado.aviso = (f"El conductor {id_conductor_preferido} elegido ya no está disponible; "
                                       f"se asignó el mejor disponible ({mejor.id_conductor}).")
            elif id_conductor_preferido is not None:
                resultado.eleccion_usuario = True
            conductor = self.flota.obtener_conductor(elegido.id_conductor)
            assert conductor is not None and conductor.estado is EstadoConductor.DISPONIBLE

            # Ruta del viaje (después de elegir conductor; antes de confirmar).
            t = time.perf_counter()
            ruta_viaje = self.grafo.calcular_ruta(pasajero.nodo_origen, pasajero.nodo_destino)
            tiempos["dijkstra_viaje"] = (time.perf_counter() - t) * 1000
            if not ruta_viaje.encontrada:
                return self._rechazar(pasajero, CodigoResultado.DESTINO_INALCANZABLE,
                                      "No existe ruta vial dirigida desde el origen hasta el destino.", tiempos, resultado)

            # 10. Cambio de estado atómico (dentro del cerrojo).
            elegido.seleccionado = True
            conductor.asignar_ruta_recogida(elegido.nodos_ruta, pasajero.id_pasajero)
            pasajero.asignar_conductor(conductor.id_conductor)

            resultado.exito = True
            resultado.codigo = CodigoResultado.ASIGNADO
            resultado.conductor = conductor
            resultado.ruta_recogida_nodos = elegido.nodos_ruta
            resultado.ruta_viaje_nodos = ruta_viaje.nodos
            resultado.distancia_recogida_m = elegido.distancia_ruta_m
            resultado.distancia_haversine_m = elegido.distancia_haversine_m
            resultado.eta_recogida_s = elegido.eta_segundos
            resultado.distancia_viaje_m = ruta_viaje.distancia_metros
            resultado.duracion_viaje_s = calcular_eta_segundos(ruta_viaje.distancia_metros, conductor.velocidad)
            resultado.justificacion = self._justificar(elegido, evaluaciones)
            if elegido is not mejor:
                resultado.justificacion = (
                    f"Elegido por el pasajero: conductor {elegido.id_conductor} (ETA {formatear_eta(elegido.eta_segundos)}). "
                    f"El recomendado por el algoritmo era el {mejor.id_conductor} (ETA {formatear_eta(mejor.eta_segundos)}). "
                    + self._justificar(mejor, evaluaciones))
            if resultado.aviso:
                resultado.justificacion = resultado.aviso + " " + resultado.justificacion
            resultado.mensaje = f"Conductor {conductor.id_conductor} asignado: ETA {formatear_eta(elegido.eta_segundos)}"
            tiempos["total"] = (time.perf_counter() - inicio_total) * 1000
            resultado.tiempos_ms = {k_: round(v, 3) for k_, v in tiempos.items()}
            return resultado

    def _rechazar(
        self, pasajero: Pasajero, codigo: str, mensaje: str, tiempos: dict[str, float],
        resultado: Optional[ResultadoAsignacion] = None,
    ) -> ResultadoAsignacion:
        if pasajero.estado is EstadoPasajero.ESPERANDO:
            pasajero.cancelar(mensaje)
        resultado = resultado or ResultadoAsignacion(False, codigo, mensaje, pasajero)
        resultado.exito, resultado.codigo, resultado.mensaje = False, codigo, mensaje
        resultado.tiempos_ms = {k: round(v, 3) for k, v in tiempos.items()}
        return resultado

    @staticmethod
    def _justificar(elegido: EvaluacionCandidato, evaluaciones: list[EvaluacionCandidato]) -> str:
        validos = sorted((e for e in evaluaciones if e.valido), key=lambda e: e.eta_segundos)
        mas_cercano = min(evaluaciones, key=lambda e: e.distancia_haversine_m)
        texto = (
            f"Se evaluaron {len(evaluaciones)} candidatos ({len(validos)} con ruta válida). "
            f"El conductor {elegido.id_conductor} tiene el menor ETA ({formatear_eta(elegido.eta_segundos)}) "
            f"con {elegido.distancia_ruta_m:.0f} m por calles a {elegido.velocidad_kmh:.1f} km/h."
        )
        if mas_cercano.id_conductor != elegido.id_conductor:
            texto += (
                f" El más cercano en línea recta (conductor {mas_cercano.id_conductor}, "
                f"{mas_cercano.distancia_haversine_m:.0f} m) no fue elegido: "
                + (f"su ruta real mide {mas_cercano.distancia_ruta_m:.0f} m (ETA {formatear_eta(mas_cercano.eta_segundos)})."
                   if mas_cercano.valido else "no tiene ruta vial válida.")
            )
        if len(validos) > 1:
            texto += f" Ventaja frente al segundo mejor: {validos[1].eta_segundos - elegido.eta_segundos:.1f} s."
        return texto

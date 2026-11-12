"""Orquestación: motor de simulación + persistencia + difusión en tiempo real."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import fields
from typing import Any, Optional

from backend.servicios.catalogo_distritos import CatalogoDistritos
from backend.servicios.gestor_grafos import GestorGrafos
from backend.servicios.repositorio import Repositorio
from backend.servicios.serializacion import (
    contexto_conductores,
    coordenadas_lon_lat,
    serializar_cotizacion,
    serializar_resultado,
)
from backend.servicios.tiempo_real import ClienteTiempoReal, GestorTiempoReal
from simulacion.conductor import EstadoConductor
from simulacion.despachador import ResultadoAsignacion
from simulacion.motor_simulacion import ConfiguracionSimulacion, EstadoSimulacion, ModoSimulacion, MotorSimulacion

logger = logging.getLogger(__name__)


class ErrorServicio(RuntimeError):
    def __init__(self, mensaje: str, codigo_http: int = 400) -> None:
        super().__init__(mensaje)
        self.codigo_http = codigo_http


class ServicioSimulacion:
    def __init__(self, catalogo: CatalogoDistritos, gestor_grafos: GestorGrafos, repositorio: Repositorio,
                 tiempo_real: GestorTiempoReal) -> None:
        self.catalogo = catalogo
        self.gestor_grafos = gestor_grafos
        self.repositorio = repositorio
        self.tiempo_real = tiempo_real
        self.motor: Optional[MotorSimulacion] = None
        self.id_configuracion: Optional[int] = None
        self.configurando = False
        self._tarea_bucle: Optional[asyncio.Task] = None
        self._cerrojo_configuracion = asyncio.Lock()
        # id_pasajero -> id_asignacion: los eventos de recogida/finalización pueden ocurrir
        # en el mismo turno de la asignación, antes de que exista su fila en la BD.
        self._asignacion_por_pasajero: dict[int, int] = {}
        self.tiempo_real.proveedor_delta = self._calcular_delta_cliente

    # ================================================================ ciclo de vida
    def arrancar(self) -> None:
        if self._tarea_bucle is None:
            self._tarea_bucle = asyncio.create_task(self._bucle(), name="bucle-simulacion")

    async def apagar(self) -> None:
        if self.motor is not None and self.motor.turno > 0:
            await asyncio.to_thread(self._guardar_resultado, "apagado")
        if self._tarea_bucle is not None:
            self._tarea_bucle.cancel()
            try:
                await self._tarea_bucle
            except asyncio.CancelledError:
                pass

    def requerir_motor(self) -> MotorSimulacion:
        if self.motor is None:
            raise ErrorServicio("No hay simulación configurada: seleccione un distrito y genere la flota", 409)
        return self.motor

    # ================================================================ configuración
    async def configurar(self, datos: dict[str, Any]) -> dict[str, Any]:
        nombres_validos = {f.name for f in fields(ConfiguracionSimulacion)}
        datos = {k: v for k, v in datos.items() if k in nombres_validos and v is not None}
        if "modo" in datos:
            datos["modo"] = ModoSimulacion(datos["modo"])
        configuracion = ConfiguracionSimulacion(**datos)
        try:
            configuracion.validar()
        except ValueError as error:
            raise ErrorServicio(str(error), 422) from error
        if self.catalogo.obtener(configuracion.id_distrito) is None:
            raise ErrorServicio(f"Distrito desconocido: {configuracion.id_distrito}", 404)
        if not self.gestor_grafos.esta_descargado(configuracion.id_distrito):
            raise ErrorServicio("La red vial del distrito no está descargada. Descárguela primero.", 409)

        async with self._cerrojo_configuracion:
            self.configurando = True
            try:
                if self.motor is not None and self.motor.turno > 0:
                    await asyncio.to_thread(self._guardar_resultado, "reconfiguracion")
                grafo = await asyncio.to_thread(self.gestor_grafos.cargar_grafo, configuracion.id_distrito)
                inicio = time.perf_counter()
                motor = await asyncio.to_thread(MotorSimulacion, grafo, configuracion)
                motor.observador_asignacion = self._anexar_serializacion
                duracion = (time.perf_counter() - inicio) * 1000
                self.motor = motor
                self._asignacion_por_pasajero.clear()
                metadatos = self.gestor_grafos.leer_metadatos(configuracion.id_distrito)
                await asyncio.to_thread(self.repositorio.cancelar_en_curso, self.id_configuracion)
                self.id_configuracion = await asyncio.to_thread(
                    self.repositorio.guardar_configuracion, configuracion.como_diccionario(), metadatos)
                await asyncio.to_thread(self.repositorio.guardar_flota, self.id_configuracion, motor.flota)
                await asyncio.to_thread(self.repositorio.guardar_metrica, "configuracion", "generacion_flota_ms",
                                        duracion, "ms", {"conductores": configuracion.cantidad_conductores,
                                                         "distrito": configuracion.id_distrito})
            finally:
                self.configurando = False
        self.tiempo_real.reiniciar_clientes()
        estado = self.estado_simulacion()
        self.tiempo_real.difundir_evento({"tipo": "simulacion", "datos": estado})
        return estado

    def estado_simulacion(self) -> dict[str, Any]:
        if self.motor is None:
            return {"configurada": False, "configurando": self.configurando, "estado": EstadoSimulacion.DETENIDA.value}
        distrito = self.catalogo.obtener(self.motor.configuracion.id_distrito)
        return {
            "configurada": True,
            "configurando": self.configurando,
            "estado": self.motor.estado.value,
            "id_configuracion": self.id_configuracion,
            "configuracion": self.motor.configuracion.como_diccionario(),
            "distrito": distrito.resumen() if distrito else None,
            "turno": self.motor.turno,
            "tiempo_simulado_s": round(self.motor.tiempo_simulado_s, 1),
            "segundos_por_turno": self.motor.segundos_por_turno,
            "grafo": {"nodos": self.motor.grafo.cantidad_nodos, "aristas": self.motor.grafo.cantidad_aristas,
                      "nodos_circulables": len(self.motor.grafo.nodos_circulables),
                      "limites": self.motor.grafo.limites.como_lista()},
            "quadtree": {"elementos": len(self.motor.flota.indice), "nodos": self.motor.flota.indice.contar_nodos(),
                         "profundidad": self.motor.flota.indice.obtener_profundidad(),
                         "capacidad": self.motor.flota.indice.capacidad},
        }

    async def controlar(self, accion: str, factor: Optional[float] = None) -> dict[str, Any]:
        motor = self.requerir_motor()
        if accion == "iniciar":
            motor.iniciar()
        elif accion == "pausar":
            motor.pausar()
            await asyncio.to_thread(self._guardar_resultado, "pausa")
        elif accion == "reanudar":
            motor.reanudar()
        elif accion == "detener":
            motor.detener()
            await asyncio.to_thread(self._guardar_resultado, "detencion")
        elif accion == "avanzar":
            if motor.estado is EstadoSimulacion.EJECUTANDO:
                raise ErrorServicio("Pause la simulación para avanzar turno a turno", 409)
            await self._procesar_turno()
        elif accion == "reiniciar":
            if motor.turno > 0:
                await asyncio.to_thread(self._guardar_resultado, "reinicio")
            await asyncio.to_thread(motor.reiniciar)
            self._asignacion_por_pasajero.clear()
            await asyncio.to_thread(self.repositorio.cancelar_en_curso, self.id_configuracion)
            self.tiempo_real.reiniciar_clientes()
        elif accion == "acelerar":
            motor.cambiar_multiplicador(factor or 2.0)
        elif accion == "desacelerar":
            motor.cambiar_multiplicador(1.0 / (factor or 2.0))
        elif accion == "modo":
            motor.configuracion.modo = (ModoSimulacion.MANUAL if motor.configuracion.modo is ModoSimulacion.AUTOMATICO
                                        else ModoSimulacion.AUTOMATICO)
        else:
            raise ErrorServicio(f"Acción desconocida: {accion}", 404)
        estado = self.estado_simulacion()
        self.tiempo_real.difundir_evento({"tipo": "simulacion", "datos": estado})
        return estado

    def actualizar_parametros_en_caliente(self, datos: dict[str, Any]) -> dict[str, Any]:
        """Parámetros que no requieren regenerar la flota."""
        motor = self.requerir_motor()
        c = motor.configuracion
        with motor.cerrojo:
            if "multiplicador_velocidad" in datos:
                c.multiplicador_velocidad = float(datos["multiplicador_velocidad"])
            if "intervalo_actualizacion_s" in datos:
                c.intervalo_actualizacion_s = float(datos["intervalo_actualizacion_s"])
            if "solicitudes_por_minuto" in datos:
                c.solicitudes_por_minuto = float(datos["solicitudes_por_minuto"])
            if "modo" in datos:
                c.modo = ModoSimulacion(datos["modo"])
            if "tipo_visualizacion" in datos:
                c.tipo_visualizacion = str(datos["tipo_visualizacion"])
            if "cantidad_candidatos" in datos:
                c.cantidad_candidatos = int(datos["cantidad_candidatos"])
                motor.despachador.parametros.cantidad_candidatos = c.cantidad_candidatos
            if "radio_inicial_metros" in datos:
                c.radio_inicial_metros = float(datos["radio_inicial_metros"])
                motor.despachador.parametros.radio_inicial_metros = c.radio_inicial_metros
            try:
                c.validar()
            except ValueError as error:
                raise ErrorServicio(str(error), 422) from error
        estado = self.estado_simulacion()
        self.tiempo_real.difundir_evento({"tipo": "simulacion", "datos": estado})
        return estado

    # ================================================================ bucle
    async def _bucle(self) -> None:
        while True:
            try:
                motor = self.motor
                if motor is None or motor.estado is not EstadoSimulacion.EJECUTANDO or self.configurando:
                    await asyncio.sleep(0.2)
                    continue
                inicio = time.monotonic()
                await self._procesar_turno()
                restante = motor.configuracion.intervalo_actualizacion_s - (time.monotonic() - inicio)
                await asyncio.sleep(max(0.01, restante))
            except asyncio.CancelledError:
                raise
            except Exception:  # el bucle nunca debe morir
                logger.exception("Error en el bucle de simulación")
                await asyncio.sleep(1.0)

    async def _procesar_turno(self) -> None:
        motor = self.requerir_motor()
        resumen, asignaciones = await asyncio.to_thread(motor.ejecutar_turno)
        await asyncio.to_thread(self._persistir_turno, motor, resumen, asignaciones)
        for resultado in asignaciones:
            self._difundir_asignacion(resultado)
        for evento in resumen.eventos:
            self.tiempo_real.difundir_evento(evento)
        self.tiempo_real.difundir_evento({"tipo": "estadisticas", "datos": motor.obtener_estadisticas()})
        self.tiempo_real.notificar_turno()

    def _persistir_turno(self, motor: MotorSimulacion, resumen, asignaciones: list[ResultadoAsignacion]) -> None:
        for resultado in asignaciones:
            self._registrar(resultado, "automatica", motor)
        for evento in resumen.eventos:
            id_asignacion = evento.get("id_asignacion") or self._asignacion_por_pasajero.get(evento["id_pasajero"])
            if id_asignacion is None:
                continue
            evento["id_asignacion"] = id_asignacion
            if evento["tipo"] == "recogida":
                self.repositorio.marcar_recogida(id_asignacion, evento["espera_real_s"])
            elif evento["tipo"] == "finalizacion":
                self.repositorio.marcar_finalizacion(id_asignacion)
                self._asignacion_por_pasajero.pop(evento["id_pasajero"], None)
        if resumen.turno % 100 == 0:
            e = motor.obtener_estadisticas()
            self.repositorio.guardar_metrica("turno", "duracion_turno_promedio_ms", e["duracion_turno_promedio_ms"] or 0,
                                             "ms", {"conductores": e["conductores_totales"], "turno": resumen.turno})
        if resumen.turno % 500 == 0:
            self._guardar_resultado("periodico")

    def _guardar_resultado(self, motivo: str) -> None:
        if self.motor is not None:
            self.repositorio.guardar_resultado_simulacion(self.id_configuracion, motivo, self.motor.obtener_estadisticas())

    # ================================================================ solicitudes
    def _anexar_serializacion(self, resultado: ResultadoAsignacion) -> None:
        """Ejecutado dentro del cerrojo del motor, inmediatamente tras el despacho."""
        motor = self.motor
        if motor is None:
            return
        resultado.anexos["datos"] = serializar_resultado(resultado, motor.grafo)
        resultado.anexos["contexto"] = (
            contexto_conductores(motor.flota, resultado.pasajero.latitud_origen, resultado.pasajero.longitud_origen)
            if resultado.exito else []
        )

    def _registrar(self, resultado: ResultadoAsignacion, origen: str, motor: MotorSimulacion) -> dict[str, Any]:
        datos = resultado.anexos.get("datos") or serializar_resultado(resultado, motor.grafo)
        id_solicitud, id_asignacion = self.repositorio.registrar_resultado(
            datos, self.id_configuracion, motor.configuracion.id_distrito, origen,
            resultado.anexos.get("contexto", []), resultado.pasajero.turno_solicitud)
        datos["id_solicitud"], datos["id_asignacion"] = id_solicitud, id_asignacion
        if id_asignacion is not None:
            motor.vincular_asignacion(resultado.pasajero.id_pasajero, id_asignacion)
            self._asignacion_por_pasajero[resultado.pasajero.id_pasajero] = id_asignacion
            if len(self._asignacion_por_pasajero) > 20_000:
                for clave in list(self._asignacion_por_pasajero)[:5_000]:
                    del self._asignacion_por_pasajero[clave]
        if "total" in resultado.tiempos_ms:
            self.repositorio.guardar_metrica("despacho", "tiempo_total_despacho_ms", resultado.tiempos_ms["total"], "ms",
                                             {**resultado.tiempos_ms, "conductores": len(motor.flota)})
        return datos

    def _difundir_asignacion(self, resultado: ResultadoAsignacion) -> None:
        datos = resultado.anexos.get("datos")
        if datos is None:
            return
        self.tiempo_real.difundir_evento({"tipo": "asignacion" if resultado.exito else "solicitud_rechazada", "datos": datos})

    def _cotizar(self, motor: MotorSimulacion, *coordenadas: float) -> dict[str, Any]:
        with motor.cerrojo:  # serializa las rutas antes de que los conductores se muevan
            cotizacion = motor.despachador.cotizar(*coordenadas)
            return serializar_cotizacion(cotizacion, motor.grafo, motor.flota, motor.configuracion.velocidad_promedio_kmh)

    async def cotizar(self, latitud_origen: float, longitud_origen: float, latitud_destino: float,
                      longitud_destino: float) -> dict[str, Any]:
        """Conductores disponibles y candidatos con ETA real, sin asignar (el usuario elige después)."""
        motor = self.requerir_motor()
        datos = await asyncio.to_thread(self._cotizar, motor, latitud_origen, longitud_origen, latitud_destino, longitud_destino)
        datos["estado_simulacion"] = motor.estado.value
        datos["multiplicador_velocidad"] = motor.configuracion.multiplicador_velocidad
        return datos

    async def solicitar_servicio(self, latitud_origen: float, longitud_origen: float, latitud_destino: float,
                                 longitud_destino: float, direccion_origen: str = "", direccion_destino: str = "",
                                 id_conductor_preferido: Optional[int] = None) -> dict[str, Any]:
        motor = self.requerir_motor()
        resultado = await asyncio.to_thread(motor.solicitar_servicio, latitud_origen, longitud_origen,
                                            latitud_destino, longitud_destino, direccion_origen, direccion_destino,
                                            id_conductor_preferido)
        datos = await asyncio.to_thread(self._registrar, resultado, "manual", motor)
        self._difundir_asignacion(resultado)
        self.tiempo_real.difundir_evento({"tipo": "estadisticas", "datos": motor.obtener_estadisticas()})
        self.tiempo_real.notificar_turno()
        return datos

    # ================================================================ consultas
    def _calcular_delta_cliente(self, cliente: ClienteTiempoReal) -> Optional[dict[str, Any]]:
        motor = self.motor
        if motor is None or cliente.vista is None:
            return None
        with motor.cerrojo:
            entradas = motor.flota.indice.buscar_en_rectangulo(cliente.vista)
            conductores = [e.objeto for e in entradas]
            return GestorTiempoReal.calcular_delta(cliente, conductores, len(conductores), motor.turno,
                                                   self.tiempo_real.maximo_por_mensaje)

    def listar_conductores(self, limites: Optional[list[float]], estado: Optional[str], limite: int) -> dict[str, Any]:
        motor = self.requerir_motor()
        from estructuras.utilidades_geograficas import LimitesGeograficos

        with motor.cerrojo:
            if limites:
                oeste, sur, este, norte = limites
                conductores = motor.flota.conductores_en_area(LimitesGeograficos(sur, oeste, norte, este))
            else:
                conductores = list(motor.flota)
            if estado:
                conductores = [c for c in conductores if c.estado.value == estado]
            total = len(conductores)
            return {"total": total, "elementos": [c.obtener_informacion() for c in conductores[:limite]]}

    def obtener_conductor(self, id_conductor: int) -> dict[str, Any]:
        motor = self.requerir_motor()
        with motor.cerrojo:
            conductor = motor.flota.obtener_conductor(id_conductor)
            if conductor is None:
                raise ErrorServicio(f"Conductor {id_conductor} no existe", 404)
            datos = conductor.obtener_informacion()
            if conductor.en_ruta_de_servicio:
                restante = conductor.ruta_actual[conductor.indice_ruta + 1:]
                datos["ruta_restante"] = [[round(conductor.longitud, 6), round(conductor.latitud, 6)]] + \
                    coordenadas_lon_lat(motor.grafo, restante)
            return datos

    def servicios_activos(self, limite: int = 300) -> list[dict[str, Any]]:
        motor = self.requerir_motor()
        salida: list[dict[str, Any]] = []
        with motor.cerrojo:
            for servicio in list(motor.servicios.values())[-limite:]:
                conductor = motor.flota.obtener_conductor(servicio.id_conductor)
                pasajero = motor.despachador.pasajeros.get(servicio.id_pasajero)
                if conductor is None or pasajero is None:
                    continue
                restante = conductor.ruta_actual[conductor.indice_ruta + 1:]
                ruta = [[round(conductor.longitud, 6), round(conductor.latitud, 6)]] + coordenadas_lon_lat(motor.grafo, restante)
                salida.append({
                    "id_pasajero": pasajero.id_pasajero, "id_conductor": conductor.id_conductor,
                    "id_asignacion": servicio.id_asignacion, "estado_pasajero": pasajero.estado.value,
                    "estado_conductor": conductor.estado.value,
                    "fase": "recogida" if conductor.estado is EstadoConductor.OCUPADO else "viaje",
                    "origen": [pasajero.longitud_origen, pasajero.latitud_origen],
                    "destino": [pasajero.longitud_destino, pasajero.latitud_destino],
                    "ruta_restante": ruta,
                    "ruta_viaje": coordenadas_lon_lat(motor.grafo, servicio.ruta_viaje)
                    if conductor.estado is EstadoConductor.OCUPADO else [],
                })
        return salida

    def seguimiento(self, id_pasajero: int) -> dict[str, Any]:
        """Seguimiento en vivo de un viaje (pantalla «Solicitar servicio»)."""
        motor = self.requerir_motor()
        datos = motor.obtener_seguimiento(id_pasajero)
        if datos is None:
            raise ErrorServicio(f"El pasajero {id_pasajero} no pertenece a la simulación actual "
                                "(se reconfiguró o reinició)", 404)
        conductor = datos["conductor"]
        nodos_restantes = datos.pop("nodos_restantes")
        if datos["fase"] in ("recogida", "viaje") and conductor:
            posicion = [[round(conductor["longitud"], 6), round(conductor["latitud"], 6)]]
            datos["ruta_restante"] = posicion + coordenadas_lon_lat(motor.grafo, nodos_restantes)
        else:
            datos["ruta_restante"] = []
        datos["ruta_viaje"] = coordenadas_lon_lat(motor.grafo, datos.pop("nodos_viaje"))
        datos["id_configuracion"] = self.id_configuracion
        datos["id_asignacion"] = self._asignacion_por_pasajero.get(id_pasajero)
        return datos

    def estadisticas(self) -> dict[str, Any]:
        historico = self.repositorio.resumen_historico()
        if self.motor is None:
            return {"simulacion": None, "historico": historico}
        datos = self.motor.obtener_estadisticas()
        datos["nodos_quadtree"] = self.motor.flota.indice.contar_nodos()
        datos["mensajes_ws"] = self.tiempo_real.mensajes_enviados
        datos["clientes_ws"] = len(self.tiempo_real.clientes)
        return {"simulacion": datos, "historico": historico}

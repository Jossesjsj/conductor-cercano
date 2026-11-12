"""Acceso a datos persistentes (historial, configuraciones, métricas)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, insert, select, update

from backend.modelos.base_datos import BaseDatos
from backend.modelos.tablas import (
    Asignacion,
    ConductorRegistrado,
    ConfiguracionGuardada,
    MetricaRendimiento,
    ResultadoSimulacion,
    Solicitud,
)
from simulacion.flota import Flota

ESTADOS_EN_CURSO = ("CONDUCTOR_ASIGNADO", "VIAJANDO")


def iso(fecha: Optional[datetime]) -> Optional[str]:
    """SQLite no conserva la zona horaria: las fechas se guardan en UTC y se reetiquetan."""
    if fecha is None:
        return None
    return (fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)).isoformat()


class Repositorio:
    def __init__(self, base_datos: BaseDatos) -> None:
        self.bd = base_datos

    # ------------------------------------------------------------ arranque
    def marcar_servicios_interrumpidos(self) -> int:
        """Tras un reinicio del servidor la simulación en memoria se pierde: los servicios
        que estaban en curso se marcan explícitamente como INTERRUMPIDO."""
        with self.bd.sesion() as s:
            r = s.execute(update(Asignacion).where(Asignacion.estado_servicio.in_(ESTADOS_EN_CURSO))
                          .values(estado_servicio="INTERRUMPIDO"))
            return r.rowcount or 0

    # ------------------------------------------------------------ configuración
    def guardar_configuracion(self, datos: dict[str, Any], metadatos_grafo: Optional[dict[str, Any]]) -> int:
        with self.bd.sesion() as s:
            fila = ConfiguracionGuardada(
                id_distrito=datos["id_distrito"], semilla=datos["semilla"],
                cantidad_conductores=datos["cantidad_conductores"], datos=datos, metadatos_grafo=metadatos_grafo,
            )
            s.add(fila)
            s.flush()
            return fila.id

    def guardar_flota(self, id_configuracion: int, flota: Flota) -> None:
        filas = [{
            "id_configuracion": id_configuracion, "id_conductor": c.id_conductor, "nombre": c.nombre,
            "placa": c.vehiculo.placa, "marca": c.vehiculo.marca, "modelo": c.vehiculo.modelo,
            "color": c.vehiculo.color, "anio": c.vehiculo.anio, "velocidad_kmh": round(c.velocidad, 2),
            "nodo_inicial": c.nodo_actual, "latitud_inicial": c.latitud, "longitud_inicial": c.longitud,
            "estado_inicial": c.estado.value,
        } for c in flota]
        if filas:
            with self.bd.sesion() as s:
                s.execute(insert(ConductorRegistrado), filas)

    def ultima_configuracion(self) -> Optional[dict[str, Any]]:
        with self.bd.sesion() as s:
            # Solo las configuraciones creadas por la aplicación (no las de scripts como generar_mapas).
            filas = s.scalars(select(ConfiguracionGuardada).order_by(ConfiguracionGuardada.id.desc()).limit(50)).all()
            fila = next((f for f in filas if f.datos.get("origen", "aplicacion") == "aplicacion"), None)
            return None if fila is None else {"id": fila.id, "fecha": iso(fila.fecha), **fila.datos}

    def listar_configuraciones(self, limite: int = 20) -> list[dict[str, Any]]:
        with self.bd.sesion() as s:
            filas = s.scalars(select(ConfiguracionGuardada).order_by(ConfiguracionGuardada.id.desc()).limit(limite)).all()
            return [{"id": f.id, "fecha": iso(f.fecha), "datos": f.datos, "metadatos_grafo": f.metadatos_grafo} for f in filas]

    # ------------------------------------------------------------ solicitudes / asignaciones
    def registrar_resultado(
        self, datos: dict[str, Any], id_configuracion: Optional[int], id_distrito: str, origen: str,
        contexto: list[list[Any]], turno: int,
    ) -> tuple[int, Optional[int]]:
        p = datos["pasajero"]
        with self.bd.sesion() as s:
            solicitud = Solicitud(
                id_configuracion=id_configuracion, id_pasajero=p["id_pasajero"], id_distrito=id_distrito, origen=origen,
                latitud_origen=p["origen"]["latitud"], longitud_origen=p["origen"]["longitud"],
                latitud_destino=p["destino"]["latitud"], longitud_destino=p["destino"]["longitud"],
                direccion_origen=p["origen"]["direccion"][:300], direccion_destino=p["destino"]["direccion"][:300],
                nodo_origen=p["nodo_origen"], nodo_destino=p["nodo_destino"], estado=p["estado"],
                codigo_resultado=datos["codigo"], mensaje=datos["mensaje"],
            )
            s.add(solicitud)
            s.flush()
            id_asignacion = None
            if datos["exito"]:
                c = datos["conductor"]
                asignacion = Asignacion(
                    id_solicitud=solicitud.id, id_distrito=id_distrito, id_conductor=c["id_conductor"],
                    nombre_conductor=c["nombre"], placa=c["vehiculo"]["placa"], velocidad_kmh=c["velocidad_kmh"],
                    candidatos=datos["candidatos"], distancia_haversine_m=datos["distancia_haversine_m"],
                    distancia_ruta_m=datos["distancia_recogida_m"], eta_segundos=datos["eta_recogida_s"],
                    distancia_viaje_m=datos["distancia_viaje_m"], duracion_viaje_s=datos["duracion_viaje_s"],
                    ruta_recogida=datos["ruta_recogida"], ruta_viaje=datos["ruta_viaje"],
                    calles_recogida=datos["calles_recogida"], conductores_contexto=contexto,
                    justificacion=datos["justificacion"], radio_busqueda_m=datos["busqueda"]["radio_final_m"],
                    iteraciones_busqueda=datos["busqueda"]["iteraciones"],
                    elementos_examinados=datos["busqueda"]["elementos_examinados"], tiempos_ms=datos["tiempos_ms"],
                    turno_asignacion=turno,
                )
                s.add(asignacion)
                s.flush()
                id_asignacion = asignacion.id
            return solicitud.id, id_asignacion

    def marcar_recogida(self, id_asignacion: int, espera_real_s: float) -> None:
        with self.bd.sesion() as s:
            s.execute(update(Asignacion).where(Asignacion.id == id_asignacion).values(
                estado_servicio="VIAJANDO", fecha_recogida=datetime.now(timezone.utc), espera_real_s=espera_real_s))
            s.execute(update(Solicitud).where(Solicitud.asignacion.has(Asignacion.id == id_asignacion)).values(estado="VIAJANDO"))

    def marcar_finalizacion(self, id_asignacion: int) -> None:
        with self.bd.sesion() as s:
            s.execute(update(Asignacion).where(Asignacion.id == id_asignacion).values(
                estado_servicio="FINALIZADO", fecha_finalizacion=datetime.now(timezone.utc)))
            s.execute(update(Solicitud).where(Solicitud.asignacion.has(Asignacion.id == id_asignacion)).values(estado="FINALIZADO"))

    def cancelar_en_curso(self, id_configuracion: Optional[int]) -> None:
        """Al reiniciar/reconfigurar la simulación, los servicios en curso se cancelan."""
        with self.bd.sesion() as s:
            s.execute(update(Asignacion).where(Asignacion.estado_servicio.in_(ESTADOS_EN_CURSO)).values(estado_servicio="CANCELADO"))

    @staticmethod
    def _resumen_asignacion(a: Asignacion, sol: Solicitud) -> dict[str, Any]:
        return {
            "id_asignacion": a.id, "id_solicitud": sol.id, "id_pasajero": sol.id_pasajero,
            "fecha": iso(a.fecha), "id_distrito": a.id_distrito, "id_conductor": a.id_conductor,
            "nombre_conductor": a.nombre_conductor, "placa": a.placa, "candidatos_evaluados": len(a.candidatos),
            "distancia_haversine_m": a.distancia_haversine_m, "distancia_ruta_m": a.distancia_ruta_m,
            "eta_segundos": a.eta_segundos, "distancia_viaje_m": a.distancia_viaje_m,
            "estado_servicio": a.estado_servicio, "origen_solicitud": sol.origen,
            "direccion_origen": sol.direccion_origen, "direccion_destino": sol.direccion_destino,
        }

    def listar_asignaciones(self, pagina: int = 1, tamano: int = 25, id_distrito: Optional[str] = None,
                            estado: Optional[str] = None, origen: Optional[str] = None) -> dict[str, Any]:
        with self.bd.sesion() as s:
            consulta = select(Asignacion, Solicitud).join(Solicitud, Asignacion.id_solicitud == Solicitud.id)
            conteo = select(func.count(Asignacion.id)).join(Solicitud, Asignacion.id_solicitud == Solicitud.id)
            for condicion in (
                Asignacion.id_distrito == id_distrito if id_distrito else None,
                Asignacion.estado_servicio == estado if estado else None,
                Solicitud.origen == origen if origen else None,
            ):
                if condicion is not None:
                    consulta, conteo = consulta.where(condicion), conteo.where(condicion)
            total = s.scalar(conteo) or 0
            filas = s.execute(consulta.order_by(Asignacion.id.desc()).offset((pagina - 1) * tamano).limit(tamano)).all()
            return {"total": total, "pagina": pagina, "tamano": tamano,
                    "elementos": [self._resumen_asignacion(a, sol) for a, sol in filas]}

    def obtener_asignacion(self, id_asignacion: int) -> Optional[dict[str, Any]]:
        with self.bd.sesion() as s:
            fila = s.execute(select(Asignacion, Solicitud).join(Solicitud, Asignacion.id_solicitud == Solicitud.id)
                             .where(Asignacion.id == id_asignacion)).first()
            if fila is None:
                return None
            a, sol = fila
            detalle = self._resumen_asignacion(a, sol)
            detalle.update({
                "velocidad_kmh": a.velocidad_kmh, "candidatos": a.candidatos, "duracion_viaje_s": a.duracion_viaje_s,
                "ruta_recogida": a.ruta_recogida, "ruta_viaje": a.ruta_viaje, "calles_recogida": a.calles_recogida,
                "conductores_contexto": a.conductores_contexto, "justificacion": a.justificacion,
                "radio_busqueda_m": a.radio_busqueda_m, "iteraciones_busqueda": a.iteraciones_busqueda,
                "elementos_examinados": a.elementos_examinados, "tiempos_ms": a.tiempos_ms,
                "turno_asignacion": a.turno_asignacion, "espera_real_s": a.espera_real_s,
                "fecha_recogida": iso(a.fecha_recogida),
                "fecha_finalizacion": iso(a.fecha_finalizacion),
                "pasajero": {
                    "origen": [sol.longitud_origen, sol.latitud_origen], "destino": [sol.longitud_destino, sol.latitud_destino],
                    "nodo_origen": sol.nodo_origen, "nodo_destino": sol.nodo_destino, "estado": sol.estado,
                },
            })
            return detalle

    def listar_solicitudes_rechazadas(self, limite: int = 20) -> list[dict[str, Any]]:
        with self.bd.sesion() as s:
            filas = s.scalars(select(Solicitud).where(Solicitud.codigo_resultado != "ASIGNADO")
                              .order_by(Solicitud.id.desc()).limit(limite)).all()
            return [{"id_solicitud": f.id, "fecha": iso(f.fecha), "id_distrito": f.id_distrito,
                     "codigo": f.codigo_resultado, "mensaje": f.mensaje, "origen": f.origen} for f in filas]

    def resumen_historico(self) -> dict[str, Any]:
        with self.bd.sesion() as s:
            total_solicitudes = s.scalar(select(func.count(Solicitud.id))) or 0
            total_asignaciones = s.scalar(select(func.count(Asignacion.id))) or 0
            finalizadas = s.scalar(select(func.count(Asignacion.id)).where(Asignacion.estado_servicio == "FINALIZADO")) or 0
            eta = s.scalar(select(func.avg(Asignacion.eta_segundos)))
            distancia = s.scalar(select(func.avg(Asignacion.distancia_ruta_m)))
            por_distrito = s.execute(select(Asignacion.id_distrito, func.count(Asignacion.id))
                                     .group_by(Asignacion.id_distrito)).all()
            return {
                "solicitudes": total_solicitudes, "asignaciones": total_asignaciones, "finalizadas": finalizadas,
                "eta_promedio_s": round(eta, 1) if eta else None,
                "distancia_promedio_recogida_m": round(distancia, 1) if distancia else None,
                "por_distrito": {d: n for d, n in por_distrito},
            }

    # ------------------------------------------------------------ resultados y métricas
    def guardar_resultado_simulacion(self, id_configuracion: Optional[int], motivo: str, estadisticas: dict[str, Any]) -> None:
        with self.bd.sesion() as s:
            s.add(ResultadoSimulacion(id_configuracion=id_configuracion, motivo=motivo, turno=estadisticas.get("turno", 0),
                                      tiempo_simulado_s=estadisticas.get("tiempo_simulado_s", 0.0), estadisticas=estadisticas))

    def listar_resultados_simulacion(self, limite: int = 20) -> list[dict[str, Any]]:
        with self.bd.sesion() as s:
            filas = s.scalars(select(ResultadoSimulacion).order_by(ResultadoSimulacion.id.desc()).limit(limite)).all()
            return [{"id": f.id, "fecha": iso(f.fecha), "motivo": f.motivo, "turno": f.turno,
                     "id_configuracion": f.id_configuracion, "estadisticas": f.estadisticas} for f in filas]

    def guardar_metrica(self, tipo: str, nombre: str, valor: float, unidad: str, detalle: Optional[dict[str, Any]] = None) -> None:
        with self.bd.sesion() as s:
            s.add(MetricaRendimiento(tipo=tipo, nombre=nombre, valor=valor, unidad=unidad, detalle=detalle))

    def listar_metricas(self, tipo: Optional[str] = None, limite: int = 200) -> list[dict[str, Any]]:
        with self.bd.sesion() as s:
            consulta = select(MetricaRendimiento).order_by(MetricaRendimiento.id.desc()).limit(limite)
            if tipo:
                consulta = consulta.where(MetricaRendimiento.tipo == tipo)
            return [{"fecha": iso(m.fecha), "tipo": m.tipo, "nombre": m.nombre, "valor": m.valor,
                     "unidad": m.unidad, "detalle": m.detalle} for m in s.scalars(consulta).all()]

"""Conversión de resultados del dominio a estructuras JSON (API, BD, WebSocket, mapas)."""

from __future__ import annotations

import math
from typing import Any, Optional

from algoritmos.dijkstra import formatear_eta
from algoritmos.haversine import distancia_haversine_rapida
from estructuras.grafo_vial import GrafoVial
from estructuras.utilidades_geograficas import rectangulo_que_contiene_circulo
from simulacion.despachador import ResultadoAsignacion
from simulacion.flota import Flota


def _finito(valor: float, decimales: int = 1) -> Optional[float]:
    return None if valor is None or math.isinf(valor) or math.isnan(valor) else round(valor, decimales)


def coordenadas_lon_lat(grafo: GrafoVial, nodos: list[int], prefijo: Optional[tuple[float, float]] = None) -> list[list[float]]:
    puntos = grafo.coordenadas_de_ruta(nodos)
    salida = [[round(lon, 6), round(lat, 6)] for lat, lon in puntos]
    if prefijo is not None:
        salida.insert(0, [round(prefijo[1], 6), round(prefijo[0], 6)])
    return salida


def ruta_desde_conductor(grafo: GrafoVial, conductor, nodos_desde_siguiente: list[int]) -> list[list[float]]:
    """Polilínea desde la posición exacta del conductor (resto de su arista actual) y luego
    por los nodos calculados con Dijkstra (que comienzan en su nodo siguiente)."""
    u, v = conductor.ruta_actual[conductor.indice_ruta], conductor.ruta_actual[conductor.indice_ruta + 1]
    geometria = grafo.obtener_geometria(u, v)
    restante = [p for p, d in zip(geometria.puntos, geometria.acumuladas) if d > conductor.distancia_en_arista]
    inicio = [[round(conductor.longitud, 6), round(conductor.latitud, 6)]]
    inicio += [[round(lon, 6), round(lat, 6)] for lat, lon in restante[:-1]]
    return inicio + coordenadas_lon_lat(grafo, nodos_desde_siguiente)


def ruta_recogida_desde_conductor(grafo: GrafoVial, resultado: ResultadoAsignacion) -> list[list[float]]:
    if resultado.conductor is None:
        return []
    return ruta_desde_conductor(grafo, resultado.conductor, resultado.ruta_recogida_nodos)


def serializar_cotizacion(cotizacion, grafo: GrafoVial, flota: Flota, velocidad_media_kmh: float) -> dict[str, Any]:
    """Vista previa: disponibles, candidatos con su ruta de recogida y estimación del viaje."""
    candidatos = []
    for evaluacion in cotizacion.candidatos:
        datos = evaluacion.como_diccionario()
        datos["recomendado"] = datos.pop("seleccionado")
        conductor = flota.obtener_conductor(evaluacion.id_conductor)
        if conductor is not None:
            datos["vehiculo"] = conductor.obtener_informacion()["vehiculo"]
            datos["ruta_recogida"] = ruta_desde_conductor(grafo, conductor, evaluacion.nodos_ruta) if evaluacion.valido else []
        candidatos.append(datos)
    candidatos.sort(key=lambda c: (c["eta_segundos"] is None, c["eta_segundos"] or 0))
    return {
        "exito": cotizacion.exito,
        "codigo": cotizacion.codigo,
        "mensaje": cotizacion.mensaje,
        "nodo_origen": cotizacion.nodo_origen,
        "nodo_destino": cotizacion.nodo_destino,
        "disponibles_totales": cotizacion.disponibles_totales,
        "disponibles_cercanos": cotizacion.disponibles_cercanos,
        "radio_cercania_m": cotizacion.radio_cercania_m,
        "cercanos": [[i, round(lat, 6), round(lon, 6)] for i, lat, lon in cotizacion.cercanos],
        "candidatos": candidatos,
        "id_conductor_recomendado": cotizacion.id_conductor_recomendado,
        "ruta_viaje": coordenadas_lon_lat(grafo, cotizacion.nodos_viaje),
        "distancia_viaje_m": _finito(cotizacion.distancia_viaje_m),
        "duracion_viaje_estimada_s": _finito(cotizacion.distancia_viaje_m / (velocidad_media_kmh / 3.6)),
        "busqueda": {"radio_final_m": round(cotizacion.radio_busqueda_m, 1), "elementos_examinados": cotizacion.elementos_examinados},
        "tiempos_ms": cotizacion.tiempos_ms,
    }


def contexto_conductores(flota: Flota, latitud: float, longitud: float, radio_m: float = 1500.0, maximo: int = 400) -> list[list[Any]]:
    """Instantánea de conductores cercanos en el momento de la asignación (para mapas Folium)."""
    entradas = flota.indice.buscar_en_rectangulo(rectangulo_que_contiene_circulo(latitud, longitud, radio_m))
    cercanos = sorted(
        ((distancia_haversine_rapida(latitud, longitud, e.latitud, e.longitud), e.objeto) for e in entradas),
        key=lambda t: t[0],
    )[:maximo]
    return [[c.id_conductor, round(c.latitud, 6), round(c.longitud, 6), c.estado.value] for _, c in cercanos]


def serializar_resultado(resultado: ResultadoAsignacion, grafo: GrafoVial, id_asignacion: Optional[int] = None,
                         id_solicitud: Optional[int] = None) -> dict[str, Any]:
    p = resultado.pasajero
    datos: dict[str, Any] = {
        "exito": resultado.exito,
        "codigo": resultado.codigo,
        "mensaje": resultado.mensaje,
        "id_asignacion": id_asignacion,
        "id_solicitud": id_solicitud,
        "pasajero": p.obtener_informacion(),
        "candidatos": [c.como_diccionario() for c in resultado.candidatos],
        "busqueda": {
            "radio_final_m": round(resultado.radio_busqueda_m, 1),
            "iteraciones": resultado.iteraciones_busqueda,
            "elementos_examinados": resultado.elementos_examinados,
        },
        "tiempos_ms": resultado.tiempos_ms,
        "fecha": resultado.fecha.isoformat(),
    }
    if resultado.exito and resultado.conductor is not None:
        c = resultado.conductor
        datos.update({
            "conductor": c.obtener_informacion(),
            "distancia_haversine_m": _finito(resultado.distancia_haversine_m),
            "distancia_recogida_m": _finito(resultado.distancia_recogida_m),
            "eta_recogida_s": _finito(resultado.eta_recogida_s),
            "eta_recogida_texto": formatear_eta(resultado.eta_recogida_s),
            "distancia_viaje_m": _finito(resultado.distancia_viaje_m),
            "duracion_viaje_s": _finito(resultado.duracion_viaje_s),
            "duracion_viaje_texto": formatear_eta(resultado.duracion_viaje_s),
            "ruta_recogida": ruta_recogida_desde_conductor(grafo, resultado),
            "ruta_viaje": coordenadas_lon_lat(grafo, resultado.ruta_viaje_nodos),
            "calles_recogida": grafo.nombres_de_ruta(resultado.ruta_recogida_nodos),
            "calles_viaje": grafo.nombres_de_ruta(resultado.ruta_viaje_nodos),
            "justificacion": resultado.justificacion,
            "id_conductor_recomendado": resultado.id_conductor_recomendado,
            "eleccion_usuario": resultado.eleccion_usuario,
            "aviso": resultado.aviso,
        })
    return datos

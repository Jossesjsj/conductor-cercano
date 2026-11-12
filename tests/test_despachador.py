"""Pruebas del Despachador (asignación por menor ETA y casos sin servicio)."""

from __future__ import annotations

import threading

from estructuras.grafo_vial import crear_grafo_cuadricula
from simulacion.conductor import EstadoConductor
from simulacion.despachador import CodigoResultado, Despachador, ParametrosDespacho
from simulacion.flota import Flota, ParametrosFlota
from simulacion.pasajero import EstadoPasajero
from tests.conftest import agregar, crear_conductor, crear_flota_vacia, crear_grafo, desplazar


def test_asigna_conductor_con_menor_eta_no_el_mas_cercano(grafo_sentido_unico):
    grafo = grafo_sentido_unico
    flota = crear_flota_vacia(grafo)
    cercano = crear_conductor(grafo, 1, 1, 3, desplazamiento_m=30)  # ~70 m del pasajero, se aleja (sentido único)
    lejano = crear_conductor(grafo, 2, 6, 0, desplazamiento_m=50)  # 250 m, ruta directa
    agregar(flota, cercano)
    agregar(flota, lejano)
    despachador = Despachador(grafo, flota, ParametrosDespacho(cantidad_candidatos=5))
    lat_p, lon_p = desplazar(0, 0)
    lat_d, lon_d = desplazar(-300, 0)
    resultado = despachador.procesar_solicitud(lat_p, lon_p, lat_d, lon_d)

    assert resultado.exito and resultado.codigo == CodigoResultado.ASIGNADO
    por_id = {c.id_conductor: c for c in resultado.candidatos}
    assert por_id[1].distancia_haversine_m < por_id[2].distancia_haversine_m
    assert por_id[1].distancia_ruta_m > por_id[2].distancia_ruta_m  # rodeo por el sentido único
    assert resultado.conductor.id_conductor == 2
    assert resultado.eta_recogida_s == min(c.eta_segundos for c in resultado.candidatos)
    assert lejano.estado is EstadoConductor.OCUPADO and cercano.estado is EstadoConductor.DISPONIBLE
    assert resultado.pasajero.estado is EstadoPasajero.CONDUCTOR_ASIGNADO
    assert "menor ETA" in resultado.justificacion
    # Ruta del viaje calculada tras la asignación.
    assert resultado.ruta_viaje_nodos[0] == resultado.pasajero.nodo_origen


def test_conductores_sin_disponibilidad_son_excluidos(grafo_sentido_unico):
    grafo = grafo_sentido_unico
    flota = crear_flota_vacia(grafo)
    agregar(flota, crear_conductor(grafo, 1, 6, 0, 280, estado=EstadoConductor.INACTIVO))  # el más cercano
    agregar(flota, crear_conductor(grafo, 2, 6, 0, 250, estado=EstadoConductor.OCUPADO))
    agregar(flota, crear_conductor(grafo, 3, 0, 6, 200))  # disponible, más lejano
    despachador = Despachador(grafo, flota)
    resultado = despachador.procesar_solicitud(*desplazar(0, 0), *desplazar(400, 400))
    assert [c.id_conductor for c in resultado.candidatos] == [3]
    assert resultado.conductor.id_conductor == 3


def test_pasajero_sin_conductores_disponibles(grafo_sentido_unico):
    grafo = grafo_sentido_unico
    flota = crear_flota_vacia(grafo)
    agregar(flota, crear_conductor(grafo, 1, 6, 0, 100, estado=EstadoConductor.INACTIVO))
    resultado = Despachador(grafo, flota).procesar_solicitud(*desplazar(0, 0), *desplazar(400, 400))
    assert not resultado.exito
    assert resultado.codigo == CodigoResultado.SIN_CONDUCTORES_DISPONIBLES
    assert resultado.pasajero.estado is EstadoPasajero.CANCELADO


def test_pasajero_en_zona_sin_conexion_vial(grafo_sentido_unico):
    grafo = grafo_sentido_unico
    flota = crear_flota_vacia(grafo)
    agregar(flota, crear_conductor(grafo, 1, 6, 0, 100))
    despachador = Despachador(grafo, flota, ParametrosDespacho(distancia_maxima_ajuste_metros=300))
    lejos = desplazar(150, 1500)  # 1.1 km de la calle más cercana (zona sin red vial)
    resultado = despachador.procesar_solicitud(*lejos, *desplazar(0, 0))
    assert not resultado.exito
    assert resultado.codigo == CodigoResultado.ORIGEN_SIN_CONEXION_VIAL
    assert "no existe una ruta válida" in resultado.mensaje
    assert flota.obtener_conductor(1).estado is EstadoConductor.DISPONIBLE


def test_candidato_sin_ruta_se_descarta_sin_detener_la_operacion():
    # Isla 10↔11 desconectada de la red principal 0↔1↔2.
    grafo = crear_grafo({0: (0, 0), 1: (200, 0), 2: (400, 0), 10: (0, 60), 11: (100, 60)},
                        [(0, 1), (1, 0), (1, 2), (2, 1), (10, 11), (11, 10)])
    flota = crear_flota_vacia(grafo)
    agregar(flota, crear_conductor(grafo, 1, 10, 11, 10))  # en la isla: muy cerca, pero sin ruta
    agregar(flota, crear_conductor(grafo, 2, 2, 1, 50))
    resultado = Despachador(grafo, flota).procesar_solicitud(*desplazar(0, 0), *desplazar(400, 0))
    por_id = {c.id_conductor: c for c in resultado.candidatos}
    assert not por_id[1].valido and "Sin ruta" in por_id[1].motivo
    assert resultado.exito and resultado.conductor.id_conductor == 2


def test_asignacion_concurrente_no_duplica_conductores():
    grafo = crear_grafo_cuadricula(15, 15)
    flota = Flota(grafo, ParametrosFlota(cantidad_conductores=40, proporcion_inactivos=0))
    import random

    flota.generar_flota(random.Random(3))
    despachador = Despachador(grafo, flota)
    lat, lon = grafo.coordenadas(112)
    resultados = []
    barrera = threading.Barrier(30)

    def solicitar():
        barrera.wait()
        resultados.append(despachador.procesar_solicitud(lat, lon, *grafo.coordenadas(0)))

    hilos = [threading.Thread(target=solicitar) for _ in range(30)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    asignados = [r.conductor.id_conductor for r in resultados if r.exito]
    assert len(asignados) == 30
    assert len(set(asignados)) == len(asignados)  # nunca el mismo conductor dos veces


def test_cotizar_cuenta_todos_los_disponibles_cercanos_sin_tope():
    """El conteo de disponibles cercanos es exacto aunque supere el máximo que se dibuja."""
    import random

    from algoritmos.haversine import calcular_haversine

    grafo = crear_grafo_cuadricula(12, 12, separacion_metros=60)
    flota = Flota(grafo, ParametrosFlota(cantidad_conductores=600, proporcion_inactivos=0))
    flota.generar_flota(random.Random(5))
    despachador = Despachador(grafo, flota)
    lat, lon = grafo.coordenadas(78)
    destino = grafo.coordenadas(0)
    cot = despachador.cotizar(lat, lon, *destino, radio_cercania_m=300, maximo_cercanos=50)
    esperado = sum(1 for c in flota if c.estado is EstadoConductor.DISPONIBLE
                   and calcular_haversine(lat, lon, c.latitud, c.longitud) <= 300)
    assert esperado > 50 and cot.disponibles_cercanos == esperado and len(cot.cercanos) == 50
    assert all(c.estado is EstadoConductor.DISPONIBLE for c in flota)  # cotizar no cambia estados

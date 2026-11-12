"""Pruebas del motor de simulación: movimiento sobre la red, Quadtree y reproducibilidad."""

from __future__ import annotations

from algoritmos.haversine import calcular_haversine
from estructuras.grafo_vial import crear_grafo_cuadricula
from simulacion.conductor import EstadoConductor
from simulacion.motor_simulacion import ConfiguracionSimulacion, ModoSimulacion, MotorSimulacion
from simulacion.pasajero import EstadoPasajero


def crear_motor(semilla: int = 42, conductores: int = 200, modo=ModoSimulacion.AUTOMATICO) -> MotorSimulacion:
    grafo = crear_grafo_cuadricula(20, 20, separacion_metros=120)
    return MotorSimulacion(grafo, ConfiguracionSimulacion(
        id_distrito="prueba", cantidad_conductores=conductores, semilla=semilla, solicitudes_por_minuto=40, modo=modo,
        multiplicador_velocidad=4.0))  # 2 s simulados por turno: pruebas rápidas


def test_quadtree_se_actualiza_durante_los_movimientos():
    motor = crear_motor()
    antes = {c.id_conductor: (c.latitud, c.longitud) for c in motor.flota}
    motor.ejecutar_turnos(60)
    indice = motor.flota.indice
    indice.validar_consistencia()
    movidos = 0
    for c in motor.flota:
        entrada = indice.obtener_entrada(c.id_conductor)
        assert (entrada.latitud, entrada.longitud) == (c.latitud, c.longitud)
        movidos += (c.latitud, c.longitud) != antes[c.id_conductor]
    activos = sum(1 for c in motor.flota if c.estado is not EstadoConductor.INACTIVO)
    assert movidos == activos
    # La búsqueda por rectángulo refleja las posiciones nuevas.
    c = next(iter(motor.flota))
    from estructuras.utilidades_geograficas import rectangulo_que_contiene_circulo

    cercanos = indice.buscar_en_rectangulo(rectangulo_que_contiene_circulo(c.latitud, c.longitud, 1))
    assert c.id_conductor in {e.identificador for e in cercanos}


def test_conductores_solo_circulan_por_aristas_validas_sin_giro_en_u():
    motor = crear_motor(modo=ModoSimulacion.MANUAL)
    grafo = motor.grafo
    previos = {c.id_conductor: list(c.ruta_actual) for c in motor.flota}
    for _ in range(120):
        motor.ejecutar_turno()
        for c in motor.flota:
            u, v = c.ruta_actual[c.indice_ruta], c.ruta_actual[c.indice_ruta + 1]
            assert (u, v) in grafo.geometrias  # arista dirigida existente
            geometria = grafo.obtener_geometria(u, v)
            lat, lon, _ = geometria.interpolar(c.distancia_en_arista)
            assert calcular_haversine(lat, lon, c.latitud, c.longitud) < 0.01  # está SOBRE la calle
            anterior = previos[c.id_conductor]
            if anterior != c.ruta_actual and len(anterior) == 2 and len(c.ruta_actual) == 2 and anterior[1] == u:
                # La cuadrícula no tiene calles ciegas: nunca debe volver por donde vino.
                assert v != anterior[0]
            previos[c.id_conductor] = list(c.ruta_actual)


def test_reproducibilidad_de_la_semilla():
    a, b, c = crear_motor(semilla=7), crear_motor(semilla=7), crear_motor(semilla=8)
    assert a.obtener_huella_estado() == b.obtener_huella_estado()
    assert a.obtener_huella_estado() != c.obtener_huella_estado()
    a.ejecutar_turnos(150)
    b.ejecutar_turnos(150)
    assert a.obtener_huella_estado() == b.obtener_huella_estado()
    assert a.estadisticas["solicitudes_totales"] == b.estadisticas["solicitudes_totales"] > 0
    # Reiniciar devuelve exactamente la distribución inicial.
    inicial = crear_motor(semilla=7).obtener_huella_estado()
    a.reiniciar()
    assert a.obtener_huella_estado() == inicial


def test_ciclo_completo_de_servicio():
    motor = crear_motor(modo=ModoSimulacion.MANUAL, conductores=30)
    lat_o, lon_o = motor.grafo.coordenadas(21)
    lat_d, lon_d = motor.grafo.coordenadas(378)
    resultado = motor.solicitar_servicio(lat_o, lon_o, lat_d, lon_d)
    assert resultado.exito
    pasajero, conductor = resultado.pasajero, resultado.conductor
    assert conductor.estado is EstadoConductor.OCUPADO
    vistos = set()
    for _ in range(2000):
        resumen, _ = motor.ejecutar_turno()
        vistos |= {e["tipo"] for e in resumen.eventos}
        if pasajero.estado is EstadoPasajero.FINALIZADO:
            break
    assert {"recogida", "finalizacion"} <= vistos
    assert pasajero.estado is EstadoPasajero.FINALIZADO
    assert conductor.estado is EstadoConductor.DISPONIBLE and conductor.servicios_completados == 1
    assert motor.estadisticas["viajes_completados"] == 1
    # Llegó al nodo de destino.
    assert calcular_haversine(conductor.latitud, conductor.longitud, lat_d, lon_d) < 200


def test_modo_automatico_miles_de_movimientos_sin_intervencion():
    motor = crear_motor(conductores=300)
    motor.ejecutar_turnos(400)  # 400 turnos × ~290 conductores ≈ 116 000 movimientos
    e = motor.obtener_estadisticas()
    assert e["actualizaciones_quadtree"] > 100_000
    assert e["asignaciones_completadas"] > 0
    motor.flota.indice.validar_consistencia()


def test_seguimiento_del_viaje_fases_y_distancia_restante():
    """El pasajero ve al conductor acercarse, subir y llegar: fases en orden y distancia decreciente."""
    motor = crear_motor(modo=ModoSimulacion.MANUAL, conductores=30)
    resultado = motor.solicitar_servicio(*motor.grafo.coordenadas(42), *motor.grafo.coordenadas(357))
    assert resultado.exito
    id_pasajero = resultado.pasajero.id_pasajero
    inicial = motor.obtener_seguimiento(id_pasajero)
    assert inicial["fase"] == "recogida" and inicial["conductor"]["id_conductor"] == resultado.conductor.id_conductor
    assert inicial["distancia_restante_m"] > 0 and inicial["eta_restante_s"] > 0
    assert inicial["distancia_restante_m"] == __import__("pytest").approx(resultado.distancia_recogida_m, abs=0.5)
    fases, anterior = [inicial["fase"]], (inicial["fase"], inicial["distancia_restante_m"])
    for _ in range(3000):
        motor.ejecutar_turno()
        s = motor.obtener_seguimiento(id_pasajero)
        if s["fase"] == anterior[0] and s["fase"] in ("recogida", "viaje"):
            assert s["distancia_restante_m"] <= anterior[1] + 1e-6  # siempre se acerca
        if s["fase"] != fases[-1]:
            fases.append(s["fase"])
        anterior = (s["fase"], s["distancia_restante_m"])
        if s["fase"] == "finalizado":
            break
    assert fases == ["recogida", "viaje", "finalizado"]
    final = motor.obtener_seguimiento(id_pasajero)
    assert final["espera_real_s"] > 0 and final["duracion_viaje_s"] > 0
    assert motor.obtener_seguimiento(999_999) is None

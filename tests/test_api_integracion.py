"""Pruebas de integración del backend (FastAPI + SQLite + WebSocket) con un grafo sintético."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend.configuracion.ajustes import Ajustes
from backend.main import construir_contenedor, crear_aplicacion
from backend.servicios.catalogo_distritos import Distrito
from estructuras.grafo_vial import crear_grafo_cuadricula


@pytest.fixture
def cliente(tmp_path):
    ajustes = Ajustes(directorio_datos=tmp_path, precargar_distrito=False, directorio_frontend=tmp_path / "sin_front")
    ajustes.asegurar_directorios()
    contenedor = construir_contenedor(ajustes)
    grafo = crear_grafo_cuadricula(25, 25, separacion_metros=100)
    oeste, sur, este, norte = grafo.limites.como_lista()
    distrito = Distrito("cuadricula", "Cuadrícula", "Prueba", 0, 6.0, [oeste, sur, este, norte],
                        [(oeste + este) / 2, (sur + norte) / 2], True, box(oeste, sur, este, norte))
    contenedor.catalogo._distritos = {"cuadricula": distrito}
    contenedor.gestor_grafos.esta_descargado = lambda _id: True
    contenedor.gestor_grafos.cargar_grafo = lambda _id: grafo
    contenedor.gestor_grafos.leer_metadatos = lambda _id: {"fuente": "sintetica"}
    app = crear_aplicacion(ajustes, contenedor)
    with TestClient(app) as c:
        c.grafo = grafo
        yield c


def configurar(cliente, **extra):
    datos = {"id_distrito": "cuadricula", "cantidad_conductores": 150, "semilla": 3, "modo": "MANUAL", **extra}
    r = cliente.post("/api/simulacion/configurar", json=datos)
    assert r.status_code == 200, r.text
    return r.json()


def test_salud_y_simulacion_no_configurada(cliente):
    assert cliente.get("/api/salud").json()["estado"] == "ok"
    assert cliente.get("/api/simulacion").json()["configurada"] is False
    assert cliente.post("/api/solicitudes", json={"origen": {"latitud": -12.1, "longitud": -77.0},
                                                  "destino": {"latitud": -12.1, "longitud": -77.0}}).status_code == 409


def test_configuracion_invalida(cliente):
    r = cliente.post("/api/simulacion/configurar", json={"id_distrito": "cuadricula", "cantidad_conductores": -5})
    assert r.status_code == 422
    r = cliente.post("/api/simulacion/configurar", json={"id_distrito": "no-existe"})
    assert r.status_code == 404


def test_flujo_solicitud_asignacion_historial_y_mapa(cliente):
    estado = configurar(cliente)
    assert estado["configurada"] and estado["quadtree"]["elementos"] == 150
    lat_o, lon_o = cliente.grafo.coordenadas(312)
    lat_d, lon_d = cliente.grafo.coordenadas(20)
    r = cliente.post("/api/solicitudes", json={"origen": {"latitud": lat_o, "longitud": lon_o, "direccion": "Origen"},
                                               "destino": {"latitud": lat_d, "longitud": lon_d}})
    datos = r.json()
    assert r.status_code == 200 and datos["exito"], datos
    assert len(datos["candidatos"]) == 5
    assert sum(c["seleccionado"] for c in datos["candidatos"]) == 1
    seleccionado = next(c for c in datos["candidatos"] if c["seleccionado"])
    assert seleccionado["eta_segundos"] == min(c["eta_segundos"] for c in datos["candidatos"] if c["valido"])
    assert len(datos["ruta_recogida"]) >= 2 and len(datos["ruta_viaje"]) >= 2

    historial = cliente.get("/api/asignaciones").json()
    assert historial["total"] == 1
    detalle = cliente.get(f"/api/asignaciones/{datos['id_asignacion']}").json()
    assert detalle["id_conductor"] == datos["conductor"]["id_conductor"]
    assert detalle["direccion_origen"] == "Origen" and len(detalle["candidatos"]) == 5
    mapa = cliente.get(f"/api/asignaciones/{datos['id_asignacion']}/mapa")
    assert mapa.status_code == 200 and "leaflet" in mapa.text.lower()

    conductor = cliente.get(f"/api/conductores/{datos['conductor']['id_conductor']}").json()
    assert conductor["estado"] == "OCUPADO" and "ruta_restante" in conductor


def test_solicitud_sin_conexion_vial(cliente):
    configurar(cliente)
    r = cliente.post("/api/solicitudes", json={"origen": {"latitud": -11.5, "longitud": -77.5},
                                               "destino": {"latitud": -12.1, "longitud": -77.0}})
    datos = r.json()
    assert r.status_code == 200 and not datos["exito"]
    assert datos["codigo"] == "ORIGEN_SIN_CONEXION_VIAL"
    assert cliente.get("/api/solicitudes/rechazadas").json()[0]["codigo"] == "ORIGEN_SIN_CONEXION_VIAL"


def test_control_manual_de_turnos_y_estadisticas(cliente):
    configurar(cliente)
    for _ in range(3):
        assert cliente.post("/api/simulacion/avanzar").status_code == 200
    estado = cliente.get("/api/simulacion").json()
    assert estado["turno"] == 3
    assert cliente.post("/api/simulacion/acelerar").json()["configuracion"]["multiplicador_velocidad"] == 2.0
    assert cliente.post("/api/simulacion/desacelerar").json()["configuracion"]["multiplicador_velocidad"] == 1.0
    cliente.post("/api/simulacion/iniciar")
    assert cliente.post("/api/simulacion/avanzar").status_code == 409  # no se avanza manualmente en ejecución
    cliente.post("/api/simulacion/pausar")
    assert cliente.get("/api/simulacion").json()["estado"] == "PAUSADA"
    assert cliente.post("/api/simulacion/reiniciar").json()["turno"] == 0
    e = cliente.get("/api/estadisticas").json()["simulacion"]
    assert e["conductores_totales"] == 150
    assert e["conductores_disponibles"] + e["conductores_ocupados"] + e["conductores_inactivos"] == 150
    assert cliente.get("/api/simulacion/resultados").json()  # resultados persistidos al pausar


def test_websocket_envia_deltas_incrementales(cliente):
    configurar(cliente)
    oeste, sur, este, norte = cliente.grafo.limites.como_lista()
    with cliente.websocket_connect("/ws/tiempo-real") as ws:
        assert ws.receive_json()["tipo"] == "bienvenida"
        ws.send_json({"tipo": "vista", "limites": [oeste, sur, este, norte], "zoom": 15, "intervalo_minimo_ms": 50})
        primero = ws.receive_json()
        assert primero["tipo"] == "posiciones" and len(primero["actualizados"]) == primero["total_en_vista"] == 150
        cliente.post("/api/simulacion/avanzar")
        tipos, posiciones = set(), None
        for _ in range(10):
            mensaje = ws.receive_json()
            tipos.add(mensaje["tipo"])
            if mensaje["tipo"] == "posiciones":
                posiciones = mensaje
                break
        assert "estadisticas" in tipos and posiciones is not None
        # Solo se envían los que se movieron (los inactivos no aparecen de nuevo).
        assert 0 < len(posiciones["actualizados"]) < 150


def test_seguimiento_del_viaje_por_api(cliente):
    configurar(cliente, multiplicador_velocidad=8)
    lat_o, lon_o = cliente.grafo.coordenadas(312)
    lat_d, lon_d = cliente.grafo.coordenadas(20)
    datos = cliente.post("/api/solicitudes", json={"origen": {"latitud": lat_o, "longitud": lon_o},
                                                   "destino": {"latitud": lat_d, "longitud": lon_d}}).json()
    id_pasajero = datos["pasajero"]["id_pasajero"]
    s = cliente.get(f"/api/seguimiento/{id_pasajero}").json()
    assert s["fase"] == "recogida" and s["id_asignacion"] == datos["id_asignacion"]
    assert len(s["ruta_restante"]) >= 1 and len(s["ruta_viaje"]) >= 2
    for _ in range(400):
        cliente.post("/api/simulacion/avanzar")
        s = cliente.get(f"/api/seguimiento/{id_pasajero}").json()
        if s["fase"] == "finalizado":
            break
    assert s["fase"] == "finalizado" and s["duracion_viaje_s"] > 0
    detalle = cliente.get(f"/api/asignaciones/{datos['id_asignacion']}").json()
    assert detalle["estado_servicio"] == "FINALIZADO"
    assert cliente.get("/api/seguimiento/987654").status_code == 404


def test_ultima_configuracion_ignora_las_de_scripts(cliente):
    configurar(cliente)
    repositorio = cliente.app.state.contenedor.repositorio
    repositorio.guardar_configuracion({"id_distrito": "otro", "semilla": 1, "cantidad_conductores": 10, "origen": "script"}, None)
    assert repositorio.ultima_configuracion()["id_distrito"] == "cuadricula"


def test_cotizar_y_elegir_conductor(cliente):
    """Primero se ven los disponibles y candidatos (sin asignar); luego el pasajero confirma uno."""
    configurar(cliente)
    lat_o, lon_o = cliente.grafo.coordenadas(312)
    lat_d, lon_d = cliente.grafo.coordenadas(20)
    puntos = {"origen": {"latitud": lat_o, "longitud": lon_o}, "destino": {"latitud": lat_d, "longitud": lon_d}}
    antes = cliente.get("/api/estadisticas").json()["simulacion"]
    cot = cliente.post("/api/solicitudes/cotizar", json=puntos).json()
    assert cot["exito"] and cot["disponibles_totales"] == antes["conductores_disponibles"]
    assert len(cot["candidatos"]) == 5 and cot["disponibles_cercanos"] >= 1
    recomendado = [c for c in cot["candidatos"] if c["recomendado"]]
    assert len(recomendado) == 1 and recomendado[0]["id_conductor"] == cot["id_conductor_recomendado"]
    assert recomendado[0]["eta_segundos"] == min(c["eta_segundos"] for c in cot["candidatos"] if c["valido"])
    assert all(len(c["ruta_recogida"]) >= 1 for c in cot["candidatos"] if c["valido"]) and len(cot["ruta_viaje"]) >= 2
    despues = cliente.get("/api/estadisticas").json()["simulacion"]
    assert despues["solicitudes_realizadas"] == antes["solicitudes_realizadas"]  # cotizar no asigna nada
    assert despues["conductores_disponibles"] == antes["conductores_disponibles"]

    otro = next(c for c in cot["candidatos"] if c["valido"] and not c["recomendado"])
    r = cliente.post("/api/solicitudes", json={**puntos, "id_conductor": otro["id_conductor"]}).json()
    assert r["exito"] and r["conductor"]["id_conductor"] == otro["id_conductor"]
    assert r["eleccion_usuario"] and r["id_conductor_recomendado"] == cot["id_conductor_recomendado"]
    assert "Elegido por el pasajero" in r["justificacion"]

    # El mismo conductor ya está ocupado: la siguiente solicitud recibe el mejor disponible con aviso.
    r2 = cliente.post("/api/solicitudes", json={**puntos, "id_conductor": otro["id_conductor"]}).json()
    assert r2["exito"] and r2["conductor"]["id_conductor"] != otro["id_conductor"] and "ya no está disponible" in r2["aviso"]


def test_velocidad_x1_equivale_a_tiempo_real(cliente):
    estado = configurar(cliente, intervalo_actualizacion_s=0.5, multiplicador_velocidad=1)
    assert estado["segundos_por_turno"] == 0.5
    cliente.post("/api/simulacion/avanzar")
    assert cliente.get("/api/simulacion").json()["tiempo_simulado_s"] == 0.5
    assert cliente.patch("/api/simulacion/parametros", json={"multiplicador_velocidad": 4}).json()["segundos_por_turno"] == 2.0

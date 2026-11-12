"""Genera mapas HTML (Folium) de asignaciones REALES calculadas por el backend.

Para cada distrito: crea la simulación con semilla fija, ejecuta turnos para que haya
conductores ocupados, despacha una solicitud con el mismo Despachador que usa la API,
la persiste en SQLite (origen = "script") y dibuja el mapa a partir de lo almacenado.

Uso:  python -m mapas.generar_mapas
"""

from __future__ import annotations

from pathlib import Path

from backend.configuracion.ajustes import obtener_ajustes
from backend.modelos.base_datos import BaseDatos
from backend.servicios.catalogo_distritos import CatalogoDistritos
from backend.servicios.gestor_grafos import GestorGrafos
from backend.servicios.mapas_folium import generar_mapa_asignacion
from backend.servicios.repositorio import Repositorio
from backend.servicios.serializacion import contexto_conductores, serializar_resultado
from simulacion.motor_simulacion import ConfiguracionSimulacion, ModoSimulacion, MotorSimulacion

DIRECTORIO = Path(__file__).resolve().parent

# (distrito, conductores, origen, destino, descripción) — coordenadas de lugares reales.
ESCENARIOS = [
    ("miraflores", 1500, (-12.1219, -77.0300), (-12.1336, -77.0228), "Parque Kennedy → Larcomar"),
    ("san-isidro", 1200, (-12.0973, -77.0365), (-12.0915, -77.0499), "Centro empresarial → Av. Javier Prado Oeste"),
    ("santiago-de-surco", 2500, (-12.1450, -76.9930), (-12.1080, -76.9700), "Av. Benavides → Jockey Plaza"),
]


def main() -> None:
    ajustes = obtener_ajustes()
    catalogo = CatalogoDistritos(ajustes)
    gestor = GestorGrafos(ajustes, catalogo)
    repositorio = Repositorio(BaseDatos(ajustes.url_sqlalchemy))
    for numero, (id_distrito, cantidad, origen, destino, descripcion) in enumerate(ESCENARIOS, start=1):
        if not gestor.esta_descargado(id_distrito):
            print(f"Descargando {id_distrito}…")
            gestor.descargar_y_guardar(catalogo.obtener(id_distrito))
        grafo = gestor.cargar_grafo(id_distrito)
        configuracion = ConfiguracionSimulacion(id_distrito=id_distrito, cantidad_conductores=cantidad, semilla=42 + numero,
                                                modo=ModoSimulacion.AUTOMATICO, solicitudes_por_minuto=120,
                                                multiplicador_velocidad=4.0)
        motor = MotorSimulacion(grafo, configuracion)
        motor.ejecutar_turnos(40)  # genera conductores en recogida y en servicio
        # origen="script": no se usa como «última configuración» al reiniciar el servidor.
        id_configuracion = repositorio.guardar_configuracion({**configuracion.como_diccionario(), "origen": "script"},
                                                             gestor.leer_metadatos(id_distrito))

        resultado = motor.solicitar_servicio(*origen, *destino, descripcion.split(" → ")[0], descripcion.split(" → ")[1])
        if not resultado.exito:
            print(f"{id_distrito}: la solicitud no pudo asignarse ({resultado.mensaje})")
            continue
        datos = serializar_resultado(resultado, grafo)
        contexto = contexto_conductores(motor.flota, origen[0], origen[1], radio_m=1800, maximo=600)
        _, id_asignacion = repositorio.registrar_resultado(datos, id_configuracion, id_distrito, "script", contexto, motor.turno)
        detalle = repositorio.obtener_asignacion(id_asignacion)
        ruta = DIRECTORIO / f"mapa_{numero}_{id_distrito}.html"
        generar_mapa_asignacion(detalle, catalogo.geojson_distrito(id_distrito), ruta)
        estados = {}
        for _, _, _, estado in contexto:
            estados[estado] = estados.get(estado, 0) + 1
        print(f"{ruta.name}: asignación #{id_asignacion}, conductor {detalle['id_conductor']}, "
              f"ETA {detalle['eta_segundos']:.0f} s, {detalle['distancia_ruta_m']:.0f} m por calles; contexto {estados}")


if __name__ == "__main__":
    main()

"""Mapas HTML (Folium) de asignaciones reales registradas por el backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

COLORES_ESTADO = {
    "DISPONIBLE": "#22c55e",
    "OCUPADO": "#f59e0b",
    "EN_SERVICIO": "#ef4444",
    "INACTIVO": "#64748b",
}


def generar_mapa_asignacion(asignacion: dict[str, Any], limite_distrito: Optional[dict[str, Any]] = None,
                            ruta_salida: Optional[Path] = None) -> str:
    """Construye el mapa: pasajero, conductores disponibles/ocupados, 5 candidatos,
    conductor seleccionado, ruta de recogida y ruta del viaje. Devuelve el HTML."""
    import folium
    from folium.plugins import MiniMap

    origen_lon, origen_lat = asignacion["pasajero"]["origen"]
    destino_lon, destino_lat = asignacion["pasajero"]["destino"]
    mapa = folium.Map(location=[origen_lat, origen_lon], zoom_start=15, tiles="OpenStreetMap", control_scale=True)

    if limite_distrito:
        folium.GeoJson(limite_distrito, name="Límite del distrito",
                       style_function=lambda _: {"color": "#2563eb", "weight": 2, "fillOpacity": 0.03}).add_to(mapa)

    id_candidatos = {c["id_conductor"] for c in asignacion["candidatos"]}
    capas = {
        "DISPONIBLE": folium.FeatureGroup(name="Conductores disponibles"),
        "OCUPADO": folium.FeatureGroup(name="Conductores ocupados (en recogida)"),
        "EN_SERVICIO": folium.FeatureGroup(name="Conductores ocupados (en servicio)"),
        "INACTIVO": folium.FeatureGroup(name="Conductores inactivos", show=False),
    }
    for id_conductor, lat, lon, estado in asignacion.get("conductores_contexto", []):
        if id_conductor in id_candidatos:
            continue
        folium.CircleMarker([lat, lon], radius=4, color=COLORES_ESTADO.get(estado, "#999"), fill=True, fill_opacity=0.8,
                            weight=1, tooltip=f"Conductor {id_conductor} · {estado}").add_to(capas.get(estado, capas["DISPONIBLE"]))
    for capa in capas.values():
        capa.add_to(mapa)

    grupo_candidatos = folium.FeatureGroup(name="Candidatos evaluados (k más cercanos)")
    for orden, c in enumerate(sorted(asignacion["candidatos"], key=lambda x: x["distancia_haversine_m"]), start=1):
        seleccionado = c["seleccionado"]
        eta = c["eta_texto"]
        ruta = f"{c['distancia_ruta_m']:.0f} m" if c["distancia_ruta_m"] is not None else "sin ruta"
        html = (f"<b>{'SELECCIONADO · ' if seleccionado else ''}Conductor {c['id_conductor']}</b><br>{c['nombre']} · {c['placa']}"
                f"<br>Haversine: {c['distancia_haversine_m']:.0f} m<br>Por calles: {ruta}<br>ETA: {eta}"
                f"<br>Velocidad: {c['velocidad_kmh']} km/h<br>{c['motivo']}")
        if seleccionado:
            folium.Marker([c["latitud"], c["longitud"]], popup=folium.Popup(html, max_width=260),
                          tooltip=f"Seleccionado: conductor {c['id_conductor']} (ETA {eta})",
                          icon=folium.Icon(color="blue", icon="car", prefix="fa")).add_to(grupo_candidatos)
        else:
            folium.CircleMarker([c["latitud"], c["longitud"]], radius=9, color="#7c3aed", fill=True, fill_color="#a78bfa",
                                fill_opacity=0.9, weight=2, popup=folium.Popup(html, max_width=260),
                                tooltip=f"Candidato #{orden}: {c['id_conductor']} · ETA {eta}").add_to(grupo_candidatos)
            folium.PolyLine([[c["latitud"], c["longitud"]], [origen_lat, origen_lon]], color="#7c3aed", weight=1,
                            dash_array="4 6", opacity=0.6, tooltip="Distancia Haversine (línea recta)").add_to(grupo_candidatos)
    grupo_candidatos.add_to(mapa)

    folium.PolyLine([[lat, lon] for lon, lat in asignacion["ruta_recogida"]], color="#2563eb", weight=6, opacity=0.9,
                    tooltip=f"Ruta de recogida: {asignacion['distancia_ruta_m']:.0f} m · ETA {asignacion['eta_segundos'] / 60:.1f} min",
                    name="Ruta de recogida").add_to(mapa)
    folium.PolyLine([[lat, lon] for lon, lat in asignacion["ruta_viaje"]], color="#db2777", weight=5, opacity=0.85,
                    dash_array="10 6", tooltip=f"Ruta del viaje: {asignacion['distancia_viaje_m']:.0f} m",
                    name="Ruta del viaje").add_to(mapa)
    folium.Marker([origen_lat, origen_lon], tooltip="Pasajero (origen)",
                  popup=f"Pasajero {asignacion['id_pasajero']}<br>{asignacion.get('direccion_origen') or ''}",
                  icon=folium.Icon(color="green", icon="user", prefix="fa")).add_to(mapa)
    folium.Marker([destino_lat, destino_lon], tooltip="Destino del viaje",
                  icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa")).add_to(mapa)

    leyenda = f"""
    <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:#0b1220;color:#e2e8f0;padding:12px 14px;
         border-radius:10px;font:12px/1.5 system-ui;box-shadow:0 4px 18px rgba(0,0,0,.35);max-width:330px">
      <div style="font-weight:700;font-size:13px;margin-bottom:6px">CONDUCTOR CERCANO · Asignación #{asignacion['id_asignacion']}</div>
      <div>Distrito: {asignacion['id_distrito']} · {asignacion['fecha'][:19].replace('T', ' ')} UTC</div>
      <div>Conductor: <b>{asignacion['id_conductor']}</b> ({asignacion['placa']}) · ETA <b>{asignacion['eta_segundos'] / 60:.1f} min</b></div>
      <div>Recogida: {asignacion['distancia_ruta_m']:.0f} m por calles / {asignacion['distancia_haversine_m']:.0f} m en línea recta</div>
      <hr style="border-color:#1e293b">
      <div><span style="color:#22c55e">●</span> Disponible &nbsp;<span style="color:#f59e0b">●</span> En recogida
           &nbsp;<span style="color:#ef4444">●</span> En servicio</div>
      <div><span style="color:#a78bfa">●</span> Candidato evaluado &nbsp;<span style="color:#60a5fa">⬤</span> Seleccionado</div>
      <div><span style="color:#2563eb">━━</span> Ruta de recogida &nbsp;<span style="color:#db2777">╍╍</span> Ruta del viaje</div>
    </div>"""
    mapa.get_root().html.add_child(folium.Element(leyenda))
    MiniMap(toggle_display=True).add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)
    puntos = [[lat, lon] for lon, lat in asignacion["ruta_recogida"] + asignacion["ruta_viaje"]]
    if puntos:
        mapa.fit_bounds([[min(p[0] for p in puntos), min(p[1] for p in puntos)],
                         [max(p[0] for p in puntos), max(p[1] for p in puntos)]], padding=(30, 30))
    html = mapa.get_root().render()
    if ruta_salida is not None:
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        ruta_salida.write_text(html, encoding="utf-8")
    return html

// Fuentes y capas MapLibre compartidas (límite, red vial, flota 2D, rutas, edificios 3D).
import type maplibregl from "maplibre-gl";
import { COLOR_CIAN, COLOR_RECOGIDA, COLOR_VIAJE, EXPRESION_COLOR_ESTADO, registrarIconoFlecha } from "./estiloBase";

export const vacio = (): GeoJSON.FeatureCollection => ({ type: "FeatureCollection", features: [] });

function fuente(map: maplibregl.Map, id: string) {
  if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: vacio() });
}

export function agregarCapaEdificios(map: maplibregl.Map) {
  if (map.getLayer("edificios-3d") || !map.getSource("openmaptiles")) return;
  map.addLayer({
    id: "edificios-3d",
    type: "fill-extrusion",
    source: "openmaptiles",
    "source-layer": "building",
    minzoom: 13,
    layout: { visibility: "none" },
    paint: {
      "fill-extrusion-color": ["interpolate", ["linear"], ["coalesce", ["get", "render_height"], 8], 0, "#111a2e", 40, "#1b2a47", 120, "#25406e"],
      "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8],
      "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
      "fill-extrusion-opacity": 0.85,
    },
  });
}

export function agregarCapasOperacion(map: maplibregl.Map) {
  registrarIconoFlecha(map);
  for (const id of ["limite", "red-vial", "rutas", "rutas-3d", "pasajeros", "flota", "seleccion"]) fuente(map, id);

  map.addLayer({ id: "limite-relleno", type: "fill", source: "limite", paint: { "fill-color": COLOR_CIAN, "fill-opacity": 0.025 } });
  map.addLayer({ id: "limite-borde", type: "line", source: "limite", paint: { "line-color": COLOR_CIAN, "line-width": 1.6, "line-opacity": 0.6, "line-dasharray": [3, 2] } });

  map.addLayer({
    id: "red-vial-calles", type: "line", source: "red-vial", filter: ["==", ["geometry-type"], "LineString"],
    layout: { visibility: "none", "line-cap": "round" },
    paint: {
      "line-color": ["case", ["get", "sentido_unico"], "#a78bfa", "#38bdf8"],
      "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.5, 17, 2.5],
      "line-opacity": 0.55,
    },
  });
  map.addLayer({
    id: "red-vial-sentido", type: "symbol", source: "red-vial", minzoom: 16,
    filter: ["all", ["==", ["geometry-type"], "LineString"], ["get", "sentido_unico"]],
    layout: { visibility: "none", "symbol-placement": "line", "symbol-spacing": 70, "icon-image": "flecha", "icon-size": 0.35, "icon-rotate": 90, "icon-allow-overlap": true },
    paint: { "icon-color": "#c4b5fd", "icon-opacity": 0.8 },
  });
  map.addLayer({
    id: "red-vial-intersecciones", type: "circle", source: "red-vial", minzoom: 15,
    filter: ["==", ["geometry-type"], "Point"], layout: { visibility: "none" },
    paint: { "circle-radius": 2.2, "circle-color": "#e2e8f0", "circle-opacity": 0.7 },
  });

  map.addLayer({
    id: "rutas-recogida-halo", type: "line", source: "rutas", filter: ["==", ["get", "tipo"], "recogida"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": COLOR_RECOGIDA, "line-width": ["case", ["get", "destacada"], 12, 7], "line-opacity": 0.18, "line-blur": 3 },
  });
  map.addLayer({
    id: "rutas-viaje", type: "line", source: "rutas", filter: ["==", ["get", "tipo"], "viaje"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": COLOR_VIAJE, "line-width": ["case", ["get", "destacada"], 4.5, 2.2], "line-opacity": ["case", ["get", "destacada"], 0.95, 0.55], "line-dasharray": [2, 1.5] },
  });
  map.addLayer({
    id: "rutas-recogida", type: "line", source: "rutas", filter: ["==", ["get", "tipo"], "recogida"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": COLOR_RECOGIDA, "line-width": ["case", ["get", "destacada"], 5, 2.6], "line-opacity": ["case", ["get", "destacada"], 1, 0.75] },
  });
  map.addLayer({
    id: "rutas-3d", type: "fill-extrusion", source: "rutas-3d", layout: { visibility: "none" },
    paint: { "fill-extrusion-color": ["get", "color"], "fill-extrusion-height": ["get", "altura"], "fill-extrusion-base": 0, "fill-extrusion-opacity": 0.75 },
  });

  map.addLayer({
    id: "pasajeros-halo", type: "circle", source: "pasajeros",
    paint: { "circle-radius": 14, "circle-color": ["get", "color"], "circle-opacity": 0.15, "circle-blur": 0.6 },
  });
  map.addLayer({
    id: "pasajeros", type: "circle", source: "pasajeros",
    paint: { "circle-radius": 6, "circle-color": ["get", "color"], "circle-stroke-color": "#0b1220", "circle-stroke-width": 2 },
  });

  map.addLayer({
    id: "flota-circulos", type: "circle", source: "flota",
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 1.6, 14, 3, 17, 6.5],
      "circle-color": EXPRESION_COLOR_ESTADO,
      "circle-stroke-color": "#0b1220",
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 12, 0, 15, 1],
      "circle-opacity": 0.95,
    },
  });
  map.addLayer({
    id: "flota-flechas", type: "symbol", source: "flota", minzoom: 15.5,
    layout: { "icon-image": "flecha", "icon-size": ["interpolate", ["linear"], ["zoom"], 15.5, 0.45, 18, 0.8], "icon-rotate": ["get", "r"], "icon-rotation-alignment": "map", "icon-allow-overlap": true, "icon-ignore-placement": true },
    paint: { "icon-color": EXPRESION_COLOR_ESTADO, "icon-halo-color": "#0b1220", "icon-halo-width": 1.5 },
  });
  map.addLayer({
    id: "seleccion", type: "circle", source: "seleccion",
    paint: { "circle-radius": 16, "circle-color": "transparent", "circle-stroke-color": COLOR_CIAN, "circle-stroke-width": 2.5 },
  });
}

/** Banda extruida a lo largo de una polilínea (rutas con profundidad visual en 3D). */
export function polilineaAPoligonos(coordenadas: [number, number][], anchoMetros: number, propiedades: Record<string, unknown>): GeoJSON.Feature[] {
  const salida: GeoJSON.Feature[] = [];
  for (let i = 0; i < coordenadas.length - 1; i++) {
    const [lon1, lat1] = coordenadas[i];
    const [lon2, lat2] = coordenadas[i + 1];
    const kx = 111320 * Math.cos((lat1 * Math.PI) / 180);
    const dx = (lon2 - lon1) * kx;
    const dy = (lat2 - lat1) * 110540;
    const largo = Math.hypot(dx, dy);
    if (largo < 0.5) continue;
    const nx = (-dy / largo) * (anchoMetros / 2);
    const ny = (dx / largo) * (anchoMetros / 2);
    const desplazamiento = (lon: number, lat: number, s: number): [number, number] => [lon + (s * nx) / kx, lat + (s * ny) / 110540];
    salida.push({
      type: "Feature",
      properties: propiedades,
      geometry: { type: "Polygon", coordinates: [[desplazamiento(lon1, lat1, 1), desplazamiento(lon2, lat2, 1), desplazamiento(lon2, lat2, -1), desplazamiento(lon1, lat1, -1), desplazamiento(lon1, lat1, 1)]] },
    });
  }
  return salida;
}

export function fijarDatos(map: maplibregl.Map, id: string, datos: GeoJSON.FeatureCollection) {
  const f = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  f?.setData(datos);
}

export function visibilidad(map: maplibregl.Map, capas: string[], visible: boolean) {
  for (const capa of capas) if (map.getLayer(capa)) map.setLayoutProperty(capa, "visibility", visible ? "visible" : "none");
}

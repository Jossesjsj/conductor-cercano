// Estilos del mapa base. Principal: OpenFreeMap (datos OSM, esquema OpenMapTiles, con
// alturas de edificios para 3D, sin clave). Respaldo: teselas ráster estándar de OSM.
import type { StyleSpecification } from "maplibre-gl";

export const ESTILO_PRINCIPAL = "https://tiles.openfreemap.org/styles/dark";

export const ESTILO_RESPALDO: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© colaboradores de OpenStreetMap",
    },
  },
  layers: [
    { id: "fondo", type: "background", paint: { "background-color": "#070b14" } },
    { id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.9, "raster-brightness-max": 0.45, "raster-contrast": 0.1 } },
  ],
};

export const COLORES_ESTADO: Record<string, string> = {
  DISPONIBLE: "#22c55e",
  OCUPADO: "#f59e0b",
  EN_SERVICIO: "#ef4444",
  INACTIVO: "#64748b",
};

export const COLOR_RECOGIDA = "#3b82f6";
export const COLOR_VIAJE = "#ec4899";
export const COLOR_CIAN = "#22d3ee";

/** Expresión de color por código de estado (0..3), como lo envía el WebSocket. */
export const EXPRESION_COLOR_ESTADO: any = [
  "match", ["get", "e"],
  0, COLORES_ESTADO.DISPONIBLE,
  1, COLORES_ESTADO.OCUPADO,
  2, COLORES_ESTADO.EN_SERVICIO,
  COLORES_ESTADO.INACTIVO,
];

/** Ajustes del estilo vectorial: atenuar etiquetas de POI y realzar las vías. */
export function afinarEstilo(map: maplibregl.Map) {
  const estilo = map.getStyle();
  for (const capa of estilo.layers ?? []) {
    if (capa.type === "symbol" && /poi|housenumber/.test(capa.id)) map.setLayoutProperty(capa.id, "visibility", "none");
  }
}

/** Crea el icono de flecha (sentido de marcha) para la capa de símbolos. */
export function registrarIconoFlecha(map: maplibregl.Map) {
  if (map.hasImage("flecha")) return;
  const tam = 48;
  const lienzo = document.createElement("canvas");
  lienzo.width = lienzo.height = tam;
  const ctx = lienzo.getContext("2d")!;
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.moveTo(tam / 2, 4);
  ctx.lineTo(tam - 10, tam - 8);
  ctx.lineTo(tam / 2, tam - 16);
  ctx.lineTo(10, tam - 8);
  ctx.closePath();
  ctx.fill();
  map.addImage("flecha", ctx.getImageData(0, 0, tam, tam), { sdf: true, pixelRatio: 2 });
}

// Mapa de una asignación concreta: candidatos, conductor elegido, rutas de recogida y viaje.
import { useEffect, useRef } from "react";
import type maplibregl from "maplibre-gl";
import type { Candidato, EstadoConductor } from "@/services/tipos";
import { COLORES_ESTADO, COLOR_RECOGIDA, COLOR_VIAJE } from "./estiloBase";
import { fijarDatos, vacio } from "./capasMapa";
import { usarMapa } from "./usarMapa";

export interface DatosMapaRuta {
  origen?: [number, number] | null;
  destino?: [number, number] | null;
  rutaRecogida?: [number, number][];
  rutaViaje?: [number, number][];
  candidatos?: Candidato[];
  contexto?: [number, number, number, EstadoConductor][];
  limite?: GeoJSON.Feature | null;
}

export interface VehiculoSeguido {
  lon: number;
  lat: number;
  rumbo: number;
}

interface Props extends DatosMapaRuta {
  alHacerClic?: (lngLat: [number, number]) => void;
  centroInicial?: [number, number];
  /** Vehículo en movimiento (seguimiento del viaje); su posición se interpola entre lecturas. */
  vehiculo?: VehiculoSeguido | null;
  /** Si el pasajero ya subió, su marcador de origen se oculta (viaja dentro del vehículo). */
  pasajeroABordo?: boolean;
  seguirVehiculo?: boolean;
  /** Si se indica, el mapa solo se reencuadra cuando cambia esta clave (evita saltos en vivo). */
  claveEncuadre?: string;
  duracionTransicionMs?: number;
  /** Puntos a encuadrar cuando cambia ``claveEncuadre`` (si no, se usan rutas y marcadores). */
  puntosEncuadre?: [number, number][];
  /** Permite elegir un candidato haciendo clic sobre él en el mapa. */
  alSeleccionarCandidato?: (idConductor: number) => void;
}

/** Ícono del auto visto desde arriba (frente hacia el norte, se rota con el rumbo). */
function registrarIconoAuto(map: maplibregl.Map) {
  if (map.hasImage("auto-seguido")) return;
  const ancho = 44, alto = 80;
  const lienzo = document.createElement("canvas");
  lienzo.width = ancho;
  lienzo.height = alto;
  const ctx = lienzo.getContext("2d")!;
  const rect = (x: number, y: number, w: number, h: number, r: number) => {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  };
  ctx.shadowColor = "rgba(34,211,238,0.9)";
  ctx.shadowBlur = 8;
  const degradado = ctx.createLinearGradient(0, 0, ancho, alto);
  degradado.addColorStop(0, "#3b82f6");
  degradado.addColorStop(1, "#22d3ee");
  ctx.fillStyle = degradado;
  rect(6, 4, ancho - 12, alto - 8, 12);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.fillStyle = "#0b1220";
  rect(11, 18, ancho - 22, 14, 4); // parabrisas
  ctx.fill();
  rect(11, 50, ancho - 22, 12, 4); // luneta
  ctx.fill();
  ctx.fillStyle = "#fef08a";
  ctx.fillRect(10, 5, 6, 3); // faros
  ctx.fillRect(ancho - 16, 5, 6, 3);
  map.addImage("auto-seguido", ctx.getImageData(0, 0, ancho, alto), { pixelRatio: 2 });
}

function agregarCapas(map: maplibregl.Map) {
  registrarIconoAuto(map);
  for (const id of ["r-limite", "r-contexto", "r-rutas", "r-lineas-candidatos", "r-candidatos", "r-puntos", "r-vehiculo"]) {
    if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: vacio() });
  }
  map.addLayer({ id: "r-limite", type: "line", source: "r-limite", paint: { "line-color": "#22d3ee", "line-width": 1.4, "line-opacity": 0.5, "line-dasharray": [3, 2] } });
  map.addLayer({
    id: "r-contexto", type: "circle", source: "r-contexto",
    paint: { "circle-radius": 3.2, "circle-color": ["get", "color"], "circle-opacity": 0.75, "circle-stroke-width": 0.5, "circle-stroke-color": "#0b1220" },
  });
  map.addLayer({
    id: "r-lineas-candidatos", type: "line", source: "r-lineas-candidatos",
    paint: { "line-color": "#a78bfa", "line-width": 1, "line-opacity": 0.6, "line-dasharray": [2, 3] },
  });
  map.addLayer({
    id: "r-viaje", type: "line", source: "r-rutas", filter: ["==", ["get", "tipo"], "viaje"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": COLOR_VIAJE, "line-width": 4, "line-dasharray": [2, 1.4], "line-opacity": 0.9 },
  });
  map.addLayer({
    id: "r-recogida-halo", type: "line", source: "r-rutas", filter: ["==", ["get", "tipo"], "recogida"],
    paint: { "line-color": COLOR_RECOGIDA, "line-width": 12, "line-opacity": 0.2, "line-blur": 3 },
  });
  map.addLayer({
    id: "r-recogida", type: "line", source: "r-rutas", filter: ["==", ["get", "tipo"], "recogida"],
    layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": COLOR_RECOGIDA, "line-width": 5 },
  });
  map.addLayer({
    id: "r-candidatos", type: "circle", source: "r-candidatos",
    paint: {
      "circle-radius": ["case", ["get", "seleccionado"], 10, 7],
      "circle-color": ["case", ["get", "seleccionado"], "#22d3ee", ["get", "valido"], "#a78bfa", "#64748b"],
      "circle-stroke-color": "#0b1220", "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: "r-candidatos-etiqueta", type: "symbol", source: "r-candidatos",
    layout: { "text-field": ["get", "etiqueta"], "text-size": 11, "text-offset": [0, -1.6], "text-font": ["Noto Sans Bold"], "text-allow-overlap": true },
    paint: { "text-color": "#e2e8f0", "text-halo-color": "#0b1220", "text-halo-width": 1.5 },
  });
  map.addLayer({
    id: "r-puntos", type: "circle", source: "r-puntos",
    paint: { "circle-radius": 8, "circle-color": ["get", "color"], "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 },
  });
  map.addLayer({
    id: "r-vehiculo-halo", type: "circle", source: "r-vehiculo",
    paint: { "circle-radius": 22, "circle-color": "#22d3ee", "circle-opacity": 0.14, "circle-blur": 0.5 },
  });
  map.addLayer({
    id: "r-vehiculo", type: "symbol", source: "r-vehiculo",
    layout: {
      "icon-image": "auto-seguido", "icon-rotate": ["get", "rumbo"], "icon-rotation-alignment": "map",
      "icon-size": ["interpolate", ["linear"], ["zoom"], 12, 0.55, 16, 0.9, 18, 1.2],
      "icon-allow-overlap": true, "icon-ignore-placement": true,
    },
  });
}

/** Caja [[oeste, sur], [este, norte]] de cualquier geometría GeoJSON (Polygon, MultiPolygon, ...). */
export function limitesGeometria(geometria: GeoJSON.Geometry): [[number, number], [number, number]] | null {
  let oeste = Infinity, sur = Infinity, este = -Infinity, norte = -Infinity;
  const recorrer = (v: unknown): void => {
    if (Array.isArray(v) && typeof v[0] === "number" && typeof v[1] === "number") {
      oeste = Math.min(oeste, v[0]); este = Math.max(este, v[0]);
      sur = Math.min(sur, v[1]); norte = Math.max(norte, v[1]);
    } else if (Array.isArray(v)) v.forEach(recorrer);
  };
  recorrer("coordinates" in geometria ? geometria.coordinates : []);
  return Number.isFinite(oeste) ? [[oeste, sur], [este, norte]] : null;
}

function encuadrarPuntos(mapa: maplibregl.Map, puntos: [number, number][], zoomMaximo = 17) {
  const lons = puntos.map((p) => p[0]);
  const lats = puntos.map((p) => p[1]);
  mapa.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: { top: 80, left: 80, right: 100, bottom: 110 }, duration: 800, maxZoom: zoomMaximo });
}

function encuadrar(mapa: maplibregl.Map, datos: DatosMapaRuta, vehiculo?: VehiculoSeguido | null) {
  const { origen, destino, rutaRecogida = [], rutaViaje = [], limite } = datos;
  const todos: [number, number][] = [...rutaRecogida, ...rutaViaje, ...(origen ? [origen] : []), ...(destino ? [destino] : []),
    ...(vehiculo ? [[vehiculo.lon, vehiculo.lat] as [number, number]] : [])];
  if (todos.length > 1) {
    const lons = todos.map((p) => p[0]);
    const lats = todos.map((p) => p[1]);
    mapa.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: { top: 70, left: 70, right: 100, bottom: 110 }, duration: 700, maxZoom: 16.5 });
  } else if (limite && !origen) {
    const caja = limitesGeometria(limite.geometry);
    if (caja) mapa.fitBounds(caja, { padding: 30, duration: 0 });
  }
}

export function MapaRuta({
  alHacerClic, centroInicial, vehiculo = null, pasajeroABordo = false, seguirVehiculo = false, claveEncuadre,
  duracionTransicionMs = 700, alSeleccionarCandidato, puntosEncuadre, ...datos
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const clic = useRef(alHacerClic);
  clic.current = alHacerClic;
  const { mapa } = usarMapa(contenedor, { centro: centroInicial, zoom: 14, alCargar: agregarCapas });
  const datosActuales = useRef(datos);
  datosActuales.current = datos;
  const seguir = useRef(seguirVehiculo);
  seguir.current = seguirVehiculo;
  const elegirCandidato = useRef(alSeleccionarCandidato);
  elegirCandidato.current = alSeleccionarCandidato;

  useEffect(() => {
    if (!mapa) return;
    const alClic = (e: maplibregl.MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.id;
      if (id !== undefined && elegirCandidato.current) elegirCandidato.current(Number(id));
    };
    const entrar = () => { if (elegirCandidato.current) mapa.getCanvas().style.cursor = "pointer"; };
    const salir = () => { mapa.getCanvas().style.cursor = ""; };
    mapa.on("click", "r-candidatos", alClic);
    mapa.on("mouseenter", "r-candidatos", entrar);
    mapa.on("mouseleave", "r-candidatos", salir);
    return () => {
      mapa.off("click", "r-candidatos", alClic);
      mapa.off("mouseenter", "r-candidatos", entrar);
      mapa.off("mouseleave", "r-candidatos", salir);
    };
  }, [mapa]);

  // Animación del vehículo: interpola entre la última posición mostrada y la nueva lectura.
  const animacion = useRef<{ desde: VehiculoSeguido; hasta: VehiculoSeguido; inicio: number } | null>(null);
  useEffect(() => {
    if (!vehiculo) {
      animacion.current = null;
      return;
    }
    const ahora = performance.now();
    const actual = animacion.current;
    let desde = vehiculo;
    if (actual) {
      const f = Math.min(1, (ahora - actual.inicio) / duracionTransicionMs);
      let giro = actual.hasta.rumbo - actual.desde.rumbo;
      if (giro > 180) giro -= 360;
      if (giro < -180) giro += 360;
      desde = {
        lon: actual.desde.lon + (actual.hasta.lon - actual.desde.lon) * f,
        lat: actual.desde.lat + (actual.hasta.lat - actual.desde.lat) * f,
        rumbo: actual.desde.rumbo + giro * f,
      };
    }
    animacion.current = { desde, hasta: vehiculo, inicio: ahora };
  }, [vehiculo, duracionTransicionMs]);

  useEffect(() => {
    if (!mapa) return;
    let cuadro = 0;
    const paso = (t: number) => {
      cuadro = requestAnimationFrame(paso);
      const a = animacion.current;
      if (!a) {
        fijarDatos(mapa, "r-vehiculo", vacio());
        return;
      }
      const f = Math.min(1, (t - a.inicio) / duracionTransicionMs);
      let giro = a.hasta.rumbo - a.desde.rumbo;
      if (giro > 180) giro -= 360;
      if (giro < -180) giro += 360;
      const lon = a.desde.lon + (a.hasta.lon - a.desde.lon) * f;
      const lat = a.desde.lat + (a.hasta.lat - a.desde.lat) * f;
      fijarDatos(mapa, "r-vehiculo", {
        type: "FeatureCollection",
        features: [{ type: "Feature", properties: { rumbo: a.desde.rumbo + giro * f }, geometry: { type: "Point", coordinates: [lon, lat] } }],
      });
      if (seguir.current && f < 1) mapa.setCenter([lon, lat]);
    };
    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  }, [mapa, duracionTransicionMs]);

  useEffect(() => {
    if (mapa && seguirVehiculo && vehiculo) mapa.easeTo({ center: [vehiculo.lon, vehiculo.lat], zoom: Math.max(mapa.getZoom(), 15.5), duration: 600 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapa, seguirVehiculo]);

  useEffect(() => {
    if (!mapa) return;
    const manejar = (e: maplibregl.MapMouseEvent) => clic.current?.([e.lngLat.lng, e.lngLat.lat]);
    mapa.on("click", manejar);
    mapa.getCanvas().style.cursor = alHacerClic ? "crosshair" : "";
    return () => {
      mapa.off("click", manejar);
    };
  }, [mapa, alHacerClic]);

  useEffect(() => {
    if (!mapa) return;
    const { origen, destino, rutaRecogida = [], rutaViaje = [], candidatos = [], contexto = [], limite } = datos;
    fijarDatos(mapa, "r-limite", { type: "FeatureCollection", features: limite ? [limite] : [] });
    fijarDatos(mapa, "r-contexto", {
      type: "FeatureCollection",
      features: contexto
        .filter(([id]) => !candidatos.some((c) => c.id_conductor === id))
        .map(([, lat, lon, estado]) => ({ type: "Feature", properties: { color: COLORES_ESTADO[estado] }, geometry: { type: "Point", coordinates: [lon, lat] } })),
    });
    const rutas: GeoJSON.Feature[] = [];
    if (rutaViaje.length > 1) rutas.push({ type: "Feature", properties: { tipo: "viaje" }, geometry: { type: "LineString", coordinates: rutaViaje } });
    if (rutaRecogida.length > 1) rutas.push({ type: "Feature", properties: { tipo: "recogida" }, geometry: { type: "LineString", coordinates: rutaRecogida } });
    fijarDatos(mapa, "r-rutas", { type: "FeatureCollection", features: rutas });
    const ordenados = [...candidatos].sort((a, b) => a.distancia_haversine_m - b.distancia_haversine_m);
    fijarDatos(mapa, "r-candidatos", {
      type: "FeatureCollection",
      features: ordenados.map((c, i) => ({
        type: "Feature",
        properties: { id: c.id_conductor, seleccionado: c.seleccionado, valido: c.valido, etiqueta: c.seleccionado ? `★ ${c.id_conductor}` : `#${i + 1}` },
        geometry: { type: "Point", coordinates: [c.longitud, c.latitud] },
      })),
    });
    fijarDatos(mapa, "r-lineas-candidatos", {
      type: "FeatureCollection",
      features: origen ? ordenados.filter((c) => !c.seleccionado).map((c) => ({
        type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[c.longitud, c.latitud], origen] },
      })) : [],
    });
    const puntos: GeoJSON.Feature[] = [];
    if (origen && !pasajeroABordo) puntos.push({ type: "Feature", properties: { color: "#22c55e" }, geometry: { type: "Point", coordinates: origen } });
    if (destino) puntos.push({ type: "Feature", properties: { color: COLOR_VIAJE }, geometry: { type: "Point", coordinates: destino } });
    fijarDatos(mapa, "r-puntos", { type: "FeatureCollection", features: puntos });
    if (claveEncuadre === undefined) encuadrar(mapa, datos);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapa, datos.origen, datos.destino, datos.rutaRecogida, datos.rutaViaje, datos.candidatos, datos.contexto, datos.limite, pasajeroABordo]);

  // Encuadre controlado: en el seguimiento en vivo solo se reencuadra al cambiar de fase.
  useEffect(() => {
    if (!mapa || claveEncuadre === undefined || seguir.current) return;
    if (puntosEncuadre && puntosEncuadre.length > 1) encuadrarPuntos(mapa, puntosEncuadre);
    else encuadrar(mapa, datosActuales.current, vehiculo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapa, claveEncuadre]);

  return <div ref={contenedor} className="h-full w-full" />;
}

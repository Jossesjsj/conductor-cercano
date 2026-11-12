// Mapa en vivo del centro de operaciones (2D/3D) alimentado por WebSocket.
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { api } from "@/services/api";
import { tiempoReal } from "@/services/tiempoReal";
import { usarAlmacen, type RutaActiva } from "@/stores/almacen";
import { flotaVisual } from "@/stores/flotaVisual";
import { CapaVehiculos3D } from "./capaVehiculos3D";
import { agregarCapaEdificios, agregarCapasOperacion, fijarDatos, polilineaAPoligonos, vacio, visibilidad } from "./capasMapa";
import { COLOR_RECOGIDA, COLOR_VIAJE } from "./estiloBase";
import { usarMapa } from "./usarMapa";

const CODIGOS: Record<string, number> = { DISPONIBLE: 0, OCUPADO: 1, EN_SERVICIO: 2, INACTIVO: 3 };
const SIN_MARCADORES: { lon: number; lat: number; color: string }[] = [];

interface Props {
  alHacerClic?: (lngLat: [number, number]) => void;
  marcadoresExtra?: { lon: number; lat: number; color: string }[];
}

export function MapaOperaciones({ alHacerClic, marcadoresExtra = SIN_MARCADORES }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const capa3D = useRef(new CapaVehiculos3D());
  const clic = useRef(alHacerClic);
  clic.current = alHacerClic;

  const { mapa, usaRespaldo } = usarMapa(contenedor, {
    alCargar: (map) => {
      agregarCapaEdificios(map);
      agregarCapasOperacion(map);
      map.addLayer(capa3D.current);
    },
  });

  const distrito = usarAlmacen((s) => s.simulacion?.distrito?.id_distrito);
  const centro = usarAlmacen((s) => s.simulacion?.distrito?.centro);
  const rutas = usarAlmacen((s) => s.rutas);
  const modo3D = usarAlmacen((s) => s.modo3D);
  const modelos3D = usarAlmacen((s) => s.modelos3D);
  const mostrarEdificios = usarAlmacen((s) => s.mostrarEdificios);
  const mostrarRedVial = usarAlmacen((s) => s.mostrarRedVial);
  const mostrarRutas = usarAlmacen((s) => s.mostrarRutas);
  const filtros = usarAlmacen((s) => s.filtros);
  const seleccionado = usarAlmacen((s) => s.conductorSeleccionado);
  const conexion = usarAlmacen((s) => s.conexion);

  // Distrito: límite, encuadre y origen de la escena 3D.
  useEffect(() => {
    if (!mapa || !distrito) return;
    let cancelado = false;
    api.distrito(distrito).then(({ limite, distrito: d }) => {
      if (cancelado) return;
      fijarDatos(mapa, "limite", { type: "FeatureCollection", features: [limite] });
      const [o, s, e, n] = d.limites;
      mapa.fitBounds([[o, s], [e, n]], { padding: 40, duration: 900 });
    }).catch(() => undefined);
    if (centro) capa3D.current.fijarOrigen(centro[0], centro[1]);
    return () => {
      cancelado = true;
    };
  }, [mapa, distrito, centro]);

  // Vista enviada al servidor (solo recibe los conductores dentro de ella).
  useEffect(() => {
    if (!mapa) return;
    const enviarVista = () => {
      const b = mapa.getBounds();
      tiempoReal.fijarVista({ limites: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], zoom: mapa.getZoom() });
    };
    enviarVista();
    mapa.on("moveend", enviarVista);
    return () => {
      mapa.off("moveend", enviarVista);
    };
  }, [mapa, conexion]);

  // Bucle de animación: interpolación de posiciones (2D a ~20 fps; la capa 3D en cada cuadro).
  useEffect(() => {
    if (!mapa) return;
    let cuadro = 0;
    let ultimo = 0;
    const paso = (t: number) => {
      cuadro = requestAnimationFrame(paso);
      if (t - ultimo < 50) return;
      ultimo = t;
      const filtrosActivos = usarAlmacen.getState().filtros;
      const elegido = usarAlmacen.getState().conductorSeleccionado;
      const features: GeoJSON.Feature[] = [];
      let seleccion: GeoJSON.Feature | null = null;
      for (const v of flotaVisual.vehiculos.values()) {
        const [lat, lon, rumbo] = flotaVisual.interpolar(v, t);
        if (v.id === elegido) seleccion = { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [lon, lat] } };
        if (!filtrosActivos[v.estado]) continue;
        features.push({ type: "Feature", properties: { id: v.id, e: CODIGOS[v.estado], r: rumbo }, geometry: { type: "Point", coordinates: [lon, lat] } });
      }
      fijarDatos(mapa, "flota", { type: "FeatureCollection", features });
      fijarDatos(mapa, "seleccion", { type: "FeatureCollection", features: seleccion ? [seleccion] : [] });
    };
    cuadro = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(cuadro);
  }, [mapa]);

  // Rutas activas, pasajeros y marcadores elevados.
  useEffect(() => {
    if (!mapa) return;
    const lineas: GeoJSON.Feature[] = [];
    const bandas: GeoJSON.Feature[] = [];
    const pasajeros: GeoJSON.Feature[] = [];
    const elevados: { lon: number; lat: number; color: string }[] = [...marcadoresExtra];
    const lista = Object.values(rutas) as RutaActiva[];
    for (const r of lista) {
      const destacada = r.idConductor === seleccionado;
      if (r.fase === "recogida") {
        lineas.push({ type: "Feature", properties: { tipo: "recogida", destacada }, geometry: { type: "LineString", coordinates: r.recogida } });
        pasajeros.push({ type: "Feature", properties: { color: "#22c55e" }, geometry: { type: "Point", coordinates: r.origen } });
        elevados.push({ lon: r.origen[0], lat: r.origen[1], color: "#22c55e" });
        if (modo3D) bandas.push(...polilineaAPoligonos(r.recogida, destacada ? 9 : 5, { color: COLOR_RECOGIDA, altura: destacada ? 14 : 6 }));
      }
      if (r.viaje.length > 1) {
        lineas.push({ type: "Feature", properties: { tipo: "viaje", destacada }, geometry: { type: "LineString", coordinates: r.viaje } });
        if (modo3D && (destacada || r.fase === "viaje")) bandas.push(...polilineaAPoligonos(r.viaje, destacada ? 7 : 4, { color: COLOR_VIAJE, altura: destacada ? 10 : 4 }));
      }
      pasajeros.push({ type: "Feature", properties: { color: COLOR_VIAJE }, geometry: { type: "Point", coordinates: r.destino } });
      if (r.fase === "viaje") elevados.push({ lon: r.destino[0], lat: r.destino[1], color: COLOR_VIAJE });
    }
    fijarDatos(mapa, "rutas", { type: "FeatureCollection", features: mostrarRutas ? lineas : [] });
    fijarDatos(mapa, "rutas-3d", { type: "FeatureCollection", features: mostrarRutas ? bandas.slice(0, 20000) : [] });
    fijarDatos(mapa, "pasajeros", { type: "FeatureCollection", features: pasajeros });
    capa3D.current.fijarMarcadores(modo3D ? elevados : []);
  }, [mapa, rutas, seleccionado, mostrarRutas, modo3D, marcadoresExtra]);

  // 2D / 3D, edificios, modelos e iconos.
  useEffect(() => {
    if (!mapa) return;
    mapa.easeTo(modo3D ? { pitch: 62, bearing: -24, duration: 1100 } : { pitch: 0, bearing: 0, duration: 900 });
    visibilidad(mapa, ["edificios-3d"], modo3D && mostrarEdificios);
    visibilidad(mapa, ["rutas-3d"], modo3D);
    visibilidad(mapa, ["rutas-recogida", "rutas-recogida-halo"], true);
    const usarModelos = modo3D && modelos3D;
    capa3D.current.visible = usarModelos;
    visibilidad(mapa, ["flota-circulos", "flota-flechas"], !usarModelos);
    mapa.triggerRepaint();
  }, [mapa, modo3D, modelos3D, mostrarEdificios]);

  useEffect(() => {
    capa3D.current.filtroEstados = { ...filtros };
    capa3D.current.seleccionado = seleccionado;
  }, [filtros, seleccionado]);

  // Red vial procesada (grafo real que usan Dijkstra y la simulación).
  useEffect(() => {
    if (!mapa || !distrito) return;
    visibilidad(mapa, ["red-vial-calles", "red-vial-sentido", "red-vial-intersecciones"], mostrarRedVial);
    if (!mostrarRedVial) return;
    let cancelado = false;
    api.redVial(distrito).then((datos) => !cancelado && fijarDatos(mapa, "red-vial", datos)).catch(() => undefined);
    return () => {
      cancelado = true;
      fijarDatos(mapa, "red-vial", vacio());
    };
  }, [mapa, distrito, mostrarRedVial]);

  // Selección: vehículo más cercano al clic en pantalla (vale para íconos y modelos 3D).
  useEffect(() => {
    if (!mapa) return;
    const manejar = (e: maplibregl.MapMouseEvent) => {
      if (clic.current) {
        clic.current([e.lngLat.lng, e.lngLat.lat]);
        return;
      }
      let mejor: number | null = null;
      let distanciaMinima = 22;
      const ahora = performance.now();
      const filtrosActivos = usarAlmacen.getState().filtros;
      for (const v of flotaVisual.vehiculos.values()) {
        if (!filtrosActivos[v.estado]) continue;
        const [lat, lon] = flotaVisual.interpolar(v, ahora);
        const p = mapa.project([lon, lat]);
        const d = Math.hypot(p.x - e.point.x, p.y - e.point.y);
        if (d < distanciaMinima) {
          distanciaMinima = d;
          mejor = v.id;
        }
      }
      usarAlmacen.getState().seleccionarConductor(mejor);
    };
    mapa.on("click", manejar);
    return () => {
      mapa.off("click", manejar);
    };
  }, [mapa]);

  useEffect(() => {
    if (!mapa) return;
    mapa.getCanvas().style.cursor = alHacerClic ? "crosshair" : "";
  }, [mapa, alHacerClic]);

  // Sincronización periódica de servicios activos (consistencia tras reconexiones).
  useEffect(() => {
    if (conexion !== "conectado") return;
    const sincronizar = () =>
      api.serviciosActivos().then((lista) =>
        usarAlmacen.getState().reemplazarRutas(lista.map((s) => ({
          idPasajero: s.id_pasajero, idConductor: s.id_conductor, idAsignacion: s.id_asignacion,
          recogida: s.fase === "recogida" ? s.ruta_restante : [], viaje: s.fase === "viaje" ? s.ruta_restante : s.ruta_viaje,
          origen: s.origen, destino: s.destino, fase: s.fase, creada: Date.now(),
        }))),
      ).catch(() => undefined);
    sincronizar();
    const t = window.setInterval(sincronizar, 15000);
    return () => window.clearInterval(t);
  }, [conexion, distrito]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={contenedor} className="h-full w-full" />
      {usaRespaldo && (
        <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full bg-amber-500/15 px-3 py-1 text-xs text-amber-300 ring-1 ring-amber-500/30">
          Mapa vectorial no disponible: usando teselas ráster de OSM (sin edificios 3D)
        </div>
      )}
    </div>
  );
}

// Estado global de la interfaz (Zustand). Los datos provienen siempre del backend.
import { create } from "zustand";
import type { EstadoConductor, EstadoSimulacion, Estadisticas, ResultadoSolicitud } from "@/services/tipos";

export type EstadoConexion = "conectando" | "conectado" | "desconectado";

export interface PuntoSerie {
  turno: number;
  disponibles: number;
  ocupados: number;
  eta: number | null;
  duracion: number;
  pasajeros: number;
}

export interface EventoFeed {
  id: number;
  tipo: "asignacion" | "recogida" | "finalizacion" | "rechazo" | "sistema";
  texto: string;
  fecha: number;
}

export interface RutaActiva {
  idPasajero: number;
  idConductor: number;
  idAsignacion: number | null;
  recogida: [number, number][];
  viaje: [number, number][];
  origen: [number, number];
  destino: [number, number];
  fase: "recogida" | "viaje";
  creada: number;
}

interface Almacen {
  conexion: EstadoConexion;
  reconexiones: number;
  simulacion: EstadoSimulacion | null;
  estadisticas: Estadisticas | null;
  serie: PuntoSerie[];
  eventos: EventoFeed[];
  rutas: Record<number, RutaActiva>;
  ultimaAsignacion: ResultadoSolicitud | null;
  conductorSeleccionado: number | null;

  modo3D: boolean;
  modelos3D: boolean;
  mostrarRedVial: boolean;
  mostrarEdificios: boolean;
  mostrarRutas: boolean;
  filtros: Record<EstadoConductor, boolean>;

  fijarConexion: (c: EstadoConexion) => void;
  fijarSimulacion: (s: EstadoSimulacion) => void;
  fijarEstadisticas: (e: Estadisticas) => void;
  agregarEvento: (tipo: EventoFeed["tipo"], texto: string) => void;
  registrarAsignacion: (r: ResultadoSolicitud) => void;
  marcarRecogida: (idPasajero: number) => void;
  finalizarRuta: (idPasajero: number) => void;
  reemplazarRutas: (rutas: RutaActiva[]) => void;
  seleccionarConductor: (id: number | null) => void;
  alternar: (clave: "modo3D" | "modelos3D" | "mostrarRedVial" | "mostrarEdificios" | "mostrarRutas") => void;
  fijarModo3D: (valor: boolean) => void;
  alternarFiltro: (estado: EstadoConductor) => void;
  reiniciarVista: () => void;
}

let secuenciaEventos = 0;

export const usarAlmacen = create<Almacen>((set) => ({
  conexion: "conectando",
  reconexiones: 0,
  simulacion: null,
  estadisticas: null,
  serie: [],
  eventos: [],
  rutas: {},
  ultimaAsignacion: null,
  conductorSeleccionado: null,

  modo3D: false,
  modelos3D: true,
  mostrarRedVial: false,
  mostrarEdificios: true,
  mostrarRutas: true,
  filtros: { DISPONIBLE: true, OCUPADO: true, EN_SERVICIO: true, INACTIVO: false },

  fijarConexion: (conexion) => set((s) => ({ conexion, reconexiones: conexion === "conectado" ? s.reconexiones : s.reconexiones + (s.conexion === "conectado" ? 1 : 0) })),
  fijarSimulacion: (simulacion) => set({ simulacion }),
  fijarEstadisticas: (e) =>
    set((s) => {
      const ultimo = s.serie[s.serie.length - 1];
      const punto: PuntoSerie = {
        turno: e.turno, disponibles: e.conductores_disponibles, ocupados: e.conductores_ocupados,
        eta: e.eta_promedio_s, duracion: e.ultima_duracion_turno_ms, pasajeros: e.pasajeros_activos,
      };
      const serie = ultimo && ultimo.turno === e.turno ? [...s.serie.slice(0, -1), punto] : [...s.serie, punto].slice(-180);
      return { estadisticas: e, serie };
    }),
  agregarEvento: (tipo, texto) =>
    set((s) => ({ eventos: [{ id: ++secuenciaEventos, tipo, texto, fecha: Date.now() }, ...s.eventos].slice(0, 60) })),
  registrarAsignacion: (r) =>
    set((s) => {
      if (!r.exito || !r.conductor) return { ultimaAsignacion: r };
      const ruta: RutaActiva = {
        idPasajero: r.pasajero.id_pasajero, idConductor: r.conductor.id_conductor, idAsignacion: r.id_asignacion,
        recogida: r.ruta_recogida ?? [], viaje: r.ruta_viaje ?? [],
        origen: [r.pasajero.origen.longitud, r.pasajero.origen.latitud],
        destino: [r.pasajero.destino.longitud, r.pasajero.destino.latitud], fase: "recogida", creada: Date.now(),
      };
      const rutas = { ...s.rutas, [ruta.idPasajero]: ruta };
      const claves = Object.keys(rutas);
      if (claves.length > 250) delete rutas[Number(claves[0])];
      return { ultimaAsignacion: r, rutas };
    }),
  marcarRecogida: (idPasajero) =>
    set((s) => (s.rutas[idPasajero] ? { rutas: { ...s.rutas, [idPasajero]: { ...s.rutas[idPasajero], fase: "viaje" } } } : {})),
  finalizarRuta: (idPasajero) =>
    set((s) => {
      if (!s.rutas[idPasajero]) return {};
      const rutas = { ...s.rutas };
      delete rutas[idPasajero];
      return { rutas };
    }),
  reemplazarRutas: (lista) => set({ rutas: Object.fromEntries(lista.map((r) => [r.idPasajero, r])) }),
  seleccionarConductor: (id) => set({ conductorSeleccionado: id }),
  alternar: (clave) => set((s) => ({ [clave]: !s[clave] }) as Partial<Almacen>),
  fijarModo3D: (valor) => set({ modo3D: valor }),
  alternarFiltro: (estado) => set((s) => ({ filtros: { ...s.filtros, [estado]: !s.filtros[estado] } })),
  reiniciarVista: () => set({ serie: [], rutas: {}, ultimaAsignacion: null, conductorSeleccionado: null }),
}));

// Cliente HTTP del backend. Toda la lógica de negocio vive en el servidor.
import type {
  ConfiguracionSimulacion,
  Cotizacion,
  DetalleAsignacion,
  Distrito,
  EstadoDescarga,
  EstadoSimulacion,
  Estadisticas,
  InfoConductor,
  PaginaAsignaciones,
  ResultadoGeocodificacion,
  ResultadoSolicitud,
  ResumenHistorico,
  SeguimientoViaje,
  ServicioActivo,
} from "./tipos";

export const URL_API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export function urlWebSocket(): string {
  if (URL_API) return URL_API.replace(/^http/, "ws") + "/ws/tiempo-real";
  const protocolo = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocolo}://${window.location.host}/ws/tiempo-real`;
}

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string) {
    super(mensaje);
  }
}

async function solicitar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(URL_API + ruta, {
      ...opciones,
      headers: { "Content-Type": "application/json", ...(opciones.headers ?? {}) },
    });
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el servidor");
  }
  if (!respuesta.ok) {
    let detalle = respuesta.statusText;
    try {
      const cuerpo = await respuesta.json();
      detalle = typeof cuerpo.detail === "string" ? cuerpo.detail : JSON.stringify(cuerpo.detail);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ErrorApi(respuesta.status, detalle);
  }
  return (await respuesta.json()) as T;
}

const json = (cuerpo: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(cuerpo) });

export const api = {
  salud: () => solicitar<Record<string, unknown>>("/api/salud"),
  distritos: () => solicitar<Distrito[]>("/api/distritos"),
  limitesDistritos: () => solicitar<GeoJSON.FeatureCollection>("/api/distritos/limites"),
  distrito: (id: string) => solicitar<{ distrito: Distrito; limite: GeoJSON.Feature; estado: EstadoDescarga }>(`/api/distritos/${id}`),
  estadoDescarga: (id: string) => solicitar<EstadoDescarga>(`/api/distritos/${id}/estado`),
  descargarDistrito: (id: string, forzar = false) =>
    solicitar<EstadoDescarga>(`/api/distritos/${id}/descargar?forzar=${forzar}`, { method: "POST" }),
  redVial: (id: string) => solicitar<GeoJSON.FeatureCollection>(`/api/distritos/${id}/red-vial`),

  simulacion: () => solicitar<EstadoSimulacion>("/api/simulacion"),
  configurar: (config: Partial<ConfiguracionSimulacion> & { id_distrito: string }) =>
    solicitar<EstadoSimulacion>("/api/simulacion/configurar", json(config)),
  parametros: (parametros: Partial<ConfiguracionSimulacion>) =>
    solicitar<EstadoSimulacion>("/api/simulacion/parametros", { method: "PATCH", body: JSON.stringify(parametros) }),
  controlar: (accion: string) => solicitar<EstadoSimulacion>(`/api/simulacion/${accion}`, { method: "POST" }),
  estadisticas: () => solicitar<{ simulacion: Estadisticas | null; historico: ResumenHistorico }>("/api/estadisticas"),
  configuraciones: () => solicitar<{ id: number; fecha: string; datos: ConfiguracionSimulacion }[]>("/api/simulacion/configuraciones"),

  conductor: (id: number) => solicitar<InfoConductor>(`/api/conductores/${id}`),
  serviciosActivos: () => solicitar<ServicioActivo[]>("/api/servicios/activos"),
  seguimiento: (idPasajero: number) => solicitar<SeguimientoViaje>(`/api/seguimiento/${idPasajero}`),

  cotizar: (origen: { latitud: number; longitud: number; direccion?: string }, destino: { latitud: number; longitud: number; direccion?: string }) =>
    solicitar<Cotizacion>("/api/solicitudes/cotizar", json({ origen, destino })),
  solicitar: (origen: { latitud: number; longitud: number; direccion?: string }, destino: { latitud: number; longitud: number; direccion?: string },
    idConductor?: number | null) =>
    solicitar<ResultadoSolicitud>("/api/solicitudes", json({ origen, destino, id_conductor: idConductor ?? null })),
  asignaciones: (parametros: { pagina?: number; tamano?: number; distrito?: string; estado?: string; origen?: string }) => {
    const q = new URLSearchParams();
    Object.entries(parametros).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, String(v)));
    return solicitar<PaginaAsignaciones>(`/api/asignaciones?${q}`);
  },
  asignacion: (id: number) => solicitar<DetalleAsignacion>(`/api/asignaciones/${id}`),
  urlMapaAsignacion: (id: number) => `${URL_API}/api/asignaciones/${id}/mapa`,

  geocodificar: (texto: string) => solicitar<ResultadoGeocodificacion[]>(`/api/geocodificar?q=${encodeURIComponent(texto)}`),
  geocodificarInversa: (lat: number, lon: number) =>
    solicitar<ResultadoGeocodificacion>(`/api/geocodificar/inversa?latitud=${lat}&longitud=${lon}`),

  benchmarks: () => solicitar<{ resultados: Record<string, any>; graficos: string[] }>("/api/benchmarks"),
  urlGrafico: (nombre: string) => `${URL_API}/api/benchmarks/graficos/${nombre}`,
};

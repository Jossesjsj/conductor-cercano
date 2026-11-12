// Tipos de los contratos de la API del backend (fuente de verdad: backend/api y backend/servicios).

export type EstadoConductor = "DISPONIBLE" | "OCUPADO" | "EN_SERVICIO" | "INACTIVO";
export const ESTADOS_CONDUCTOR: EstadoConductor[] = ["DISPONIBLE", "OCUPADO", "EN_SERVICIO", "INACTIVO"];
export const CODIGO_A_ESTADO: EstadoConductor[] = ["DISPONIBLE", "OCUPADO", "EN_SERVICIO", "INACTIVO"];

export interface Distrito {
  id_distrito: string;
  nombre: string;
  provincia: string;
  osm_id: number;
  area_km2: number;
  limites: [number, number, number, number];
  centro: [number, number];
  cobertura_completa: boolean;
  elegible: boolean;
  estado_descarga: string;
  descargado: boolean;
  nodos: number | null;
  aristas: number | null;
}

export interface EstadoDescarga {
  id_distrito: string;
  estado: "NO_DESCARGADO" | "EN_COLA" | "DESCARGANDO" | "PROCESANDO" | "LISTO" | "ERROR";
  mensaje: string;
  error: string;
  fuente: string;
  actualizado: string;
  descargado: boolean;
  metadatos: Record<string, unknown> | null;
}

export interface ConfiguracionSimulacion {
  id_distrito: string;
  cantidad_conductores: number;
  semilla: number;
  velocidad_promedio_kmh: number;
  variacion_velocidad: number;
  proporcion_inactivos: number;
  cantidad_candidatos: number;
  radio_inicial_metros: number;
  multiplicador_velocidad: number;
  intervalo_actualizacion_s: number;
  modo: "AUTOMATICO" | "MANUAL";
  solicitudes_por_minuto: number;
  tipo_visualizacion: "2D" | "3D";
  capacidad_quadtree: number;
}

export interface EstadoSimulacion {
  configurada: boolean;
  configurando: boolean;
  estado: "DETENIDA" | "EJECUTANDO" | "PAUSADA";
  id_configuracion?: number;
  configuracion?: ConfiguracionSimulacion;
  distrito?: Omit<Distrito, "estado_descarga" | "descargado" | "nodos" | "aristas"> | null;
  turno?: number;
  tiempo_simulado_s?: number;
  segundos_por_turno?: number;
  grafo?: { nodos: number; aristas: number; nodos_circulables: number; limites: [number, number, number, number] };
  quadtree?: { elementos: number; nodos: number; profundidad: number; capacidad: number };
}

export interface Estadisticas {
  estado_simulacion: string;
  modo: string;
  distrito: string;
  turno: number;
  tiempo_simulado_s: number;
  multiplicador_velocidad: number;
  conductores_totales: number;
  conductores_disponibles: number;
  conductores_ocupados: number;
  conductores_en_recogida: number;
  conductores_en_servicio: number;
  conductores_inactivos: number;
  pasajeros_activos: number;
  solicitudes_realizadas: number;
  asignaciones_exitosas: number;
  asignaciones_fallidas: number;
  asignaciones_completadas: number;
  eta_promedio_s: number | null;
  distancia_promedio_recogida_m: number | null;
  distancia_promedio_haversine_m: number | null;
  espera_real_promedio_s: number | null;
  duracion_turno_promedio_ms: number | null;
  ultima_duracion_turno_ms: number;
  actualizaciones_quadtree: number;
  nodos_quadtree: number | null;
  nodos_grafo: number;
  aristas_grafo: number;
  mensajes_ws?: number;
  clientes_ws?: number;
}

export interface ResumenHistorico {
  solicitudes: number;
  asignaciones: number;
  finalizadas: number;
  eta_promedio_s: number | null;
  distancia_promedio_recogida_m: number | null;
  por_distrito: Record<string, number>;
}

export interface Candidato {
  id_conductor: number;
  nombre: string;
  placa: string;
  velocidad_kmh: number;
  latitud: number;
  longitud: number;
  distancia_haversine_m: number;
  distancia_ruta_m: number | null;
  eta_segundos: number | null;
  eta_texto: string;
  nodos_explorados: number;
  valido: boolean;
  motivo: string;
  seleccionado: boolean;
}

export interface InfoConductor {
  id_conductor: number;
  nombre: string;
  latitud: number;
  longitud: number;
  rumbo: number;
  nodo_actual: number;
  nodo_siguiente: number;
  estado: EstadoConductor;
  velocidad_kmh: number;
  distancia_recorrida_m: number;
  id_pasajero_asignado: number | null;
  servicios_completados: number;
  id_vehiculo: string;
  vehiculo: { placa: string; marca: string; modelo: string; color: string; anio: number; capacidad_pasajeros: number };
  ruta_restante?: [number, number][];
}

export interface ResultadoSolicitud {
  exito: boolean;
  codigo: string;
  mensaje: string;
  id_asignacion: number | null;
  id_solicitud: number | null;
  pasajero: {
    id_pasajero: number;
    origen: { latitud: number; longitud: number; direccion: string };
    destino: { latitud: number; longitud: number; direccion: string };
    nodo_origen: number | null;
    nodo_destino: number | null;
    estado: string;
    fecha_solicitud: string;
    motivo_cancelacion?: string;
    id_conductor_asignado?: number | null;
  };
  candidatos: Candidato[];
  busqueda: { radio_final_m: number; iteraciones: number; elementos_examinados: number };
  tiempos_ms: Record<string, number>;
  fecha: string;
  conductor?: InfoConductor;
  distancia_haversine_m?: number;
  distancia_recogida_m?: number;
  eta_recogida_s?: number;
  eta_recogida_texto?: string;
  distancia_viaje_m?: number;
  duracion_viaje_s?: number;
  duracion_viaje_texto?: string;
  ruta_recogida?: [number, number][];
  ruta_viaje?: [number, number][];
  calles_recogida?: string[];
  calles_viaje?: string[];
  justificacion?: string;
  id_conductor_recomendado?: number | null;
  eleccion_usuario?: boolean;
  aviso?: string;
}

export interface ResumenAsignacion {
  id_asignacion: number;
  id_solicitud: number;
  id_pasajero: number;
  fecha: string;
  id_distrito: string;
  id_conductor: number;
  nombre_conductor: string;
  placa: string;
  candidatos_evaluados: number;
  distancia_haversine_m: number;
  distancia_ruta_m: number;
  eta_segundos: number;
  distancia_viaje_m: number;
  estado_servicio: string;
  origen_solicitud: string;
  direccion_origen: string;
  direccion_destino: string;
}

export interface DetalleAsignacion extends ResumenAsignacion {
  velocidad_kmh: number;
  candidatos: Candidato[];
  duracion_viaje_s: number;
  ruta_recogida: [number, number][];
  ruta_viaje: [number, number][];
  calles_recogida: string[];
  conductores_contexto: [number, number, number, EstadoConductor][];
  justificacion: string;
  radio_busqueda_m: number;
  iteraciones_busqueda: number;
  elementos_examinados: number;
  tiempos_ms: Record<string, number>;
  turno_asignacion: number;
  espera_real_s: number | null;
  fecha_recogida: string | null;
  fecha_finalizacion: string | null;
  pasajero: { origen: [number, number]; destino: [number, number]; nodo_origen: number; nodo_destino: number; estado: string };
}

export interface PaginaAsignaciones {
  total: number;
  pagina: number;
  tamano: number;
  elementos: ResumenAsignacion[];
}

export interface ServicioActivo {
  id_pasajero: number;
  id_conductor: number;
  id_asignacion: number | null;
  estado_pasajero: string;
  estado_conductor: EstadoConductor;
  fase: "recogida" | "viaje";
  origen: [number, number];
  destino: [number, number];
  ruta_restante: [number, number][];
  ruta_viaje: [number, number][];
}

export interface ResultadoGeocodificacion {
  nombre: string;
  latitud: number;
  longitud: number;
  tipo?: string;
}

export type FaseViaje = "recogida" | "viaje" | "finalizado" | "cancelado";

export interface SeguimientoViaje {
  fase: FaseViaje;
  pasajero: ResultadoSolicitud["pasajero"];
  turno: number;
  tiempo_simulado_s: number;
  estado_simulacion: "DETENIDA" | "EJECUTANDO" | "PAUSADA";
  modo: "AUTOMATICO" | "MANUAL";
  multiplicador_velocidad: number;
  distancia_recogida_m: number | null;
  distancia_viaje_m: number | null;
  eta_recogida_s: number | null;
  espera_real_s: number | null;
  duracion_viaje_s: number | null;
  transcurrido_s: number | null;
  conductor: InfoConductor | null;
  distancia_restante_m: number;
  eta_restante_s: number;
  ruta_restante: [number, number][];
  ruta_viaje: [number, number][];
  id_configuracion: number | null;
  id_asignacion: number | null;
}

export interface CandidatoCotizado extends Omit<Candidato, "seleccionado"> {
  recomendado: boolean;
  vehiculo?: InfoConductor["vehiculo"];
  ruta_recogida: [number, number][];
}

export interface Cotizacion {
  exito: boolean;
  codigo: string;
  mensaje: string;
  disponibles_totales: number;
  disponibles_cercanos: number;
  radio_cercania_m: number;
  cercanos: [number, number, number][];
  candidatos: CandidatoCotizado[];
  id_conductor_recomendado: number | null;
  ruta_viaje: [number, number][];
  distancia_viaje_m: number | null;
  duracion_viaje_estimada_s: number | null;
  busqueda: { radio_final_m: number; elementos_examinados: number };
  tiempos_ms: Record<string, number>;
  estado_simulacion: "DETENIDA" | "EJECUTANDO" | "PAUSADA";
  multiplicador_velocidad: number;
}

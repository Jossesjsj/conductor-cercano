export const formatoNumero = (n: number | null | undefined, decimales = 0) =>
  n === null || n === undefined || Number.isNaN(n) ? "—" : n.toLocaleString("es-PE", { maximumFractionDigits: decimales, minimumFractionDigits: decimales });

export function formatoDistancia(metros: number | null | undefined): string {
  if (metros === null || metros === undefined) return "—";
  return metros >= 1000 ? `${formatoNumero(metros / 1000, 2)} km` : `${formatoNumero(metros, 0)} m`;
}

export function formatoDuracion(segundos: number | null | undefined): string {
  if (segundos === null || segundos === undefined) return "—";
  const s = Math.round(segundos);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${String(s % 60).padStart(2, "0")} s`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

export function formatoFecha(iso: string): string {
  const fecha = new Date(iso);
  return fecha.toLocaleString("es-PE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const ETIQUETA_ESTADO: Record<string, string> = {
  DISPONIBLE: "Disponible",
  OCUPADO: "En recogida",
  EN_SERVICIO: "En servicio",
  INACTIVO: "Inactivo",
  CONDUCTOR_ASIGNADO: "Asignado",
  VIAJANDO: "Viajando",
  FINALIZADO: "Finalizado",
  CANCELADO: "Cancelado",
  INTERRUMPIDO: "Interrumpido",
  ESPERANDO: "Esperando",
  RECOGIDO: "Recogido",
  EJECUTANDO: "En ejecución",
  PAUSADA: "Pausada",
  DETENIDA: "Detenida",
  AUTOMATICO: "Automático",
  MANUAL: "Manual",
};

// Búfer mutable de posiciones de la flota visible (fuera de React para no re-renderizar
// la interfaz completa en cada turno). Guarda posición anterior y objetivo para interpolar.
import { CODIGO_A_ESTADO, type EstadoConductor } from "@/services/tipos";

export interface VehiculoVisual {
  id: number;
  lat: number;
  lon: number;
  rumbo: number;
  estado: EstadoConductor;
  latPrevia: number;
  lonPrevia: number;
  rumboPrevio: number;
  inicio: number; // ms (performance.now) en que comenzó la transición
}

type Oyente = () => void;

class FlotaVisual {
  vehiculos = new Map<number, VehiculoVisual>();
  duracionTransicion = 500;
  totalEnVista = 0;
  mostrados = 0;
  turno = 0;
  private oyentes = new Set<Oyente>();

  aplicarDelta(actualizados: [number, number, number, number, number][], eliminados: number[], total: number, mostrados: number, turno: number) {
    const ahora = performance.now();
    for (const id of eliminados) this.vehiculos.delete(id);
    for (const [id, lat, lon, rumbo, codigo] of actualizados) {
      const estado = CODIGO_A_ESTADO[codigo] ?? "DISPONIBLE";
      const existente = this.vehiculos.get(id);
      if (existente) {
        const [latActual, lonActual, rumboActual] = this.interpolar(existente, ahora);
        // Saltos grandes (p. ej. reinicio de flota) no se animan.
        const salto = Math.abs(latActual - lat) + Math.abs(lonActual - lon) > 0.004;
        existente.latPrevia = salto ? lat : latActual;
        existente.lonPrevia = salto ? lon : lonActual;
        existente.rumboPrevio = salto ? rumbo : rumboActual;
        existente.lat = lat;
        existente.lon = lon;
        existente.rumbo = rumbo;
        existente.estado = estado;
        existente.inicio = ahora;
      } else {
        this.vehiculos.set(id, { id, lat, lon, rumbo, estado, latPrevia: lat, lonPrevia: lon, rumboPrevio: rumbo, inicio: ahora });
      }
    }
    this.totalEnVista = total;
    this.mostrados = mostrados;
    this.turno = turno;
    this.oyentes.forEach((o) => o());
  }

  interpolar(v: VehiculoVisual, ahora: number): [number, number, number] {
    const f = Math.min(1, Math.max(0, (ahora - v.inicio) / this.duracionTransicion));
    let delta = v.rumbo - v.rumboPrevio;
    if (delta > 180) delta -= 360;
    if (delta < -180) delta += 360;
    return [v.latPrevia + (v.lat - v.latPrevia) * f, v.lonPrevia + (v.lon - v.lonPrevia) * f, v.rumboPrevio + delta * f];
  }

  limpiar() {
    this.vehiculos.clear();
    this.oyentes.forEach((o) => o());
  }

  suscribir(oyente: Oyente): () => void {
    this.oyentes.add(oyente);
    return () => this.oyentes.delete(oyente);
  }
}

export const flotaVisual = new FlotaVisual();

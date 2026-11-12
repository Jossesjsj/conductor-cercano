// Cliente WebSocket con reconexión automática (backoff exponencial) y vista del mapa.
import { urlWebSocket } from "./api";
import { flotaVisual } from "@/stores/flotaVisual";
import { usarAlmacen } from "@/stores/almacen";
import type { EstadoSimulacion, Estadisticas, ResultadoSolicitud } from "./tipos";

type Vista = { limites: [number, number, number, number]; zoom: number };

class ClienteTiempoReal {
  private ws: WebSocket | null = null;
  private espera = 1000;
  private temporizador: number | undefined;
  private latido: number | undefined;
  private vista: Vista | null = null;
  private activo = false;

  iniciar() {
    if (this.activo) return;
    this.activo = true;
    this.conectar();
  }

  detener() {
    this.activo = false;
    window.clearTimeout(this.temporizador);
    window.clearInterval(this.latido);
    const ws = this.ws;
    this.ws = null;
    ws?.close();
  }

  fijarVista(vista: Vista) {
    this.vista = vista;
    this.enviar({ tipo: "vista", ...vista, intervalo_minimo_ms: 150 });
  }

  sincronizar() {
    this.enviar({ tipo: "sincronizar" });
  }

  private enviar(mensaje: object) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(mensaje));
  }

  private conectar() {
    const almacen = usarAlmacen.getState();
    almacen.fijarConexion("conectando");
    const ws = new WebSocket(urlWebSocket());
    this.ws = ws;
    ws.onopen = () => {
      if (ws !== this.ws) return ws.close();
      this.espera = 1000;
      usarAlmacen.getState().fijarConexion("conectado");
      // El servidor tiene una caché nueva por conexión: se reinicia el búfer local.
      flotaVisual.limpiar();
      if (this.vista) this.fijarVista(this.vista);
      window.clearInterval(this.latido);
      this.latido = window.setInterval(() => this.enviar({ tipo: "ping", t: Date.now() }), 20000);
    };
    ws.onmessage = (evento) => {
      if (ws === this.ws) this.procesar(JSON.parse(evento.data));
    };
    ws.onclose = () => {
      if (ws !== this.ws) return; // cierre de una conexión ya reemplazada
      window.clearInterval(this.latido);
      usarAlmacen.getState().fijarConexion("desconectado");
      if (!this.activo) return;
      this.temporizador = window.setTimeout(() => this.conectar(), this.espera);
      this.espera = Math.min(15000, this.espera * 2);
    };
    ws.onerror = () => ws.close();
  }

  private procesar(m: any) {
    const a = usarAlmacen.getState();
    switch (m.tipo) {
      case "bienvenida":
        a.fijarSimulacion(m.simulacion as EstadoSimulacion);
        break;
      case "posiciones":
        flotaVisual.aplicarDelta(m.actualizados, m.eliminados, m.total_en_vista, m.mostrados, m.turno);
        break;
      case "estadisticas":
        a.fijarEstadisticas(m.datos as Estadisticas);
        break;
      case "simulacion": {
        const s = m.datos as EstadoSimulacion;
        const previo = a.simulacion;
        if (previo?.id_configuracion !== s.id_configuracion || (s.turno === 0 && (previo?.turno ?? 0) > 0)) a.reiniciarVista();
        a.fijarSimulacion(s);
        const intervalo = s.configuracion?.intervalo_actualizacion_s;
        if (intervalo) flotaVisual.duracionTransicion = Math.min(1500, intervalo * 1000);
        break;
      }
      case "asignacion": {
        const r = m.datos as ResultadoSolicitud;
        a.registrarAsignacion(r);
        a.agregarEvento("asignacion", `Pasajero ${r.pasajero.id_pasajero} → conductor ${r.conductor?.id_conductor} · ETA ${r.eta_recogida_texto}`);
        break;
      }
      case "solicitud_rechazada": {
        const r = m.datos as ResultadoSolicitud;
        a.registrarAsignacion(r);
        a.agregarEvento("rechazo", `Solicitud ${r.pasajero.id_pasajero} rechazada: ${r.mensaje}`);
        break;
      }
      case "recogida":
        a.marcarRecogida(m.id_pasajero);
        a.agregarEvento("recogida", `Conductor ${m.id_conductor} recogió al pasajero ${m.id_pasajero} (espera ${m.espera_real_s} s)`);
        break;
      case "finalizacion":
        a.finalizarRuta(m.id_pasajero);
        a.agregarEvento("finalizacion", `Viaje del pasajero ${m.id_pasajero} finalizado (${m.duracion_total_s} s)`);
        break;
    }
  }
}

export const tiempoReal = new ClienteTiempoReal();

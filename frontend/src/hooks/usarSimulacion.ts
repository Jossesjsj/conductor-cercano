import { useCallback, useEffect, useState } from "react";
import { api, ErrorApi } from "@/services/api";
import { tiempoReal } from "@/services/tiempoReal";
import { usarAlmacen } from "@/stores/almacen";
import { notificar } from "@/stores/notificaciones";

/** Conexión en tiempo real + sondeo de respaldo cuando el WebSocket está caído. */
export function usarSincronizacion() {
  const conexion = usarAlmacen((s) => s.conexion);
  useEffect(() => {
    tiempoReal.iniciar();
    return () => tiempoReal.detener();
  }, []);
  useEffect(() => {
    const actualizar = () => {
      api.simulacion().then((s) => usarAlmacen.getState().fijarSimulacion(s)).catch(() => undefined);
      if (usarAlmacen.getState().conexion !== "conectado") {
        api.estadisticas().then((e) => e.simulacion && usarAlmacen.getState().fijarEstadisticas(e.simulacion)).catch(() => undefined);
      }
    };
    actualizar();
    const t = window.setInterval(actualizar, conexion === "conectado" ? 8000 : 3000);
    return () => window.clearInterval(t);
  }, [conexion]);
}

const MENSAJES: Record<string, string> = {
  iniciar: "Simulación iniciada",
  pausar: "Simulación pausada",
  reanudar: "Simulación reanudada",
  avanzar: "Turno ejecutado",
  reiniciar: "Simulación reiniciada con la misma semilla",
  acelerar: "Velocidad aumentada",
  desacelerar: "Velocidad reducida",
  detener: "Simulación detenida",
  modo: "Modo de simulación cambiado",
};

export function usarControlSimulacion() {
  const [ocupado, setOcupado] = useState<string | null>(null);
  const ejecutar = useCallback(async (accion: string) => {
    setOcupado(accion);
    try {
      const estado = await api.controlar(accion);
      usarAlmacen.getState().fijarSimulacion(estado);
      if (accion !== "avanzar") notificar("info", MENSAJES[accion] ?? accion);
    } catch (error) {
      notificar("error", error instanceof ErrorApi ? error.message : "Error al controlar la simulación");
    } finally {
      setOcupado(null);
    }
  }, []);
  return { ejecutar, ocupado };
}

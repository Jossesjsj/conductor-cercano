import { useEffect, useRef, useState } from "react";
import { api, ErrorApi } from "@/services/api";
import type { SeguimientoViaje } from "@/services/tipos";

export const INTERVALO_SEGUIMIENTO_MS = 700;

/** Sondea el estado en vivo de un viaje hasta que finaliza (o deja de existir). */
export function usarSeguimiento(idPasajero: number | null) {
  const [datos, setDatos] = useState<SeguimientoViaje | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activo = useRef(true);

  useEffect(() => {
    activo.current = true;
    setDatos(null);
    setError(null);
    if (idPasajero === null) return;
    let temporizador: number | undefined;
    const consultar = async () => {
      try {
        const s = await api.seguimiento(idPasajero);
        if (!activo.current) return;
        setDatos(s);
        setError(null);
        if (s.fase === "finalizado" || s.fase === "cancelado") return; // fin del viaje: deja de sondear
      } catch (e) {
        if (!activo.current) return;
        if (e instanceof ErrorApi && e.estado === 404) {
          setError(e.message);
          return;
        }
        setError("Sin conexión con el servidor; reintentando…");
      }
      temporizador = window.setTimeout(consultar, INTERVALO_SEGUIMIENTO_MS);
    };
    consultar();
    return () => {
      activo.current = false;
      window.clearTimeout(temporizador);
    };
  }, [idPasajero]);

  return { datos, error };
}

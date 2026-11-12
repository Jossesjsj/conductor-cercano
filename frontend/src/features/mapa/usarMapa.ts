// Crea una instancia de MapLibre con el estilo vectorial y respaldo ráster automático.
import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { ESTILO_PRINCIPAL, ESTILO_RESPALDO, afinarEstilo } from "./estiloBase";

export interface OpcionesMapa {
  centro?: [number, number];
  zoom?: number;
  interactivo?: boolean;
  alCargar?: (map: maplibregl.Map) => void;
}

export function usarMapa(contenedor: React.RefObject<HTMLDivElement>, opciones: OpcionesMapa = {}) {
  const [mapa, setMapa] = useState<maplibregl.Map | null>(null);
  const [usaRespaldo, setUsaRespaldo] = useState(false);
  const alCargar = useRef(opciones.alCargar);
  alCargar.current = opciones.alCargar;

  useEffect(() => {
    if (!contenedor.current) return;
    let cargado = false;
    let respaldoAplicado = false;
    const map = new maplibregl.Map({
      container: contenedor.current,
      style: ESTILO_PRINCIPAL,
      center: opciones.centro ?? [-77.03, -12.12],
      zoom: opciones.zoom ?? 13.5,
      maxPitch: 75,
      attributionControl: { compact: true },
      interactive: opciones.interactivo ?? true,
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    map.on("styleimagemissing", (e) => {
      if (!map.hasImage(e.id)) map.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) });
    });
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

    const aplicarRespaldo = () => {
      if (cargado || respaldoAplicado) return;
      respaldoAplicado = true;
      setUsaRespaldo(true);
      map.setStyle(ESTILO_RESPALDO);
    };
    const temporizador = window.setTimeout(aplicarRespaldo, 9000);
    map.on("error", (e) => {
      if (!cargado && /style|fetch|Failed/i.test(String(e.error?.message ?? ""))) aplicarRespaldo();
    });
    map.once("load", () => {
      cargado = true;
      window.clearTimeout(temporizador);
      if (!respaldoAplicado) afinarEstilo(map);
      alCargar.current?.(map);
      setMapa(map);
    });
    map.on("style.load", () => {
      if (respaldoAplicado && !cargado) {
        cargado = true;
        window.clearTimeout(temporizador);
        alCargar.current?.(map);
        setMapa(map);
      }
    });
    // El contenedor puede cambiar de tamaño (paneles, transiciones): se redimensiona el lienzo.
    const observador = new ResizeObserver(() => map.resize());
    observador.observe(contenedor.current);
    return () => {
      observador.disconnect();
      window.clearTimeout(temporizador);
      map.remove();
      setMapa(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { mapa, usaRespaldo };
}

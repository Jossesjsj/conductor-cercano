import { useEffect, useRef, useState } from "react";
import { Crosshair, Loader2, MapPin, Search } from "lucide-react";
import { api, ErrorApi } from "@/services/api";
import type { ResultadoGeocodificacion } from "@/services/tipos";

export interface Ubicacion {
  latitud: number;
  longitud: number;
  direccion: string;
}

interface Props {
  etiqueta: string;
  color: string;
  valor: Ubicacion | null;
  alCambiar: (u: Ubicacion | null) => void;
  seleccionandoEnMapa: boolean;
  alSeleccionarEnMapa: () => void;
}

/** Dirección (Nominatim vía backend), selección en el mapa o coordenadas directas. */
export function SelectorUbicacion({ etiqueta, color, valor, alCambiar, seleccionandoEnMapa, alSeleccionarEnMapa }: Props) {
  const [texto, setTexto] = useState("");
  const [sugerencias, setSugerencias] = useState<ResultadoGeocodificacion[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const temporizador = useRef<number>();

  useEffect(() => {
    if (valor) {
      setLat(valor.latitud.toFixed(6));
      setLon(valor.longitud.toFixed(6));
      if (valor.direccion) setTexto(valor.direccion);
    }
  }, [valor]);

  const buscar = (consulta: string) => {
    setTexto(consulta);
    setError(null);
    window.clearTimeout(temporizador.current);
    if (consulta.trim().length < 3) {
      setSugerencias([]);
      return;
    }
    // Espera de 700 ms tras dejar de escribir: respeta el límite de 1 solicitud/s de Nominatim.
    temporizador.current = window.setTimeout(async () => {
      setBuscando(true);
      try {
        setSugerencias(await api.geocodificar(consulta));
      } catch (e) {
        setSugerencias([]);
        setError(e instanceof ErrorApi ? e.message : "Geocodificación no disponible");
      } finally {
        setBuscando(false);
      }
    }, 700);
  };

  const aplicarCoordenadas = () => {
    const la = Number(lat);
    const lo = Number(lon);
    if (!Number.isFinite(la) || !Number.isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) {
      setError("Coordenadas inválidas");
      return;
    }
    setError(null);
    alCambiar({ latitud: la, longitud: lo, direccion: texto || `${la.toFixed(5)}, ${lo.toFixed(5)}` });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium text-slate-100"><span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />{etiqueta}</span>
        <button type="button" onClick={alSeleccionarEnMapa} className={`boton h-7 px-2 text-xs ${seleccionandoEnMapa ? "bg-cyan-500/20 text-cyan-200 ring-1 ring-cyan-400/40" : "text-slate-300 hover:bg-slate-800"}`}>
          <Crosshair size={13} /> {seleccionandoEnMapa ? "Haga clic en el mapa" : "Elegir en el mapa"}
        </button>
      </div>
      <div className="relative">
        <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input className="campo pl-9" placeholder="Buscar dirección (p. ej. Av. Larco 1150, Miraflores)" value={texto} onChange={(e) => buscar(e.target.value)} />
        {buscando && <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-slate-400" />}
        {sugerencias.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-lg border border-slate-700 bg-panel-solido shadow-panel">
            {sugerencias.map((s) => (
              <li key={`${s.latitud},${s.longitud}`}>
                <button type="button" className="flex w-full items-start gap-2 px-3 py-2 text-left text-xs text-slate-300 hover:bg-slate-800"
                  onClick={() => { alCambiar({ latitud: s.latitud, longitud: s.longitud, direccion: s.nombre }); setTexto(s.nombre); setSugerencias([]); }}>
                  <MapPin size={13} className="mt-0.5 shrink-0 text-slate-500" /> {s.nombre}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="grid grid-cols-[1fr_1fr_auto] gap-2">
        <input className="campo num text-xs" placeholder="Latitud" value={lat} onChange={(e) => setLat(e.target.value)} />
        <input className="campo num text-xs" placeholder="Longitud" value={lon} onChange={(e) => setLon(e.target.value)} />
        <button type="button" className="boton-secundario text-xs" onClick={aplicarCoordenadas}>Usar</button>
      </div>
      {error && <p className="text-[11px] text-amber-300">{error}</p>}
    </div>
  );
}

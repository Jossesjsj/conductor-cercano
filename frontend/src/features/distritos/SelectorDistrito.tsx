import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, CloudDownload, Loader2, RefreshCw, Search, TriangleAlert } from "lucide-react";
import { api, ErrorApi } from "@/services/api";
import type { Distrito, EstadoDescarga } from "@/services/tipos";
import { notificar } from "@/stores/notificaciones";
import { formatoNumero } from "@/components/ui/formato";

interface Props {
  seleccionado: string;
  alSeleccionar: (id: string) => void;
}

const EN_CURSO = ["EN_COLA", "DESCARGANDO", "PROCESANDO"];

export function SelectorDistrito({ seleccionado, alSeleccionar }: Props) {
  const [distritos, setDistritos] = useState<Distrito[]>([]);
  const [progreso, setProgreso] = useState<Record<string, EstadoDescarga>>({});
  const [texto, setTexto] = useState("");
  const sondeo = useRef<number>();

  const cargar = () => api.distritos().then(setDistritos).catch(() => notificar("error", "No se pudo cargar el catálogo de distritos"));
  useEffect(() => {
    cargar();
  }, []);

  // Sondeo del estado de las descargas en curso.
  useEffect(() => {
    const pendientes = Object.values(progreso).filter((p) => EN_CURSO.includes(p.estado));
    window.clearInterval(sondeo.current);
    if (!pendientes.length) return;
    sondeo.current = window.setInterval(async () => {
      for (const p of pendientes) {
        const estado = await api.estadoDescarga(p.id_distrito).catch(() => null);
        if (!estado) continue;
        setProgreso((actual) => ({ ...actual, [p.id_distrito]: estado }));
        if (estado.estado === "LISTO") {
          notificar("exito", `Red vial de ${p.id_distrito} lista (${estado.mensaje})`);
          cargar();
        } else if (estado.estado === "ERROR") notificar("error", `Error al descargar ${p.id_distrito}: ${estado.error}`);
      }
    }, 1500);
    return () => window.clearInterval(sondeo.current);
  }, [progreso]);

  const descargar = async (id: string, forzar: boolean) => {
    try {
      const estado = await api.descargarDistrito(id, forzar);
      setProgreso((p) => ({ ...p, [id]: estado }));
      if (estado.estado === "LISTO" && !forzar) notificar("info", estado.mensaje);
    } catch (e) {
      notificar("error", e instanceof ErrorApi ? e.message : "No se pudo iniciar la descarga");
    }
  };

  const grupos = useMemo(() => {
    const filtro = texto.trim().toLowerCase();
    const visibles = distritos.filter((d) => !filtro || d.nombre.toLowerCase().includes(filtro));
    return ["Lima Metropolitana", "Callao"].map((p) => ({ provincia: p, lista: visibles.filter((d) => d.provincia === p) }));
  }, [distritos, texto]);

  return (
    <div className="flex h-full flex-col">
      <div className="relative border-b border-panel-borde p-3">
        <Search size={14} className="absolute left-6 top-1/2 -translate-y-1/2 text-slate-500" />
        <input className="campo pl-9" placeholder="Buscar distrito…" value={texto} onChange={(e) => setTexto(e.target.value)} />
      </div>
      <div className="flex-1 overflow-y-auto">
        {grupos.map(({ provincia, lista }) => (
          <div key={provincia}>
            <div className="sticky top-0 z-10 bg-fondo-2/95 px-4 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500 backdrop-blur">{provincia} · {lista.length}</div>
            {lista.map((d) => {
              const p = progreso[d.id_distrito];
              const enCurso = p && EN_CURSO.includes(p.estado);
              const activo = d.id_distrito === seleccionado;
              return (
                <div key={d.id_distrito} onClick={() => d.elegible && alSeleccionar(d.id_distrito)}
                  className={`group flex items-center gap-3 border-l-2 px-4 py-2.5 transition ${activo ? "border-cyan-400 bg-cyan-500/[0.07]" : "border-transparent"} ${d.elegible ? "cursor-pointer hover:bg-slate-800/40" : "opacity-45"}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-sm text-slate-100">
                      {d.nombre}
                      {d.descargado && <CheckCircle2 size={13} className="text-green-400" />}
                    </div>
                    <div className="num text-[11px] text-slate-500">
                      {formatoNumero(d.area_km2, 2)} km²
                      {d.nodos ? ` · ${formatoNumero(d.nodos)} nodos · ${formatoNumero(d.aristas)} aristas` : ""}
                      {!d.elegible && (d.area_km2 < 3 ? " · menor a 3 km²" : " · fuera de la cobertura del extracto")}
                    </div>
                    {p && (enCurso || p.estado === "ERROR") && (
                      <div className={`mt-1 flex items-center gap-1.5 text-[11px] ${p.estado === "ERROR" ? "text-red-300" : "text-cyan-300"}`}>
                        {p.estado === "ERROR" ? <TriangleAlert size={12} /> : <Loader2 size={12} className="animate-spin" />}
                        {p.estado === "ERROR" ? p.error : p.mensaje}
                      </div>
                    )}
                  </div>
                  {d.elegible && (
                    <button disabled={enCurso} onClick={(e) => { e.stopPropagation(); descargar(d.id_distrito, d.descargado); }}
                      title={d.descargado ? "Actualizar red vial (volver a descargar)" : "Descargar red vial"}
                      className="boton-fantasma h-8 px-2 text-xs opacity-70 group-hover:opacity-100">
                      {enCurso ? <Loader2 size={14} className="animate-spin" /> : d.descargado ? <RefreshCw size={14} /> : <CloudDownload size={14} />}
                      {!d.descargado && !enCurso && "Descargar"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

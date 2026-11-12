// Paso intermedio: muestra cuántos conductores hay disponibles y los candidatos con su ETA
// real (Quadtree + Haversine + Dijkstra). El recomendado (menor ETA) viene preseleccionado;
// el pasajero puede confirmar ese u otro.
import { motion } from "framer-motion";
import { ArrowLeft, CarFront, CheckCircle2, CircleSlash, Loader2, RefreshCw, Sparkles, Star } from "lucide-react";
import type { CandidatoCotizado, Cotizacion } from "@/services/tipos";
import { formatoDistancia, formatoDuracion, formatoNumero } from "@/components/ui/formato";

interface Props {
  cotizacion: Cotizacion;
  elegido: number | null;
  alElegir: (id: number) => void;
  alConfirmar: () => void;
  alVolver: () => void;
  alActualizar: () => void;
  confirmando: boolean;
  actualizando: boolean;
}

function iniciales(nombre: string) {
  return nombre.split(" ").map((p) => p[0]).join("").slice(0, 2);
}

function TarjetaCandidato({ c, activo, alElegir, etaMinimo }: { c: CandidatoCotizado; activo: boolean; alElegir: () => void; etaMinimo: number }) {
  const diferencia = c.eta_segundos !== null ? c.eta_segundos - etaMinimo : null;
  return (
    <motion.button layout type="button" disabled={!c.valido} onClick={alElegir}
      className={`w-full rounded-xl border p-3 text-left transition ${
        !c.valido ? "cursor-not-allowed border-slate-800 opacity-50"
          : activo ? "border-cyan-400/60 bg-cyan-500/[0.08] shadow-brillo" : "border-panel-borde bg-slate-900/40 hover:border-slate-500"}`}>
      <div className="flex items-center gap-3">
        <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-full text-sm font-semibold ${activo ? "bg-gradient-to-br from-blue-600 to-cyan-500 text-white" : "bg-slate-800 text-cyan-200"}`}>
          {iniciales(c.nombre)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5 text-sm text-slate-100">
            {c.nombre}
            {c.recomendado && (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-500/15 px-1.5 py-0.5 text-[10px] font-medium text-green-300 ring-1 ring-green-500/30">
                <Star size={10} /> Recomendado · menor ETA
              </span>
            )}
          </div>
          <div className="truncate text-[11px] text-slate-400">
            {c.vehiculo ? `${c.vehiculo.marca} ${c.vehiculo.modelo} · ${c.vehiculo.color} · ` : ""}{c.placa} · {c.velocidad_kmh} km/h
          </div>
        </div>
        <div className="text-right">
          {c.valido ? (
            <>
              <div className="num text-base font-semibold text-white">{formatoDuracion(c.eta_segundos)}</div>
              <div className="num text-[10px] text-slate-500">{diferencia && diferencia > 0.5 ? `+${formatoDuracion(diferencia)}` : "el más rápido"}</div>
            </>
          ) : (
            <span className="flex items-center gap-1 text-[11px] text-slate-500"><CircleSlash size={12} /> Sin ruta</span>
          )}
        </div>
        {activo && <CheckCircle2 size={18} className="shrink-0 text-cyan-300" />}
      </div>
      <div className="num mt-2 flex gap-4 pl-[52px] text-[11px] text-slate-400">
        <span>Por calles: <b className="text-slate-200">{c.valido ? formatoDistancia(c.distancia_ruta_m) : "—"}</b></span>
        <span>Línea recta: <b className="text-slate-200">{formatoDistancia(c.distancia_haversine_m)}</b></span>
      </div>
    </motion.button>
  );
}

export function ElegirConductor({ cotizacion: cot, elegido, alElegir, alConfirmar, alVolver, alActualizar, confirmando, actualizando }: Props) {
  const validos = cot.candidatos.filter((c) => c.valido);
  const etaMinimo = Math.min(...validos.map((c) => c.eta_segundos ?? Infinity));
  const seleccionado = cot.candidatos.find((c) => c.id_conductor === elegido);
  return (
    <div className="space-y-4 p-5">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-panel-borde bg-slate-900/50 p-3">
          <div className="etiqueta">Disponibles en el distrito</div>
          <div className="num mt-1 text-2xl font-semibold text-green-400">{formatoNumero(cot.disponibles_totales)}</div>
        </div>
        <div className="rounded-xl border border-panel-borde bg-slate-900/50 p-3">
          <div className="etiqueta">A menos de {formatoDistancia(cot.radio_cercania_m)}</div>
          <div className="num mt-1 text-2xl font-semibold text-cyan-300">{formatoNumero(cot.disponibles_cercanos)}</div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-medium text-slate-100">Elige tu conductor</div>
          <div className="text-[11px] text-slate-500">
            Los {cot.candidatos.length} disponibles más cercanos, con su tiempo real de llegada por las calles
          </div>
        </div>
        <button className="boton-fantasma h-8 px-2 text-xs" onClick={alActualizar} disabled={actualizando} title="Actualizar posiciones">
          <RefreshCw size={13} className={actualizando ? "animate-spin" : ""} />
        </button>
      </div>

      <div className="space-y-2">
        {cot.candidatos.map((c) => (
          <TarjetaCandidato key={c.id_conductor} c={c} activo={c.id_conductor === elegido} etaMinimo={etaMinimo} alElegir={() => alElegir(c.id_conductor)} />
        ))}
      </div>

      <div className="rounded-xl border border-panel-borde bg-slate-900/40 px-4 py-3 text-xs text-slate-400">
        Tu viaje: <b className="text-slate-200">{formatoDistancia(cot.distancia_viaje_m)}</b> · aprox. <b className="text-slate-200">{formatoDuracion(cot.duracion_viaje_estimada_s)}</b> por la ruta más corta
      </div>

      <div className="flex gap-2">
        <button className="boton-secundario" onClick={alVolver} disabled={confirmando}><ArrowLeft size={14} /> Cambiar</button>
        <button className="boton-primario flex-1 py-2.5" onClick={alConfirmar} disabled={!seleccionado || confirmando}>
          {confirmando ? <Loader2 size={15} className="animate-spin" /> : seleccionado?.recomendado ? <Sparkles size={15} /> : <CarFront size={15} />}
          {seleccionado ? `Confirmar a ${seleccionado.nombre.split(" ")[0]} · llega en ${formatoDuracion(seleccionado.eta_segundos)}` : "Elige un conductor"}
        </button>
      </div>
      <p className="text-[11px] leading-relaxed text-slate-500">
        También puedes tocar un candidato en el mapa. Las posiciones se actualizan solas mientras eliges; si tu elegido acepta otro viaje antes de confirmar, se te asignará el mejor disponible.
      </p>
    </div>
  );
}

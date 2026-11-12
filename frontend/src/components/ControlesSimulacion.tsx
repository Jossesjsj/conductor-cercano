import { FastForward, Gauge, Pause, Play, RotateCcw, Rewind, SkipForward, Square } from "lucide-react";
import { usarControlSimulacion } from "@/hooks/usarSimulacion";
import { usarAlmacen } from "@/stores/almacen";
import { formatoDuracion } from "./ui/formato";

export function ControlesSimulacion({ compacto = false }: { compacto?: boolean }) {
  const simulacion = usarAlmacen((s) => s.simulacion);
  const { ejecutar, ocupado } = usarControlSimulacion();
  const estado = simulacion?.estado ?? "DETENIDA";
  const deshabilitado = !simulacion?.configurada || simulacion.configurando;
  const multiplicador = simulacion?.configuracion?.multiplicador_velocidad ?? 1;

  const boton = (accion: string, Icono: typeof Play, titulo: string, extra = "") => (
    <button key={accion} title={titulo} aria-label={titulo} disabled={deshabilitado || ocupado !== null} onClick={() => ejecutar(accion)}
      className={`boton-secundario h-9 px-2.5 ${extra}`}>
      <Icono size={15} />
      {!compacto && <span className="hidden xl:inline">{titulo}</span>}
    </button>
  );

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {estado === "EJECUTANDO"
        ? boton("pausar", Pause, "Pausar", "border-amber-500/40 text-amber-200")
        : estado === "PAUSADA"
          ? boton("reanudar", Play, "Reanudar", "border-green-500/40 text-green-300")
          : boton("iniciar", Play, "Iniciar", "border-green-500/40 text-green-300")}
      {boton("avanzar", SkipForward, "Avanzar un turno")}
      {boton("desacelerar", Rewind, "Disminuir velocidad")}
      <span className="num inline-flex h-9 items-center gap-1 rounded-lg border border-slate-700/70 bg-slate-900/60 px-2.5 text-xs text-cyan-300" title="Multiplicador de velocidad">
        <Gauge size={13} /> ×{multiplicador}
      </span>
      {boton("acelerar", FastForward, "Aumentar velocidad")}
      {boton("reiniciar", RotateCcw, "Reiniciar")}
      {!compacto && boton("detener", Square, "Detener")}
      {!compacto && simulacion?.configurada && (
        <span className="num ml-1 text-xs text-slate-400">
          Turno {simulacion.turno ?? 0} · {formatoDuracion(simulacion.tiempo_simulado_s ?? 0)} simulados
        </span>
      )}
    </div>
  );
}

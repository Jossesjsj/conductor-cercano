import { motion } from "framer-motion";
import { Loader2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { ETIQUETA_ESTADO } from "./formato";

export function Tarjeta({ children, className = "", retraso = 0 }: { children: ReactNode; className?: string; retraso?: number }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: retraso, ease: [0.22, 1, 0.36, 1] }}
      className={`panel ${className}`}
    >
      {children}
    </motion.section>
  );
}

export function EncabezadoTarjeta({ titulo, subtitulo, icono: Icono, accion }: { titulo: string; subtitulo?: string; icono?: LucideIcon; accion?: ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-3 border-b border-panel-borde px-5 py-3.5">
      <div className="flex items-center gap-2.5">
        {Icono && (
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-acento/10 text-acento-suave ring-1 ring-acento/20">
            <Icono size={16} />
          </span>
        )}
        <div>
          <h2 className="text-sm font-semibold text-slate-100">{titulo}</h2>
          {subtitulo && <p className="text-xs text-slate-400">{subtitulo}</p>}
        </div>
      </div>
      {accion}
    </header>
  );
}

export function Indicador({ etiqueta, valor, detalle, icono: Icono, color = "text-acento-suave", retraso = 0, children }: {
  etiqueta: string; valor: ReactNode; detalle?: ReactNode; icono: LucideIcon; color?: string; retraso?: number; children?: ReactNode;
}) {
  return (
    <Tarjeta retraso={retraso} className="relative overflow-hidden p-4">
      <div className="flex items-start justify-between">
        <span className="etiqueta">{etiqueta}</span>
        <Icono size={16} className={color} />
      </div>
      <div className="num mt-2 text-[26px] font-semibold leading-none tracking-tight text-white">{valor}</div>
      {detalle && <div className="mt-1.5 text-xs text-slate-400">{detalle}</div>}
      {children}
    </Tarjeta>
  );
}

const ESTILOS_INSIGNIA: Record<string, string> = {
  DISPONIBLE: "bg-green-500/10 text-green-400 ring-green-500/25",
  OCUPADO: "bg-amber-500/10 text-amber-300 ring-amber-500/25",
  EN_SERVICIO: "bg-red-500/10 text-red-300 ring-red-500/25",
  INACTIVO: "bg-slate-500/10 text-slate-400 ring-slate-500/25",
  CONDUCTOR_ASIGNADO: "bg-blue-500/10 text-blue-300 ring-blue-500/25",
  VIAJANDO: "bg-pink-500/10 text-pink-300 ring-pink-500/25",
  FINALIZADO: "bg-green-500/10 text-green-400 ring-green-500/25",
  CANCELADO: "bg-slate-500/10 text-slate-400 ring-slate-500/25",
  INTERRUMPIDO: "bg-orange-500/10 text-orange-300 ring-orange-500/25",
  EJECUTANDO: "bg-green-500/10 text-green-400 ring-green-500/25",
  PAUSADA: "bg-amber-500/10 text-amber-300 ring-amber-500/25",
  DETENIDA: "bg-slate-500/10 text-slate-300 ring-slate-500/25",
  LISTO: "bg-green-500/10 text-green-400 ring-green-500/25",
  ERROR: "bg-red-500/10 text-red-300 ring-red-500/25",
};

export function Insignia({ valor, texto }: { valor: string; texto?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${ESTILOS_INSIGNIA[valor] ?? "bg-blue-500/10 text-blue-300 ring-blue-500/25"}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {texto ?? ETIQUETA_ESTADO[valor] ?? valor}
    </span>
  );
}

export function Interruptor({ activo, alCambiar, etiqueta, descripcion }: { activo: boolean; alCambiar: () => void; etiqueta: string; descripcion?: string }) {
  return (
    <button type="button" onClick={alCambiar} className="flex w-full items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-slate-800/50">
      <span>
        <span className="block text-sm text-slate-200">{etiqueta}</span>
        {descripcion && <span className="block text-xs text-slate-500">{descripcion}</span>}
      </span>
      <span className={`relative h-5 w-9 shrink-0 rounded-full transition ${activo ? "bg-gradient-to-r from-blue-600 to-cyan-500" : "bg-slate-700"}`}>
        <motion.span layout className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow ${activo ? "right-0.5" : "left-0.5"}`} />
      </span>
    </button>
  );
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-400">
      <Loader2 size={16} className="animate-spin" /> {texto}
    </div>
  );
}

export function Vacio({ titulo, descripcion, accion }: { titulo: string; descripcion?: string; accion?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-600/30 to-cyan-500/20 ring-1 ring-acento/30" />
      <p className="text-sm font-medium text-slate-200">{titulo}</p>
      {descripcion && <p className="max-w-sm text-xs text-slate-400">{descripcion}</p>}
      {accion}
    </div>
  );
}

export function MiniGrafico({ valores, color = "#22d3ee", alto = 36 }: { valores: (number | null)[]; color?: string; alto?: number }) {
  const datos = valores.filter((v): v is number => v !== null);
  if (datos.length < 2) return <div style={{ height: alto }} />;
  const min = Math.min(...datos);
  const max = Math.max(...datos);
  const rango = max - min || 1;
  const ancho = 200;
  const puntos = datos.map((v, i) => `${(i / (datos.length - 1)) * ancho},${alto - 3 - ((v - min) / rango) * (alto - 6)}`).join(" ");
  const id = `g${color.replace("#", "")}`;
  return (
    <svg viewBox={`0 0 ${ancho} ${alto}`} preserveAspectRatio="none" className="mt-3 w-full" style={{ height: alto }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.35" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${alto} ${puntos} ${ancho},${alto}`} fill={`url(#${id})`} />
      <polyline points={puntos} fill="none" stroke={color} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function CampoNumero({ etiqueta, valor, alCambiar, min, max, paso = 1, unidad, ayuda }: {
  etiqueta: string; valor: number; alCambiar: (v: number) => void; min?: number; max?: number; paso?: number; unidad?: string; ayuda?: string;
}) {
  return (
    <label className="block">
      <span className="etiqueta">{etiqueta}</span>
      <div className="relative mt-1.5">
        <input type="number" className="campo num pr-14" value={Number.isFinite(valor) ? valor : ""} min={min} max={max} step={paso}
          onChange={(e) => alCambiar(e.target.value === "" ? NaN : Number(e.target.value))} />
        {unidad && <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500">{unidad}</span>}
      </div>
      {ayuda && <span className="mt-1 block text-[11px] text-slate-500">{ayuda}</span>}
    </label>
  );
}

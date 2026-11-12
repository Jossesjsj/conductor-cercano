// Panel del viaje en vivo: el conductor se acerca, el pasajero sube y llega a su destino.
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CarFront, CheckCircle2, Flag, Gauge, MapPin, Navigation, Pause, Play, SkipForward, Sparkles, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { api, ErrorApi } from "@/services/api";
import type { SeguimientoViaje as Seguimiento } from "@/services/tipos";
import { usarAlmacen } from "@/stores/almacen";
import { notificar } from "@/stores/notificaciones";
import { formatoDistancia, formatoDuracion } from "@/components/ui/formato";

const PASOS = [
  { clave: "asignado", texto: "Asignado", icono: CheckCircle2 },
  { clave: "recogida", texto: "En camino", icono: CarFront },
  { clave: "viaje", texto: "A bordo", icono: UserRound },
  { clave: "finalizado", texto: "Llegada", icono: Flag },
];

function indicePaso(fase: Seguimiento["fase"]): number {
  return fase === "recogida" ? 1 : fase === "viaje" ? 2 : fase === "finalizado" ? 3 : 0;
}

function titulo(s: Seguimiento, recienSubio: boolean): { texto: string; detalle: string } {
  const nombre = s.conductor?.nombre.split(" ")[0] ?? "Tu conductor";
  if (s.fase === "recogida") {
    return s.distancia_restante_m < 40
      ? { texto: `${nombre} está llegando`, detalle: "Prepárate para subir" }
      : { texto: `${nombre} está en camino`, detalle: "Se dirige a tu punto de recogida por la ruta más rápida" };
  }
  if (s.fase === "viaje") {
    return recienSubio
      ? { texto: "¡Subiste al vehículo!", detalle: `${nombre} te recogió; comienza el viaje` }
      : { texto: "En viaje hacia tu destino", detalle: "Siguiendo la ruta más corta por las calles reales" };
  }
  if (s.fase === "finalizado") return { texto: "Llegaste a tu destino", detalle: "Gracias por viajar con CONDUCTOR CERCANO" };
  return { texto: "Viaje cancelado", detalle: s.pasajero.motivo_cancelacion || "El servicio no pudo completarse" };
}

interface Props {
  datos: Seguimiento;
  seguirVehiculo: boolean;
  alAlternarSeguimiento: () => void;
  alNuevaSolicitud: () => void;
}

export function SeguimientoViaje({ datos: s, seguirVehiculo, alAlternarSeguimiento, alNuevaSolicitud }: Props) {
  const [recienSubio, setRecienSubio] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const faseAnterior = useRef(s.fase);

  // Avisos al cambiar de fase (recogida → viaje → llegada).
  useEffect(() => {
    if (faseAnterior.current === s.fase) return;
    if (faseAnterior.current === "recogida" && s.fase === "viaje") {
      notificar("exito", `${s.conductor?.nombre ?? "El conductor"} llegó y subiste al vehículo (espera ${formatoDuracion(s.espera_real_s)})`);
      setRecienSubio(true);
      window.setTimeout(() => setRecienSubio(false), 3500);
    }
    if (s.fase === "finalizado") notificar("exito", `Llegaste a tu destino en ${formatoDuracion(s.duracion_viaje_s)}`);
    faseAnterior.current = s.fase;
  }, [s.fase, s.conductor?.nombre, s.espera_real_s, s.duracion_viaje_s]);

  const total = s.fase === "recogida" ? s.distancia_recogida_m : s.distancia_viaje_m;
  const progreso = s.fase === "finalizado" ? 1 : total ? Math.min(1, Math.max(0, 1 - s.distancia_restante_m / total)) : 0;
  const { texto, detalle } = titulo(s, recienSubio);
  const paso = indicePaso(s.fase);
  const enCurso = s.fase === "recogida" || s.fase === "viaje";
  const detenida = s.estado_simulacion !== "EJECUTANDO";

  const ejecutar = async (accion: () => Promise<unknown>) => {
    setOcupado(true);
    try {
      const estado = await accion();
      if (estado && typeof estado === "object" && "configurada" in estado) usarAlmacen.getState().fijarSimulacion(estado as never);
    } catch (e) {
      notificar("error", e instanceof ErrorApi ? e.message : "No se pudo controlar la simulación");
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-4 p-5">
      <div className="flex items-start gap-3">
        <div className={`relative grid h-11 w-11 shrink-0 place-items-center rounded-xl ${s.fase === "finalizado" ? "bg-green-500/15 text-green-300" : "bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-brillo"}`}>
          {s.fase === "finalizado" ? <Flag size={20} /> : s.fase === "viaje" ? <Navigation size={20} /> : <CarFront size={20} />}
          {enCurso && !detenida && <span className="pulso absolute inset-0 rounded-xl text-cyan-300" />}
        </div>
        <div className="min-w-0">
          <AnimatePresence mode="wait">
            <motion.h3 key={texto} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="text-base font-semibold text-white">
              {texto}
            </motion.h3>
          </AnimatePresence>
          <p className="text-xs text-slate-400">{detalle}</p>
        </div>
      </div>

      {/* Pasos del viaje */}
      <ol className="grid grid-cols-4 gap-1">
        {PASOS.map(({ clave, texto: t, icono: Icono }, i) => (
          <li key={clave} className="flex flex-col items-center gap-1.5 text-center">
            <div className={`grid h-8 w-8 place-items-center rounded-full ring-1 transition ${
              i < paso ? "bg-cyan-500/20 text-cyan-200 ring-cyan-400/40" : i === paso ? "bg-gradient-to-br from-blue-600 to-cyan-500 text-white ring-transparent" : "bg-slate-800 text-slate-500 ring-slate-700"}`}>
              <Icono size={14} />
            </div>
            <span className={`text-[10px] ${i <= paso ? "text-slate-200" : "text-slate-500"}`}>{t}</span>
          </li>
        ))}
      </ol>

      {enCurso && (
        <div className="rounded-xl border border-panel-borde bg-slate-900/50 p-4">
          <div className="flex items-end justify-between">
            <div>
              <div className="etiqueta">{s.fase === "recogida" ? "Llega en" : "Llegas en"}</div>
              <div className="num text-3xl font-semibold text-white">{formatoDuracion(s.eta_restante_s)}</div>
            </div>
            <div className="text-right">
              <div className="etiqueta">Distancia restante</div>
              <div className="num text-lg text-cyan-200">{formatoDistancia(s.distancia_restante_m)}</div>
            </div>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-800">
            <motion.div className={`h-full rounded-full ${s.fase === "recogida" ? "bg-gradient-to-r from-blue-600 to-cyan-400" : "bg-gradient-to-r from-pink-600 to-fuchsia-400"}`}
              animate={{ width: `${progreso * 100}%` }} transition={{ duration: 0.6, ease: "linear" }} />
          </div>
          <div className="num mt-1.5 flex justify-between text-[10px] text-slate-500">
            <span>{s.fase === "recogida" ? "Conductor" : "Recogida"}</span>
            <span>{Math.round(progreso * 100)} %</span>
            <span>{s.fase === "recogida" ? "Tu ubicación" : "Destino"}</span>
          </div>
        </div>
      )}

      {s.fase === "finalizado" && (
        <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="grid grid-cols-2 gap-3 rounded-xl border border-green-500/25 bg-green-500/[0.06] p-4 text-xs">
          {[
            ["Espera del conductor", formatoDuracion(s.espera_real_s)],
            ["ETA estimado", formatoDuracion(s.eta_recogida_s)],
            ["Duración del viaje", formatoDuracion(s.duracion_viaje_s)],
            ["Distancia del viaje", formatoDistancia(s.distancia_viaje_m)],
          ].map(([k, v]) => (
            <div key={k}><div className="text-slate-400">{k}</div><div className="num text-sm font-semibold text-white">{v}</div></div>
          ))}
          <p className="col-span-2 text-[11px] text-slate-500">Tiempos del reloj de la simulación (a ×1 coinciden con el tiempo real).</p>
        </motion.div>
      )}

      {s.conductor && (
        <div className="flex items-center gap-3 rounded-xl border border-panel-borde bg-slate-900/40 p-3">
          <div className="grid h-10 w-10 place-items-center rounded-full bg-slate-800 text-sm font-semibold text-cyan-200">
            {s.conductor.nombre.split(" ").map((p) => p[0]).join("")}
          </div>
          <div className="min-w-0 flex-1 text-xs">
            <div className="text-sm text-slate-100">{s.conductor.nombre} <span className="text-slate-500">#{s.conductor.id_conductor}</span></div>
            <div className="text-slate-400">{s.conductor.vehiculo.marca} {s.conductor.vehiculo.modelo} · {s.conductor.vehiculo.color} · {s.conductor.velocidad_kmh} km/h</div>
          </div>
          <span className="num rounded-md border border-slate-600 bg-slate-950 px-2 py-1 text-xs font-semibold tracking-wider text-white">{s.conductor.vehiculo.placa}</span>
        </div>
      )}

      {enCurso && detenida && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/[0.07] px-4 py-3 text-xs text-amber-200">
          <span>La simulación está {s.estado_simulacion === "PAUSADA" ? "pausada" : "detenida"}: el vehículo no avanza.</span>
          <button className="boton-primario h-8 px-3 text-xs" disabled={ocupado}
            onClick={() => ejecutar(() => api.controlar(s.estado_simulacion === "PAUSADA" ? "reanudar" : "iniciar"))}>
            <Play size={13} /> {s.estado_simulacion === "PAUSADA" ? "Reanudar" : "Iniciar"}
          </button>
        </div>
      )}

      {enCurso && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1 text-[11px] text-slate-400" title="×1 = tiempo real"><Gauge size={12} /> Velocidad</span>
          {[1, 2, 4, 8].map((factor) => (
            <button key={factor} disabled={ocupado} onClick={() => ejecutar(() => api.parametros({ multiplicador_velocidad: factor }))}
              className={`num rounded-md px-2.5 py-1 text-xs ring-1 transition ${s.multiplicador_velocidad === factor ? "bg-cyan-500/20 text-cyan-200 ring-cyan-400/40" : "text-slate-400 ring-slate-700 hover:text-white"}`}>
              ×{factor}
            </button>
          ))}
          {detenida ? (
            <button className="boton-secundario ml-auto h-8 px-2.5 text-xs" disabled={ocupado} onClick={() => ejecutar(() => api.controlar("avanzar"))}>
              <SkipForward size={13} /> Turno
            </button>
          ) : (
            <button className="boton-secundario ml-auto h-8 px-2.5 text-xs" disabled={ocupado} onClick={() => ejecutar(() => api.controlar("pausar"))}>
              <Pause size={13} /> Pausar
            </button>
          )}
          <button onClick={alAlternarSeguimiento} className={`boton h-8 px-2.5 text-xs ring-1 ${seguirVehiculo ? "bg-cyan-500/15 text-cyan-200 ring-cyan-400/40" : "text-slate-300 ring-slate-700"}`}>
            <MapPin size={13} /> {seguirVehiculo ? "Siguiendo" : "Seguir auto"}
          </button>
        </div>
      )}

      {!enCurso && (
        <div className="flex gap-2">
          <button className="boton-primario flex-1" onClick={alNuevaSolicitud}><Sparkles size={14} /> Nueva solicitud</button>
          {s.id_asignacion && <Link to="/historial" className="boton-secundario">Ver historial</Link>}
        </div>
      )}
    </div>
  );
}

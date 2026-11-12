import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity, CarFront, CheckCircle2, Clock3, Cpu, Database, MapPin, Navigation, Route, Timer, UserRound, Users,
} from "lucide-react";
import { api } from "@/services/api";
import type { ResumenHistorico } from "@/services/tipos";
import { usarAlmacen } from "@/stores/almacen";
import { EncabezadoTarjeta, Indicador, Insignia, MiniGrafico, Tarjeta, Vacio } from "@/components/ui/Primitivos";
import { formatoDistancia, formatoDuracion, formatoNumero } from "@/components/ui/formato";

function DistribucionEstados() {
  const e = usarAlmacen((s) => s.estadisticas);
  if (!e || !e.conductores_totales) return null;
  const partes = [
    { clave: "Disponibles", valor: e.conductores_disponibles, color: "bg-estado-disponible" },
    { clave: "En recogida", valor: e.conductores_en_recogida, color: "bg-estado-ocupado" },
    { clave: "En servicio", valor: e.conductores_en_servicio, color: "bg-estado-servicio" },
    { clave: "Inactivos", valor: e.conductores_inactivos, color: "bg-estado-inactivo" },
  ];
  return (
    <div className="px-5 py-4">
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-800">
        {partes.map((p) => (
          <div key={p.clave} className={`${p.color} transition-all duration-700`} style={{ width: `${(p.valor / e.conductores_totales) * 100}%` }} />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {partes.map((p) => (
          <div key={p.clave} className="flex items-center gap-2 text-xs text-slate-400">
            <span className={`h-2 w-2 rounded-full ${p.color}`} /> {p.clave}
            <span className="num ml-auto text-slate-200">{formatoNumero(p.valor)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Dashboard() {
  const e = usarAlmacen((s) => s.estadisticas);
  const simulacion = usarAlmacen((s) => s.simulacion);
  const serie = usarAlmacen((s) => s.serie);
  const eventos = usarAlmacen((s) => s.eventos);
  const [historico, setHistorico] = useState<ResumenHistorico | null>(null);

  useEffect(() => {
    const cargar = () =>
      api.estadisticas().then((r) => {
        setHistorico(r.historico);
        if (r.simulacion && !usarAlmacen.getState().estadisticas) usarAlmacen.getState().fijarEstadisticas(r.simulacion);
      }).catch(() => undefined);
    cargar();
    const t = window.setInterval(cargar, 10000);
    return () => window.clearInterval(t);
  }, []);

  if (simulacion && !simulacion.configurada) {
    return (
      <div className="p-6">
        <Tarjeta>
          <Vacio titulo="No hay una simulación configurada" descripcion="Seleccione un distrito, descargue su red vial y genere la flota."
            accion={<Link to="/configuracion" className="boton-primario mt-3">Ir a configuración</Link>} />
        </Tarjeta>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1500px] space-y-5 p-4 lg:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white">Panel de control</h1>
          <p className="text-sm text-slate-400">
            Indicadores calculados por el backend en tiempo real · {simulacion?.distrito?.nombre ?? "—"} ({simulacion?.distrito?.provincia ?? ""})
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          Estado: <Insignia valor={simulacion?.estado ?? "DETENIDA"} />
          <span className="num">Turno {formatoNumero(e?.turno ?? 0)} · {formatoDuracion(e?.tiempo_simulado_s ?? 0)}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Indicador etiqueta="Conductores totales" valor={formatoNumero(e?.conductores_totales)} icono={CarFront} detalle={`${formatoNumero(e?.conductores_inactivos)} inactivos`} />
        <Indicador etiqueta="Disponibles" valor={formatoNumero(e?.conductores_disponibles)} icono={Navigation} color="text-green-400" retraso={0.03}>
          <MiniGrafico valores={serie.map((p) => p.disponibles)} color="#22c55e" />
        </Indicador>
        <Indicador etiqueta="Ocupados" valor={formatoNumero(e?.conductores_ocupados)} icono={Activity} color="text-amber-300" retraso={0.06}
          detalle={`${formatoNumero(e?.conductores_en_recogida)} en recogida · ${formatoNumero(e?.conductores_en_servicio)} en servicio`}>
          <MiniGrafico valores={serie.map((p) => p.ocupados)} color="#f59e0b" />
        </Indicador>
        <Indicador etiqueta="Pasajeros activos" valor={formatoNumero(e?.pasajeros_activos)} icono={UserRound} color="text-pink-300" retraso={0.09}>
          <MiniGrafico valores={serie.map((p) => p.pasajeros)} color="#ec4899" />
        </Indicador>
        <Indicador etiqueta="Solicitudes realizadas" valor={formatoNumero(e?.solicitudes_realizadas)} icono={Users} retraso={0.12}
          detalle={`${formatoNumero(e?.asignaciones_exitosas)} asignadas · ${formatoNumero(e?.asignaciones_fallidas)} rechazadas`} />
        <Indicador etiqueta="Asignaciones completadas" valor={formatoNumero(e?.asignaciones_completadas)} icono={CheckCircle2} color="text-green-400" retraso={0.15}
          detalle="Viajes finalizados en esta simulación" />
        <Indicador etiqueta="ETA promedio" valor={formatoDuracion(e?.eta_promedio_s)} icono={Timer} color="text-cyan-300" retraso={0.18}
          detalle={`Espera real medida: ${formatoDuracion(e?.espera_real_promedio_s)}`}>
          <MiniGrafico valores={serie.map((p) => p.eta)} color="#22d3ee" />
        </Indicador>
        <Indicador etiqueta="Distancia media de recogida" valor={formatoDistancia(e?.distancia_promedio_recogida_m)} icono={Route} retraso={0.21}
          detalle={`Línea recta: ${formatoDistancia(e?.distancia_promedio_haversine_m)}`} />
        <Indicador etiqueta="Estado de la simulación" valor={<Insignia valor={simulacion?.estado ?? "DETENIDA"} />} icono={Clock3} retraso={0.24}
          detalle={`Modo ${simulacion?.configuracion?.modo === "MANUAL" ? "manual" : "automático"} · ×${simulacion?.configuracion?.multiplicador_velocidad ?? 1}`} />
        <Indicador etiqueta="Distrito seleccionado" valor={<span className="text-lg">{simulacion?.distrito?.nombre ?? "—"}</span>} icono={MapPin} retraso={0.27}
          detalle={`${formatoNumero(simulacion?.distrito?.area_km2, 2)} km² · ${formatoNumero(simulacion?.grafo?.nodos)} nodos`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Tarjeta className="xl:col-span-2" retraso={0.1}>
          <EncabezadoTarjeta titulo="Distribución de la flota" subtitulo="Estados de los conductores (backend)" icono={CarFront} />
          <DistribucionEstados />
          <div className="grid grid-cols-2 gap-px border-t border-panel-borde bg-panel-borde md:grid-cols-4">
            {[
              { k: "Duración de turno", v: `${formatoNumero(e?.duracion_turno_promedio_ms, 1)} ms`, i: Cpu },
              { k: "Actualizaciones Quadtree", v: formatoNumero(e?.actualizaciones_quadtree), i: Database },
              { k: "Nodos del Quadtree", v: formatoNumero(simulacion?.quadtree?.nodos ?? e?.nodos_quadtree), i: Database },
              { k: "Aristas del grafo", v: formatoNumero(e?.aristas_grafo), i: Route },
            ].map(({ k, v, i: Icono }) => (
              <div key={k} className="bg-fondo-2/80 px-5 py-3">
                <div className="flex items-center gap-1.5 text-[11px] text-slate-400"><Icono size={12} /> {k}</div>
                <div className="num mt-1 text-sm text-slate-100">{v}</div>
              </div>
            ))}
          </div>
          <div className="px-5 pb-4 pt-3">
            <div className="etiqueta mb-1">Duración del turno (ms) · últimos {serie.length} turnos</div>
            <MiniGrafico valores={serie.map((p) => p.duracion)} color="#60a5fa" alto={56} />
          </div>
        </Tarjeta>

        <Tarjeta retraso={0.15} className="flex flex-col">
          <EncabezadoTarjeta titulo="Actividad reciente" subtitulo="Eventos emitidos por WebSocket" icono={Activity} />
          <ul className="max-h-[330px] flex-1 divide-y divide-panel-borde overflow-y-auto">
            {eventos.length === 0 && <li className="px-5 py-8 text-center text-xs text-slate-500">Inicie la simulación para ver eventos en vivo.</li>}
            {eventos.slice(0, 30).map((ev) => (
              <li key={ev.id} className="flex items-start gap-3 px-5 py-2.5 text-xs">
                <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${ev.tipo === "asignacion" ? "bg-blue-400" : ev.tipo === "recogida" ? "bg-amber-400" : ev.tipo === "finalizacion" ? "bg-green-400" : "bg-red-400"}`} />
                <span className="flex-1 text-slate-300">{ev.texto}</span>
                <span className="num shrink-0 text-slate-500">{new Date(ev.fecha).toLocaleTimeString("es-PE")}</span>
              </li>
            ))}
          </ul>
        </Tarjeta>
      </div>

      {historico && (
        <Tarjeta retraso={0.2}>
          <EncabezadoTarjeta titulo="Historial persistente" subtitulo="Totales almacenados en SQLite (sobreviven al reinicio del servidor)" icono={Database}
            accion={<Link to="/historial" className="boton-fantasma text-xs">Ver historial</Link>} />
          <div className="grid grid-cols-2 gap-4 px-5 py-4 md:grid-cols-5">
            {[
              ["Solicitudes", formatoNumero(historico.solicitudes)],
              ["Asignaciones", formatoNumero(historico.asignaciones)],
              ["Viajes finalizados", formatoNumero(historico.finalizadas)],
              ["ETA medio histórico", formatoDuracion(historico.eta_promedio_s)],
              ["Recogida media", formatoDistancia(historico.distancia_promedio_recogida_m)],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="etiqueta">{k}</div>
                <div className="num mt-1 text-lg text-white">{v}</div>
              </div>
            ))}
          </div>
        </Tarjeta>
      )}
    </div>
  );
}

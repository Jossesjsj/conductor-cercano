import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Box, Building2, CarFront, Crosshair, Layers, Map as MapaIcono, Network, Route, X } from "lucide-react";
import { MapaOperaciones } from "@/features/mapa/MapaOperaciones";
import { TablaCandidatos } from "@/features/solicitud/TablaCandidatos";
import { api, ErrorApi } from "@/services/api";
import { ESTADOS_CONDUCTOR, type InfoConductor } from "@/services/tipos";
import { usarAlmacen } from "@/stores/almacen";
import { flotaVisual } from "@/stores/flotaVisual";
import { notificar } from "@/stores/notificaciones";
import { Insignia, Interruptor } from "@/components/ui/Primitivos";
import { ETIQUETA_ESTADO, formatoDistancia, formatoDuracion, formatoNumero } from "@/components/ui/formato";
import { ControlesSimulacion } from "@/components/ControlesSimulacion";

const COLOR_PUNTO: Record<string, string> = { DISPONIBLE: "bg-estado-disponible", OCUPADO: "bg-estado-ocupado", EN_SERVICIO: "bg-estado-servicio", INACTIVO: "bg-estado-inactivo" };

function PanelCapas() {
  const s = usarAlmacen();
  return (
    <div className="panel w-[270px] p-3">
      <div className="mb-2 flex items-center gap-2 px-2 text-xs font-semibold text-slate-300"><Layers size={14} /> Visualización</div>
      <div className="mb-3 grid grid-cols-2 gap-1 rounded-lg bg-slate-900/70 p-1">
        {[false, true].map((tres) => (
          <button key={String(tres)} onClick={() => s.fijarModo3D(tres)}
            className={`flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium transition ${s.modo3D === tres ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white" : "text-slate-400 hover:text-white"}`}>
            {tres ? <Box size={13} /> : <MapaIcono size={13} />} {tres ? "3D" : "2D"}
          </button>
        ))}
      </div>
      <Interruptor etiqueta="Modelos 3D de vehículos" descripcion="Desactivar = íconos 2D" activo={s.modelos3D} alCambiar={() => s.alternar("modelos3D")} />
      <Interruptor etiqueta="Edificios 3D" activo={s.mostrarEdificios} alCambiar={() => s.alternar("mostrarEdificios")} />
      <Interruptor etiqueta="Rutas asignadas" activo={s.mostrarRutas} alCambiar={() => s.alternar("mostrarRutas")} />
      <Interruptor etiqueta="Red vial del grafo" descripcion="Calles, sentidos e intersecciones" activo={s.mostrarRedVial} alCambiar={() => s.alternar("mostrarRedVial")} />
      <div className="mt-3 border-t border-panel-borde px-2 pt-3">
        <div className="etiqueta mb-2">Filtrar conductores</div>
        <div className="grid grid-cols-2 gap-1.5">
          {ESTADOS_CONDUCTOR.map((estado) => (
            <button key={estado} onClick={() => s.alternarFiltro(estado)}
              className={`flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-[11px] transition ${s.filtros[estado] ? "border-slate-600 bg-slate-800/80 text-slate-100" : "border-transparent text-slate-500 line-through"}`}>
              <span className={`h-2 w-2 rounded-full ${COLOR_PUNTO[estado]}`} /> {ETIQUETA_ESTADO[estado]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function PanelConductor({ id }: { id: number }) {
  const [info, setInfo] = useState<InfoConductor | null>(null);
  const seleccionar = usarAlmacen((s) => s.seleccionarConductor);
  useEffect(() => {
    let activo = true;
    const cargar = () => api.conductor(id).then((d) => activo && setInfo(d)).catch(() => activo && setInfo(null));
    cargar();
    const t = window.setInterval(cargar, 2000);
    return () => {
      activo = false;
      window.clearInterval(t);
    };
  }, [id]);
  return (
    <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} className="panel w-[320px] p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="etiqueta">Conductor seleccionado</div>
          <div className="mt-1 text-lg font-semibold text-white">#{id} {info && <span className="text-sm font-normal text-slate-400">{info.nombre}</span>}</div>
        </div>
        <button onClick={() => seleccionar(null)} className="text-slate-400 hover:text-white" aria-label="Cerrar"><X size={16} /></button>
      </div>
      {info && (
        <div className="mt-3 space-y-3 text-sm">
          <Insignia valor={info.estado} />
          <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
            {[
              ["Vehículo", `${info.vehiculo.marca} ${info.vehiculo.modelo} ${info.vehiculo.anio}`],
              ["Placa · color", `${info.vehiculo.placa} · ${info.vehiculo.color}`],
              ["Velocidad", `${info.velocidad_kmh} km/h`],
              ["Recorrido", formatoDistancia(info.distancia_recorrida_m)],
              ["Nodo actual → siguiente", `${info.nodo_actual} → ${info.nodo_siguiente}`],
              ["Rumbo", `${Math.round(info.rumbo)}°`],
              ["Servicios completados", String(info.servicios_completados)],
              ["Pasajero asignado", info.id_pasajero_asignado ? `#${info.id_pasajero_asignado}` : "—"],
            ].map(([k, v]) => (
              <div key={k}><dt className="text-slate-500">{k}</dt><dd className="num text-slate-200">{v}</dd></div>
            ))}
          </dl>
          <div className="num text-[11px] text-slate-500">{info.latitud.toFixed(6)}, {info.longitud.toFixed(6)}</div>
        </div>
      )}
    </motion.div>
  );
}

function PanelUltimaAsignacion() {
  const r = usarAlmacen((s) => s.ultimaAsignacion);
  const [abierto, setAbierto] = useState(true);
  if (!r) return null;
  return (
    <motion.div layout initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="panel w-[460px] max-w-[calc(100vw-2rem)] overflow-hidden">
      <button onClick={() => setAbierto(!abierto)} className="flex w-full items-center justify-between px-4 py-3 text-left">
        <div>
          <div className="etiqueta">Última solicitud · pasajero #{r.pasajero.id_pasajero}</div>
          <div className="mt-0.5 text-sm text-white">
            {r.exito ? <>Conductor <b className="text-cyan-300">#{r.conductor?.id_conductor}</b> · ETA {r.eta_recogida_texto} · {formatoDistancia(r.distancia_recogida_m)}</> : <span className="text-red-300">{r.mensaje}</span>}
          </div>
        </div>
        <Route size={16} className="text-slate-400" />
      </button>
      <AnimatePresence initial={false}>
        {abierto && r.candidatos.length > 0 && (
          <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="border-t border-panel-borde">
            <TablaCandidatos candidatos={r.candidatos} compacta />
            {r.justificacion && <p className="border-t border-panel-borde px-4 py-2.5 text-[11px] leading-relaxed text-slate-400">{r.justificacion}</p>}
            <div className="num flex gap-3 border-t border-panel-borde px-4 py-2 text-[10px] text-slate-500">
              <span>Radio final {formatoNumero(r.busqueda.radio_final_m)} m</span>
              <span>{r.busqueda.iteraciones} expansiones</span>
              <span>{r.busqueda.elementos_examinados} examinados</span>
              <span>Total {formatoNumero(r.tiempos_ms.total, 2)} ms</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export function CentroOperaciones() {
  const estadisticas = usarAlmacen((s) => s.estadisticas);
  const seleccionado = usarAlmacen((s) => s.conductorSeleccionado);
  const eventos = usarAlmacen((s) => s.eventos);
  const [modoSolicitud, setModoSolicitud] = useState<null | "origen" | "destino">(null);
  const [origen, setOrigen] = useState<[number, number] | null>(null);
  const [destino, setDestino] = useState<[number, number] | null>(null);
  const [visibles, setVisibles] = useState({ total: 0, mostrados: 0 });
  const [panelesAbiertos, setPanelesAbiertos] = useState(() => window.matchMedia("(min-width: 1024px)").matches);

  useEffect(() => flotaVisual.suscribir(() => setVisibles({ total: flotaVisual.totalEnVista, mostrados: flotaVisual.mostrados })), []);

  const alHacerClic = useCallback(async (p: [number, number]) => {
    if (modoSolicitud === "origen") {
      setOrigen(p);
      setModoSolicitud("destino");
      return;
    }
    if (modoSolicitud === "destino" && origen) {
      setDestino(p);
      setModoSolicitud(null);
      try {
        const r = await api.solicitar({ latitud: origen[1], longitud: origen[0] }, { latitud: p[1], longitud: p[0] });
        usarAlmacen.getState().registrarAsignacion(r);
        notificar(r.exito ? "exito" : "error", r.exito ? `Asignado el conductor #${r.conductor?.id_conductor} (ETA ${r.eta_recogida_texto})` : r.mensaje);
        if (r.exito && r.conductor) usarAlmacen.getState().seleccionarConductor(r.conductor.id_conductor);
      } catch (error) {
        notificar("error", error instanceof ErrorApi ? error.message : "No se pudo registrar la solicitud");
      } finally {
        setOrigen(null);
        setDestino(null);
      }
    }
  }, [modoSolicitud, origen]);

  const marcadores = useMemo(() => [
    ...(origen ? [{ lon: origen[0], lat: origen[1], color: "#22c55e" }] : []),
    ...(destino ? [{ lon: destino[0], lat: destino[1], color: "#ec4899" }] : []),
  ], [origen, destino]);

  return (
    <div className="absolute inset-0">
      <MapaOperaciones alHacerClic={modoSolicitud ? alHacerClic : undefined} marcadoresExtra={marcadores} />

      <div className="pointer-events-none absolute inset-0 p-3 lg:p-4">
        <div className="absolute left-3 top-3 bottom-[76px] lg:left-4 lg:top-4">
          <button onClick={() => setPanelesAbiertos((v) => !v)} className="pointer-events-auto panel mb-3 flex items-center gap-2 px-3 py-2 text-xs text-slate-200 lg:hidden">
            <Layers size={14} /> {panelesAbiertos ? "Ocultar paneles" : "Capas y solicitud"}
          </button>
          <div className={`pointer-events-auto max-h-full space-y-3 overflow-y-auto pr-1 ${panelesAbiertos ? "" : "hidden"} lg:block`}>
            <PanelCapas />
            <div className="panel w-[270px] p-3">
              <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold text-slate-300"><Crosshair size={14} /> Solicitud rápida</div>
              {modoSolicitud ? (
                <div className="space-y-2 px-1 text-xs">
                  <p className="text-cyan-200">Haga clic en el mapa para fijar el <b>{modoSolicitud}</b>.</p>
                  <button className="boton-secundario w-full" onClick={() => { setModoSolicitud(null); setOrigen(null); }}>Cancelar</button>
                </div>
              ) : (
                <button className="boton-primario w-full" onClick={() => setModoSolicitud("origen")}>Marcar origen y destino</button>
              )}
            </div>
          </div>
        </div>
        <div className="absolute right-3 top-3 bottom-[76px] lg:right-4 lg:top-4">
          <div className="pointer-events-auto flex max-h-full flex-col items-end gap-3 overflow-y-auto pl-1">
            <AnimatePresence>{seleccionado !== null && <PanelConductor key={seleccionado} id={seleccionado} />}</AnimatePresence>
            <div className="hidden lg:block"><PanelUltimaAsignacion /></div>
          </div>
        </div>

        <div className="absolute inset-x-3 bottom-3 flex items-end justify-between gap-3 lg:inset-x-4 lg:bottom-4">
          <div className="pointer-events-auto panel flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-2.5 text-xs">
            <div className="hidden md:block"><ControlesSimulacion compacto /></div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-slate-400">
              {[
                ["Disponibles", estadisticas?.conductores_disponibles, "bg-estado-disponible"],
                ["Recogida", estadisticas?.conductores_en_recogida, "bg-estado-ocupado"],
                ["Servicio", estadisticas?.conductores_en_servicio, "bg-estado-servicio"],
              ].map(([k, v, c]) => (
                <span key={k as string} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${c}`} />{k} <b className="num text-slate-100">{formatoNumero(v as number)}</b></span>
              ))}
              <span className="flex items-center gap-1.5"><CarFront size={13} /> En vista <b className="num text-slate-100">{formatoNumero(visibles.total)}</b>
                {visibles.mostrados < visibles.total && <span className="text-amber-300">(dibujados {formatoNumero(visibles.mostrados)})</span>}</span>
              <span className="flex items-center gap-1.5"><Network size={13} /> ETA medio <b className="num text-slate-100">{formatoDuracion(estadisticas?.eta_promedio_s)}</b></span>
              <span className="flex items-center gap-1.5"><Building2 size={13} /> Turno <b className="num text-slate-100">{formatoNumero(estadisticas?.turno)}</b> · {formatoNumero(estadisticas?.ultima_duracion_turno_ms, 1)} ms</span>
            </div>
          </div>
          <div className="pointer-events-auto hidden 2xl:block">
            <div className="panel max-h-[120px] w-[420px] overflow-hidden px-4 py-2">
              {eventos.slice(0, 4).map((e) => (
                <motion.div key={e.id} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="truncate py-0.5 text-[11px] text-slate-400">
                  <span className="num mr-2 text-slate-600">{new Date(e.fecha).toLocaleTimeString("es-PE")}</span>{e.texto}
                </motion.div>
              ))}
              {eventos.length === 0 && <div className="py-1 text-[11px] text-slate-500">Sin eventos todavía.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

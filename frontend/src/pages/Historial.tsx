import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, ExternalLink, History, RefreshCw, X } from "lucide-react";
import { MapaRuta } from "@/features/mapa/MapaRuta";
import { TablaCandidatos } from "@/features/solicitud/TablaCandidatos";
import { api } from "@/services/api";
import type { DetalleAsignacion, Distrito, PaginaAsignaciones } from "@/services/tipos";
import { Cargando, EncabezadoTarjeta, Insignia, Tarjeta, Vacio } from "@/components/ui/Primitivos";
import { formatoDistancia, formatoDuracion, formatoFecha, formatoNumero } from "@/components/ui/formato";

const TAMANO = 20;

function Detalle({ id, alCerrar }: { id: number; alCerrar: () => void }) {
  const [d, setD] = useState<DetalleAsignacion | null>(null);
  const [limite, setLimite] = useState<GeoJSON.Feature | null>(null);
  useEffect(() => {
    api.asignacion(id).then((x) => {
      setD(x);
      api.distrito(x.id_distrito).then((r) => setLimite(r.limite)).catch(() => undefined);
    });
  }, [id]);
  return (
    <motion.aside initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 260 }}
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[760px] flex-col border-l border-panel-borde bg-fondo-2/95 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center justify-between border-b border-panel-borde px-5 py-4">
        <div>
          <div className="etiqueta">Detalle de asignación</div>
          <div className="text-lg font-semibold text-white">#{id} {d && <Insignia valor={d.estado_servicio} />}</div>
        </div>
        <div className="flex items-center gap-2">
          <a href={api.urlMapaAsignacion(id)} target="_blank" rel="noreferrer" className="boton-secundario text-xs">Mapa Folium <ExternalLink size={12} /></a>
          <button onClick={alCerrar} className="boton-fantasma" aria-label="Cerrar"><X size={16} /></button>
        </div>
      </div>
      {!d ? <Cargando /> : (
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          <div className="h-[300px] overflow-hidden rounded-xl border border-panel-borde">
            <MapaRuta origen={d.pasajero.origen} destino={d.pasajero.destino} rutaRecogida={d.ruta_recogida} rutaViaje={d.ruta_viaje}
              candidatos={d.candidatos} contexto={d.conductores_contexto} limite={limite} centroInicial={d.pasajero.origen} />
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs md:grid-cols-3">
            {[
              ["Fecha", formatoFecha(d.fecha)],
              ["Distrito", d.id_distrito],
              ["Solicitud / pasajero", `#${d.id_solicitud} / #${d.id_pasajero}`],
              ["Conductor", `#${d.id_conductor} · ${d.nombre_conductor} (${d.placa})`],
              ["Velocidad", `${formatoNumero(d.velocidad_kmh, 1)} km/h`],
              ["Origen", d.direccion_origen || `${d.pasajero.origen[1].toFixed(5)}, ${d.pasajero.origen[0].toFixed(5)}`],
              ["Distancia en línea recta", formatoDistancia(d.distancia_haversine_m)],
              ["Distancia por calles", formatoDistancia(d.distancia_ruta_m)],
              ["ETA calculado", formatoDuracion(d.eta_segundos)],
              ["Viaje", `${formatoDistancia(d.distancia_viaje_m)} · ${formatoDuracion(d.duracion_viaje_s)}`],
              ["Espera real (simulada)", formatoDuracion(d.espera_real_s)],
              ["Nodos origen → destino", `${d.pasajero.nodo_origen} → ${d.pasajero.nodo_destino}`],
              ["Búsqueda Quadtree", `${formatoNumero(d.radio_busqueda_m)} m · ${d.iteraciones_busqueda} iter. · ${d.elementos_examinados} examinados`],
              ["Tiempo de despacho", `${formatoNumero(d.tiempos_ms.total, 2)} ms`],
              ["Tipo de solicitud", d.origen_solicitud],
            ].map(([k, v]) => (
              <div key={k}><dt className="text-slate-500">{k}</dt><dd className="num mt-0.5 break-words text-slate-200">{v}</dd></div>
            ))}
          </dl>
          <Tarjeta>
            <EncabezadoTarjeta titulo={`Candidatos evaluados (${d.candidatos.length})`} subtitulo="Haversine → Dijkstra → menor ETA" />
            <TablaCandidatos candidatos={d.candidatos} />
            <p className="border-t border-panel-borde px-5 py-3 text-xs leading-relaxed text-slate-400">{d.justificacion}</p>
          </Tarjeta>
          {d.calles_recogida.length > 0 && <p className="text-xs text-slate-400">Ruta de recogida por: <span className="text-slate-200">{d.calles_recogida.join(" → ")}</span></p>}
        </div>
      )}
    </motion.aside>
  );
}

export function Historial() {
  const [pagina, setPagina] = useState(1);
  const [filtros, setFiltros] = useState({ distrito: "", estado: "", origen: "" });
  const [datos, setDatos] = useState<PaginaAsignaciones | null>(null);
  const [distritos, setDistritos] = useState<Distrito[]>([]);
  const [seleccion, setSeleccion] = useState<number | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = () => {
    setCargando(true);
    api.asignaciones({ pagina, tamano: TAMANO, ...filtros }).then(setDatos).finally(() => setCargando(false));
  };
  useEffect(cargar, [pagina, filtros]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    api.distritos().then((l) => setDistritos(l.filter((d) => d.descargado))).catch(() => undefined);
  }, []);
  useEffect(() => {
    const alPulsar = (e: KeyboardEvent) => e.key === "Escape" && setSeleccion(null);
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, []);

  const paginas = datos ? Math.max(1, Math.ceil(datos.total / TAMANO)) : 1;
  const filtro = (clave: keyof typeof filtros, valor: string) => {
    setPagina(1);
    setFiltros((f) => ({ ...f, [clave]: valor }));
  };

  return (
    <div className="mx-auto max-w-[1500px] p-4 lg:p-6">
      <Tarjeta>
        <EncabezadoTarjeta titulo="Historial de asignaciones" subtitulo={`${formatoNumero(datos?.total ?? 0)} asignaciones persistidas en SQLite`} icono={History}
          accion={<button className="boton-fantasma text-xs" onClick={cargar}><RefreshCw size={13} className={cargando ? "animate-spin" : ""} /> Actualizar</button>} />
        <div className="flex flex-wrap gap-3 border-b border-panel-borde px-5 py-3">
          <select className="campo w-auto" value={filtros.distrito} onChange={(e) => filtro("distrito", e.target.value)}>
            <option value="">Todos los distritos</option>
            {distritos.map((d) => <option key={d.id_distrito} value={d.id_distrito}>{d.nombre}</option>)}
          </select>
          <select className="campo w-auto" value={filtros.estado} onChange={(e) => filtro("estado", e.target.value)}>
            <option value="">Todos los estados</option>
            {["CONDUCTOR_ASIGNADO", "VIAJANDO", "FINALIZADO", "CANCELADO", "INTERRUMPIDO"].map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
          <select className="campo w-auto" value={filtros.origen} onChange={(e) => filtro("origen", e.target.value)}>
            <option value="">Manual y automática</option>
            <option value="manual">Manual</option>
            <option value="automatica">Automática</option>
            <option value="script">Script</option>
          </select>
        </div>
        {!datos ? <Cargando /> : datos.elementos.length === 0 ? (
          <Vacio titulo="Sin asignaciones" descripcion="Realice una solicitud o inicie la simulación en modo automático." />
        ) : (
          <div className="overflow-x-auto">
            <table className="tabla w-full">
              <thead className="border-b border-panel-borde">
                <tr>
                  <th>ID</th><th>Fecha</th><th>Pasajero</th><th>Conductor</th><th className="text-right">Candidatos</th>
                  <th className="text-right">Línea recta</th><th className="text-right">Por calles</th><th className="text-right">ETA</th>
                  <th>Estado</th><th>Distrito</th><th>Ruta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-panel-borde">
                {datos.elementos.map((a) => (
                  <tr key={a.id_asignacion} onClick={() => setSeleccion(a.id_asignacion)} className="cursor-pointer transition hover:bg-slate-800/40">
                    <td className="num text-cyan-300">#{a.id_asignacion}</td>
                    <td className="num text-slate-400">{formatoFecha(a.fecha)}</td>
                    <td className="num">#{a.id_pasajero} <span className="text-[10px] text-slate-500">{a.origen_solicitud}</span></td>
                    <td>#{a.id_conductor} <span className="text-slate-400">{a.nombre_conductor}</span></td>
                    <td className="num text-right">{a.candidatos_evaluados}</td>
                    <td className="num text-right">{formatoDistancia(a.distancia_haversine_m)}</td>
                    <td className="num text-right">{formatoDistancia(a.distancia_ruta_m)}</td>
                    <td className="num text-right">{formatoDuracion(a.eta_segundos)}</td>
                    <td><Insignia valor={a.estado_servicio} /></td>
                    <td className="text-slate-400">{a.id_distrito}</td>
                    <td><span className="text-xs text-acento-suave">Ver detalle</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between px-5 py-3 text-xs text-slate-400">
          <span>Página {pagina} de {paginas}</span>
          <div className="flex gap-2">
            <button className="boton-secundario h-8 px-2" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)} aria-label="Anterior"><ChevronLeft size={14} /></button>
            <button className="boton-secundario h-8 px-2" disabled={pagina >= paginas} onClick={() => setPagina(pagina + 1)} aria-label="Siguiente"><ChevronRight size={14} /></button>
          </div>
        </div>
      </Tarjeta>
      <AnimatePresence>
        {seleccion !== null && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-30 bg-black/50" onClick={() => setSeleccion(null)} />
            <Detalle key={seleccion} id={seleccion} alCerrar={() => setSeleccion(null)} />
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

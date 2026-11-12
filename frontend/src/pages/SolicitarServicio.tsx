import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, ChevronDown, Clock3, ExternalLink, Loader2, MapPinned, Navigation, Route, Search, Timer, Users } from "lucide-react";
import { MapaRuta, type VehiculoSeguido } from "@/features/mapa/MapaRuta";
import { ElegirConductor } from "@/features/solicitud/ElegirConductor";
import { SelectorUbicacion, type Ubicacion } from "@/features/solicitud/SelectorUbicacion";
import { SeguimientoViaje } from "@/features/solicitud/SeguimientoViaje";
import { TablaCandidatos } from "@/features/solicitud/TablaCandidatos";
import { INTERVALO_SEGUIMIENTO_MS, usarSeguimiento } from "@/hooks/usarSeguimiento";
import { api, ErrorApi } from "@/services/api";
import type { Candidato, Cotizacion, EstadoConductor, ResultadoSolicitud } from "@/services/tipos";
import { usarAlmacen } from "@/stores/almacen";
import { notificar } from "@/stores/notificaciones";
import { EncabezadoTarjeta, Tarjeta } from "@/components/ui/Primitivos";
import { formatoDistancia, formatoNumero } from "@/components/ui/formato";

type Paso = "formulario" | "eligiendo" | "viaje";
const INTERVALO_COTIZACION_MS = 4000;

function DetalleAsignacion({ resultado }: { resultado: ResultadoSolicitud }) {
  return (
    <>
      <div className="grid grid-cols-3 gap-px bg-panel-borde">
        {[
          { k: "ETA de recogida", v: resultado.eta_recogida_texto, i: Timer },
          { k: "Recogida por calles", v: formatoDistancia(resultado.distancia_recogida_m), i: Route },
          { k: "Viaje", v: `${formatoDistancia(resultado.distancia_viaje_m)} · ${resultado.duracion_viaje_texto}`, i: Clock3 },
        ].map(({ k, v, i: Icono }) => (
          <div key={k} className="bg-fondo-2/90 px-4 py-3">
            <div className="flex items-center gap-1 text-[11px] text-slate-400"><Icono size={12} />{k}</div>
            <div className="num mt-1 text-sm font-semibold text-white">{v}</div>
          </div>
        ))}
      </div>
      <TablaCandidatos candidatos={resultado.candidatos} compacta />
      <div className="space-y-2 border-t border-panel-borde px-5 py-3 text-xs text-slate-400">
        <p className="leading-relaxed">{resultado.justificacion}</p>
        {resultado.calles_recogida && resultado.calles_recogida.length > 0 && (
          <p className="flex flex-wrap items-center gap-1 text-slate-300">
            {resultado.calles_recogida.map((c, i) => <span key={i} className="flex items-center gap-1">{i > 0 && <ArrowRight size={11} className="text-slate-600" />}{c}</span>)}
          </p>
        )}
        <p className="num text-[10px] text-slate-500">
          Quadtree {formatoNumero(resultado.tiempos_ms.busqueda_quadtree, 2)} ms · Dijkstra candidatos {formatoNumero(resultado.tiempos_ms.dijkstra_candidatos, 2)} ms ·
          total {formatoNumero(resultado.tiempos_ms.total, 2)} ms · radio {formatoNumero(resultado.busqueda.radio_final_m)} m
        </p>
      </div>
    </>
  );
}

export function SolicitarServicio() {
  const simulacion = usarAlmacen((s) => s.simulacion);
  const [paso, setPaso] = useState<Paso>("formulario");
  const [origen, setOrigen] = useState<Ubicacion | null>(null);
  const [destino, setDestino] = useState<Ubicacion | null>(null);
  const [eligiendoPunto, setEligiendoPunto] = useState<"origen" | "destino" | null>("origen");
  const [buscando, setBuscando] = useState(false);
  const [errorBusqueda, setErrorBusqueda] = useState<string | null>(null);
  const [cotizacion, setCotizacion] = useState<Cotizacion | null>(null);
  const [elegido, setElegido] = useState<number | null>(null);
  const [actualizando, setActualizando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoSolicitud | null>(null);
  const [limite, setLimite] = useState<GeoJSON.Feature | null>(null);
  const [verDetalle, setVerDetalle] = useState(false);
  const [seguirVehiculo, setSeguirVehiculo] = useState(false);
  const elegidoRef = useRef(elegido);
  elegidoRef.current = elegido;

  const idPasajero = paso === "viaje" && resultado?.exito ? resultado.pasajero.id_pasajero : null;
  const { datos: viaje, error: errorViaje } = usarSeguimiento(idPasajero);
  const viajeActivo = viaje !== null && (viaje.fase === "recogida" || viaje.fase === "viaje");

  const idDistrito = simulacion?.distrito?.id_distrito;
  useEffect(() => {
    if (idDistrito) api.distrito(idDistrito).then((d) => setLimite(d.limite)).catch(() => undefined);
  }, [idDistrito]);

  const alHacerClic = async ([lon, lat]: [number, number]) => {
    if (!eligiendoPunto) return;
    const punto = { latitud: lat, longitud: lon, direccion: `${lat.toFixed(5)}, ${lon.toFixed(5)}` };
    const objetivo = eligiendoPunto;
    (objetivo === "origen" ? setOrigen : setDestino)(punto);
    setErrorBusqueda(null);
    setEligiendoPunto(objetivo === "origen" ? "destino" : null);
    try {
      const inversa = await api.geocodificarInversa(lat, lon);
      (objetivo === "origen" ? setOrigen : setDestino)((actual) => (actual && actual.latitud === lat ? { ...punto, direccion: inversa.nombre } : actual));
    } catch {
      /* sin geocodificación inversa: se conservan las coordenadas */
    }
  };

  // ---------------------------------------------------------------- paso 1 → 2: ver conductores
  const cotizar = useCallback(async (silencioso: boolean) => {
    if (!origen || !destino) return;
    silencioso ? setActualizando(true) : setBuscando(true);
    try {
      const c = await api.cotizar(origen, destino);
      if (!c.exito) {
        if (!silencioso) setErrorBusqueda(c.mensaje);
        return;
      }
      setCotizacion(c);
      const actual = elegidoRef.current;
      const sigue = c.candidatos.find((x) => x.id_conductor === actual && x.valido);
      if (!silencioso || !sigue) {
        if (silencioso && actual !== null && !sigue) notificar("info", `El conductor elegido ya no está disponible; te sugerimos al más rápido ahora.`);
        setElegido(c.id_conductor_recomendado);
      }
      if (!silencioso) {
        setErrorBusqueda(null);
        setPaso("eligiendo");
        setEligiendoPunto(null);
      }
    } catch (e) {
      if (!silencioso) setErrorBusqueda(e instanceof ErrorApi ? e.message : "No se pudo consultar a los conductores");
    } finally {
      silencioso ? setActualizando(false) : setBuscando(false);
    }
  }, [origen, destino]);

  // Mientras eliges, la flota sigue moviéndose: se actualizan posiciones y ETA periódicamente.
  useEffect(() => {
    if (paso !== "eligiendo" || confirmando) return;
    const t = window.setInterval(() => cotizar(true), INTERVALO_COTIZACION_MS);
    return () => window.clearInterval(t);
  }, [paso, confirmando, cotizar]);

  // ---------------------------------------------------------------- paso 2 → 3: confirmar y viajar
  const confirmar = async () => {
    if (!origen || !destino || elegido === null) return;
    setConfirmando(true);
    try {
      const r = await api.solicitar(origen, destino, elegido);
      setResultado(r);
      usarAlmacen.getState().registrarAsignacion(r);
      if (!r.exito) {
        notificar("error", r.mensaje);
        setErrorBusqueda(r.mensaje);
        setPaso("formulario");
        return;
      }
      if (r.aviso) notificar("info", r.aviso);
      notificar("exito", `${r.conductor?.nombre} va en camino · llega en ${r.eta_recogida_texto}`);
      // Para que el conductor realmente venga, la simulación debe estar corriendo.
      const estado = usarAlmacen.getState().simulacion?.estado;
      if (estado !== "EJECUTANDO") {
        const nuevo = await api.controlar(estado === "PAUSADA" ? "reanudar" : "iniciar");
        usarAlmacen.getState().fijarSimulacion(nuevo);
        notificar("info", "Simulación en marcha para que tu conductor avance (×1 = tiempo real)");
      }
      setVerDetalle(false);
      setPaso("viaje");
    } catch (e) {
      notificar("error", e instanceof ErrorApi ? e.message : "No se pudo confirmar el viaje");
    } finally {
      setConfirmando(false);
    }
  };

  const nuevaSolicitud = () => {
    setPaso("formulario");
    setResultado(null);
    setCotizacion(null);
    setElegido(null);
    setOrigen(null);
    setDestino(null);
    setSeguirVehiculo(false);
    setErrorBusqueda(null);
    setEligiendoPunto("origen");
  };

  // ---------------------------------------------------------------- datos del mapa por paso
  const candidatoElegido = cotizacion?.candidatos.find((c) => c.id_conductor === elegido);
  const candidatosMapa: Candidato[] | undefined = useMemo(
    () => cotizacion?.candidatos.map((c) => ({ ...c, seleccionado: c.id_conductor === elegido })),
    [cotizacion, elegido],
  );
  const contextoMapa = useMemo(
    () => (cotizacion?.cercanos ?? []).map(([id, lat, lon]) => [id, lat, lon, "DISPONIBLE"] as [number, number, number, EstadoConductor]),
    [cotizacion],
  );
  const vehiculo: VehiculoSeguido | null = useMemo(() => {
    if (!viaje?.conductor || viaje.fase === "cancelado") return null;
    return { lon: viaje.conductor.longitud, lat: viaje.conductor.latitud, rumbo: viaje.conductor.rumbo };
  }, [viaje]);

  let mapa: Record<string, unknown>;
  if (paso === "eligiendo" && cotizacion) {
    // Encuadre en el pasajero y sus candidatos (no en todo el viaje) para ver de dónde vendría cada auto.
    const puntos: [number, number][] = cotizacion.candidatos.map((c) => [c.longitud, c.latitud]);
    if (origen) puntos.push([origen.longitud, origen.latitud]);
    mapa = { candidatos: candidatosMapa, contexto: contextoMapa, rutaRecogida: candidatoElegido?.ruta_recogida, rutaViaje: cotizacion.ruta_viaje,
      claveEncuadre: "eligiendo", puntosEncuadre: puntos };
  } else if (paso === "viaje" && viaje) {
    mapa = {
      vehiculo,
      rutaRecogida: viaje.fase === "recogida" ? viaje.ruta_restante : undefined,
      rutaViaje: viaje.fase === "recogida" ? viaje.ruta_viaje : viaje.fase === "viaje" ? viaje.ruta_restante : resultado?.ruta_viaje,
      pasajeroABordo: viaje.fase === "viaje" || viaje.fase === "finalizado",
      seguirVehiculo: seguirVehiculo && viajeActivo,
      claveEncuadre: `${idPasajero}-${viaje.fase}`,
      // Recogida: el auto, su ruta y el pasajero. Viaje: lo que falta hasta el destino.
      puntosEncuadre: viaje.fase === "recogida"
        ? [...viaje.ruta_restante, ...(origen ? [[origen.longitud, origen.latitud] as [number, number]] : [])]
        : viaje.fase === "viaje" ? [...viaje.ruta_restante, ...(destino ? [[destino.longitud, destino.latitud] as [number, number]] : [])]
        : undefined,
    };
  } else {
    mapa = {};
  }

  const titulos: Record<Paso, [string, string]> = {
    formulario: ["Solicitar servicio", `Distrito activo: ${simulacion?.distrito?.nombre ?? "—"}`],
    eligiendo: ["Conductores disponibles", "Paso 2 de 3 · elige o confirma"],
    viaje: ["Tu viaje", resultado?.exito ? `Asignación #${resultado.id_asignacion} · pasajero #${resultado.pasajero.id_pasajero}` : ""],
  };

  return (
    <div className="grid h-full gap-4 p-4 lg:grid-cols-[440px_1fr] lg:p-6">
      <div className="min-h-0 space-y-4 overflow-y-auto">
        <Tarjeta>
          <EncabezadoTarjeta titulo={titulos[paso][0]} subtitulo={titulos[paso][1]} icono={paso === "viaje" ? Navigation : paso === "eligiendo" ? Users : MapPinned}
            accion={paso === "viaje" && resultado?.id_asignacion ? (
              <a className="boton-fantasma text-xs" href={api.urlMapaAsignacion(resultado.id_asignacion)} target="_blank" rel="noreferrer">Folium <ExternalLink size={12} /></a>
            ) : undefined} />

          {paso !== "formulario" && (
            <div className="flex items-center gap-2 border-b border-panel-borde px-5 py-2.5 text-[11px] text-slate-400">
              <span className="h-2 w-2 shrink-0 rounded-full bg-green-500" /><span className="truncate">{origen?.direccion}</span>
              <ArrowRight size={12} className="shrink-0 text-slate-600" />
              <span className="h-2 w-2 shrink-0 rounded-full bg-pink-500" /><span className="truncate">{destino?.direccion}</span>
            </div>
          )}

          <AnimatePresence mode="wait">
            <motion.div key={paso} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }}>
              {paso === "formulario" && (
                <div className="space-y-5 p-5">
                  <SelectorUbicacion etiqueta="Origen (recogida)" color="#22c55e" valor={origen} alCambiar={(u) => { setOrigen(u); setErrorBusqueda(null); }}
                    seleccionandoEnMapa={eligiendoPunto === "origen"} alSeleccionarEnMapa={() => setEligiendoPunto("origen")} />
                  <SelectorUbicacion etiqueta="Destino" color="#ec4899" valor={destino} alCambiar={(u) => { setDestino(u); setErrorBusqueda(null); }}
                    seleccionandoEnMapa={eligiendoPunto === "destino"} alSeleccionarEnMapa={() => setEligiendoPunto("destino")} />
                  <button className="boton-primario w-full py-2.5" disabled={!origen || !destino || buscando || !simulacion?.configurada} onClick={() => cotizar(false)}>
                    {buscando ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} Ver conductores disponibles
                  </button>
                  {errorBusqueda && <div className="rounded-xl border border-red-500/25 bg-red-500/[0.06] p-4 text-sm text-red-200">{errorBusqueda}</div>}
                  <p className="text-[11px] leading-relaxed text-slate-500">
                    El backend ubica cada punto en la red vial (Quadtree propio), busca los {simulacion?.configuracion?.cantidad_candidatos ?? 5} conductores
                    disponibles más cercanos (Haversine + heap) y calcula su tiempo real de llegada con Dijkstra. Luego eliges a tu conductor.
                  </p>
                </div>
              )}

              {paso === "eligiendo" && cotizacion && (
                <ElegirConductor cotizacion={cotizacion} elegido={elegido} alElegir={setElegido} alConfirmar={confirmar}
                  alVolver={() => { setPaso("formulario"); setCotizacion(null); }} alActualizar={() => cotizar(true)}
                  confirmando={confirmando} actualizando={actualizando} />
              )}

              {paso === "viaje" && (
                viaje ? (
                  <SeguimientoViaje datos={viaje} seguirVehiculo={seguirVehiculo} alAlternarSeguimiento={() => setSeguirVehiculo((v) => !v)} alNuevaSolicitud={nuevaSolicitud} />
                ) : errorViaje ? (
                  <div className="space-y-3 p-5 text-sm text-amber-200">
                    <p>{errorViaje}</p>
                    <button className="boton-primario w-full" onClick={nuevaSolicitud}>Nueva solicitud</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 p-5 text-sm text-slate-400"><Loader2 size={15} className="animate-spin" /> Conectando con tu conductor…</div>
                )
              )}
            </motion.div>
          </AnimatePresence>
        </Tarjeta>

        {paso === "viaje" && resultado?.exito && (
          <Tarjeta>
            <button className="flex w-full items-center justify-between px-5 py-3 text-left text-sm text-slate-200" onClick={() => setVerDetalle((v) => !v)}>
              <span>¿Por qué este conductor? <span className="text-xs text-slate-500">({resultado.candidatos.length} candidatos evaluados)</span></span>
              <ChevronDown size={16} className={`text-slate-400 transition ${verDetalle ? "rotate-180" : ""}`} />
            </button>
            <AnimatePresence initial={false}>
              {verDetalle && (
                <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} className="overflow-hidden border-t border-panel-borde">
                  <DetalleAsignacion resultado={resultado} />
                </motion.div>
              )}
            </AnimatePresence>
          </Tarjeta>
        )}
      </div>

      <Tarjeta className="relative min-h-[420px] overflow-hidden">
        <MapaRuta alHacerClic={paso === "formulario" && eligiendoPunto ? alHacerClic : undefined} centroInicial={simulacion?.distrito?.centro} limite={limite}
          origen={origen ? [origen.longitud, origen.latitud] : null} destino={destino ? [destino.longitud, destino.latitud] : null}
          alSeleccionarCandidato={paso === "eligiendo" ? setElegido : undefined} duracionTransicionMs={INTERVALO_SEGUIMIENTO_MS} {...mapa} />
        {paso === "formulario" && eligiendoPunto && (
          <div className="pointer-events-none absolute left-1/2 top-4 -translate-x-1/2 rounded-full bg-slate-950/85 px-4 py-1.5 text-xs text-cyan-200 ring-1 ring-cyan-400/30">
            Haga clic en el mapa para fijar el {eligiendoPunto}
          </div>
        )}
        {paso === "eligiendo" && (
          <div className="pointer-events-none absolute left-1/2 top-4 -translate-x-1/2 rounded-full bg-slate-950/85 px-4 py-1.5 text-xs text-cyan-200 ring-1 ring-cyan-400/30">
            Toca un candidato numerado para elegirlo · puntos verdes: disponibles cerca
          </div>
        )}
        <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-3 rounded-lg bg-slate-950/80 px-3 py-2 text-[11px] text-slate-300">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-blue-500" /> Recogida</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 border-t-2 border-dashed border-pink-500" /> Viaje</span>
          {paso === "viaje" ? (
            <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-gradient-to-br from-blue-500 to-cyan-400" /> Tu conductor</span>
          ) : (
            <>
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-cyan-400" /> Elegido</span>
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-violet-400" /> Candidato</span>
              <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-green-500" /> Disponible</span>
            </>
          )}
        </div>
      </Tarjeta>
    </div>
  );
}

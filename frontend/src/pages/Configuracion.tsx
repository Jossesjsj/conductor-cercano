import { useEffect, useState } from "react";
import { Loader2, MapPinned, Save, Settings2, SlidersHorizontal, Zap } from "lucide-react";
import { SelectorDistrito } from "@/features/distritos/SelectorDistrito";
import { api, ErrorApi } from "@/services/api";
import type { ConfiguracionSimulacion, Distrito } from "@/services/tipos";
import { usarAlmacen } from "@/stores/almacen";
import { notificar } from "@/stores/notificaciones";
import { CampoNumero, EncabezadoTarjeta, Tarjeta } from "@/components/ui/Primitivos";
import { formatoFecha } from "@/components/ui/formato";

const POR_DEFECTO: ConfiguracionSimulacion = {
  id_distrito: "miraflores", cantidad_conductores: 1500, semilla: 42, velocidad_promedio_kmh: 30, variacion_velocidad: 0.15,
  proporcion_inactivos: 0.03, cantidad_candidatos: 5, radio_inicial_metros: 250,
  multiplicador_velocidad: 1, intervalo_actualizacion_s: 0.5, modo: "AUTOMATICO", solicitudes_por_minuto: 6,
  tipo_visualizacion: "2D", capacidad_quadtree: 16,
};

function Segmentado<T extends string>({ opciones, valor, alCambiar }: { opciones: { valor: T; texto: string }[]; valor: T; alCambiar: (v: T) => void }) {
  return (
    <div className="mt-1.5 grid grid-flow-col gap-1 rounded-lg bg-slate-900/70 p-1">
      {opciones.map((o) => (
        <button key={o.valor} type="button" onClick={() => alCambiar(o.valor)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${valor === o.valor ? "bg-gradient-to-r from-blue-600 to-cyan-500 text-white" : "text-slate-400 hover:text-white"}`}>
          {o.texto}
        </button>
      ))}
    </div>
  );
}

export function Configuracion() {
  const simulacion = usarAlmacen((s) => s.simulacion);
  const [config, setConfig] = useState<ConfiguracionSimulacion>(POR_DEFECTO);
  const [distrito, setDistrito] = useState<Distrito | null>(null);
  const [aplicando, setAplicando] = useState(false);
  const [historial, setHistorial] = useState<{ id: number; fecha: string; datos: ConfiguracionSimulacion }[]>([]);

  useEffect(() => {
    if (simulacion?.configuracion) setConfig(simulacion.configuracion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simulacion?.id_configuracion]);
  useEffect(() => {
    api.configuraciones().then(setHistorial).catch(() => undefined);
  }, [simulacion?.id_configuracion]);
  useEffect(() => {
    api.distritos().then((l) => setDistrito(l.find((d) => d.id_distrito === config.id_distrito) ?? null)).catch(() => undefined);
  }, [config.id_distrito]);

  const fijar = <K extends keyof ConfiguracionSimulacion>(clave: K, valor: ConfiguracionSimulacion[K]) => setConfig((c) => ({ ...c, [clave]: valor }));

  const aplicar = async () => {
    setAplicando(true);
    try {
      const estado = await api.configurar(config);
      usarAlmacen.getState().fijarSimulacion(estado);
      usarAlmacen.getState().reiniciarVista();
      usarAlmacen.getState().fijarModo3D(config.tipo_visualizacion === "3D");
      notificar("exito", `Flota de ${config.cantidad_conductores.toLocaleString("es-PE")} conductores generada en ${estado.distrito?.nombre}`);
    } catch (e) {
      notificar("error", e instanceof ErrorApi ? e.message : "No se pudo aplicar la configuración");
    } finally {
      setAplicando(false);
    }
  };

  const aplicarEnCaliente = async () => {
    try {
      const { multiplicador_velocidad, intervalo_actualizacion_s, solicitudes_por_minuto, modo, tipo_visualizacion, cantidad_candidatos, radio_inicial_metros } = config;
      const estado = await api.parametros({ multiplicador_velocidad, intervalo_actualizacion_s, solicitudes_por_minuto, modo, tipo_visualizacion, cantidad_candidatos, radio_inicial_metros });
      usarAlmacen.getState().fijarSimulacion(estado);
      usarAlmacen.getState().fijarModo3D(tipo_visualizacion === "3D");
      notificar("exito", "Parámetros actualizados sin regenerar la flota");
    } catch (e) {
      notificar("error", e instanceof ErrorApi ? e.message : "No se pudieron actualizar los parámetros");
    }
  };

  const listoParaAplicar = distrito?.descargado && Object.values(config).every((v) => typeof v !== "number" || Number.isFinite(v));

  return (
    <div className="mx-auto grid max-w-[1500px] gap-4 p-4 lg:grid-cols-[380px_1fr] lg:p-6">
      <Tarjeta className="flex h-[calc(100vh-140px)] min-h-[480px] flex-col overflow-hidden">
        <EncabezadoTarjeta titulo="Distrito" subtitulo="Límites oficiales OSM · mínimo 3 km²" icono={MapPinned} />
        <div className="min-h-0 flex-1">
          <SelectorDistrito seleccionado={config.id_distrito} alSeleccionar={(id) => fijar("id_distrito", id)} />
        </div>
      </Tarjeta>

      <div className="space-y-4">
        <Tarjeta>
          <EncabezadoTarjeta titulo="Flota y algoritmo" subtitulo="Requiere regenerar la flota (reproducible por semilla)" icono={Settings2} />
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
            <CampoNumero etiqueta="Número de conductores" valor={config.cantidad_conductores} min={0} max={50000} paso={100} alCambiar={(v) => fijar("cantidad_conductores", v)} ayuda="Pruebe 300, 3 000 o 30 000" />
            <CampoNumero etiqueta="Semilla aleatoria" valor={config.semilla} min={0} alCambiar={(v) => fijar("semilla", v)} ayuda="Misma semilla ⇒ misma flota y decisiones" />
            <CampoNumero etiqueta="Velocidad promedio" valor={config.velocidad_promedio_kmh} min={5} max={120} unidad="km/h" alCambiar={(v) => fijar("velocidad_promedio_kmh", v)} ayuda="Base del ETA (30 km/h por defecto)" />
            <CampoNumero etiqueta="Variación de velocidad" valor={config.variacion_velocidad} min={0} max={0.5} paso={0.05} alCambiar={(v) => fijar("variacion_velocidad", v)} ayuda="±fracción por conductor (0 = homogénea)" />
            <CampoNumero etiqueta="Proporción de inactivos" valor={config.proporcion_inactivos} min={0} max={0.9} paso={0.01} alCambiar={(v) => fijar("proporcion_inactivos", v)} />
            <CampoNumero etiqueta="Capacidad de nodo Quadtree" valor={config.capacidad_quadtree} min={1} max={512} alCambiar={(v) => fijar("capacidad_quadtree", v)} />
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-panel-borde px-5 py-3">
            <span className="text-xs text-slate-400">{distrito ? (distrito.descargado ? `Red vial de ${distrito.nombre} disponible` : `Descargue primero la red vial de ${distrito.nombre}`) : "Seleccione un distrito"}</span>
            <button className="boton-primario" disabled={!listoParaAplicar || aplicando} onClick={aplicar}>
              {aplicando ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Aplicar y generar flota
            </button>
          </div>
        </Tarjeta>

        <Tarjeta>
          <EncabezadoTarjeta titulo="Simulación y visualización" subtitulo="Se aplican en caliente, sin regenerar la flota" icono={SlidersHorizontal} />
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">
            <label className="block"><span className="etiqueta">Modo de movimiento</span>
              <Segmentado valor={config.modo} alCambiar={(v) => fijar("modo", v)} opciones={[{ valor: "AUTOMATICO", texto: "Automático" }, { valor: "MANUAL", texto: "Manual" }]} />
              <span className="mt-1 block text-[11px] text-slate-500">Automático genera demanda; manual solo atiende sus solicitudes</span>
            </label>
            <label className="block"><span className="etiqueta">Tipo de visualización</span>
              <Segmentado valor={config.tipo_visualizacion} alCambiar={(v) => fijar("tipo_visualizacion", v)} opciones={[{ valor: "2D", texto: "2D" }, { valor: "3D", texto: "3D" }]} />
            </label>
            <CampoNumero etiqueta="Número de candidatos (k)" valor={config.cantidad_candidatos} min={1} max={50} alCambiar={(v) => fijar("cantidad_candidatos", v)} />
            <CampoNumero etiqueta="Radio inicial de búsqueda" valor={config.radio_inicial_metros} min={10} max={10000} unidad="m" alCambiar={(v) => fijar("radio_inicial_metros", v)} />
            <CampoNumero etiqueta="Velocidad de simulación" valor={config.multiplicador_velocidad} min={0.1} max={64} paso={0.5} unidad="×" alCambiar={(v) => fijar("multiplicador_velocidad", v)} ayuda="×1 = tiempo real; ×4 = cuatro veces más rápido" />
            <CampoNumero etiqueta="Intervalo de actualización" valor={config.intervalo_actualizacion_s} min={0.05} max={10} paso={0.05} unidad="s" alCambiar={(v) => fijar("intervalo_actualizacion_s", v)} ayuda="Cada cuánto se mueve la flota (fluidez)" />
            <CampoNumero etiqueta="Demanda automática" valor={config.solicitudes_por_minuto} min={0} max={600} unidad="sol/min" alCambiar={(v) => fijar("solicitudes_por_minuto", v)} />
          </div>
          <div className="flex justify-end border-t border-panel-borde px-5 py-3">
            <button className="boton-secundario" disabled={!simulacion?.configurada} onClick={aplicarEnCaliente}><Zap size={15} /> Aplicar en caliente</button>
          </div>
        </Tarjeta>

        <Tarjeta>
          <EncabezadoTarjeta titulo="Configuraciones guardadas" subtitulo="Cada simulación registra su configuración y semilla" />
          <div className="max-h-64 overflow-y-auto">
            <table className="tabla w-full">
              <thead className="border-b border-panel-borde"><tr><th>ID</th><th>Fecha</th><th>Distrito</th><th>Conductores</th><th>Semilla</th><th>Modo</th><th /></tr></thead>
              <tbody className="divide-y divide-panel-borde">
                {historial.map((h) => (
                  <tr key={h.id}>
                    <td className="num text-cyan-300">#{h.id}</td><td className="num text-slate-400">{formatoFecha(h.fecha)}</td><td>{h.datos.id_distrito}</td>
                    <td className="num">{h.datos.cantidad_conductores.toLocaleString("es-PE")}</td><td className="num">{h.datos.semilla}</td><td>{h.datos.modo}</td>
                    <td><button className="text-xs text-acento-suave hover:underline" onClick={() => setConfig({ ...POR_DEFECTO, ...h.datos })}>Cargar</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      </div>
    </div>
  );
}

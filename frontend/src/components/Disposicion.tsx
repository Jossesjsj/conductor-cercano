import { AnimatePresence, motion } from "framer-motion";
import { BarChart3, History, LayoutDashboard, MapPinned, Radar, Settings2, Wifi, WifiOff, X } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { usarSincronizacion } from "@/hooks/usarSimulacion";
import { usarAlmacen } from "@/stores/almacen";
import { usarNotificaciones } from "@/stores/notificaciones";
import { ControlesSimulacion } from "./ControlesSimulacion";
import { Insignia } from "./ui/Primitivos";

const NAVEGACION = [
  { a: "/", texto: "Dashboard", icono: LayoutDashboard },
  { a: "/operaciones", texto: "Centro de operaciones", icono: Radar },
  { a: "/solicitar", texto: "Solicitar servicio", icono: MapPinned },
  { a: "/historial", texto: "Historial", icono: History },
  { a: "/configuracion", texto: "Configuración", icono: Settings2 },
  { a: "/benchmarks", texto: "Benchmarks", icono: BarChart3 },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-blue-600 to-cyan-400 shadow-brillo">
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <circle cx="12" cy="12" r="6.5" />
          <circle cx="12" cy="12" r="1.8" fill="currentColor" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        </svg>
      </div>
      <div className="leading-tight">
        <div className="text-[13px] font-bold tracking-[0.14em] text-white">CONDUCTOR</div>
        <div className="text-[13px] font-bold tracking-[0.14em] text-cyan-300">CERCANO</div>
      </div>
    </div>
  );
}

function EstadoConexion() {
  const conexion = usarAlmacen((s) => s.conexion);
  const estilos = {
    conectado: "text-green-400 bg-green-500/10 ring-green-500/25",
    conectando: "text-amber-300 bg-amber-500/10 ring-amber-500/25",
    desconectado: "text-red-300 bg-red-500/10 ring-red-500/25",
  }[conexion];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${estilos}`}>
      {conexion === "conectado" ? <Wifi size={12} /> : <WifiOff size={12} />}
      {conexion === "conectado" ? "Tiempo real" : conexion === "conectando" ? "Conectando…" : "Reconectando…"}
    </span>
  );
}

function Notificaciones() {
  const { lista, descartar } = usarNotificaciones();
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[340px] flex-col gap-2">
      <AnimatePresence>
        {lista.map((n) => (
          <motion.div key={n.id} layout initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, x: 40 }}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-panel backdrop-blur-xl ${
              n.tipo === "error" ? "border-red-500/30 bg-red-950/80 text-red-100" : n.tipo === "exito" ? "border-green-500/30 bg-green-950/80 text-green-100" : "border-slate-600/40 bg-slate-900/90 text-slate-100"}`}>
            <span className="flex-1">{n.texto}</span>
            <button onClick={() => descartar(n.id)} className="text-slate-400 hover:text-white" aria-label="Cerrar"><X size={14} /></button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export function Disposicion() {
  usarSincronizacion();
  const ubicacion = useLocation();
  const simulacion = usarAlmacen((s) => s.simulacion);
  const pantallaCompleta = ubicacion.pathname === "/operaciones";

  return (
    <div className="flex h-full">
      <aside className="hidden w-[232px] shrink-0 flex-col border-r border-panel-borde bg-fondo-2/80 backdrop-blur-xl lg:flex">
        <div className="px-5 pb-6 pt-5"><Logo /></div>
        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAVEGACION.map(({ a, texto, icono: Icono }) => (
            <NavLink key={a} to={a} end={a === "/"}
              className={({ isActive }) => `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                isActive ? "bg-acento/10 text-white" : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-100"}`}>
              {({ isActive }) => (
                <>
                  {isActive && <motion.span layoutId="nav-activo" className="absolute inset-y-1.5 left-0 w-[3px] rounded-full bg-gradient-to-b from-blue-500 to-cyan-400" />}
                  <Icono size={17} className={isActive ? "text-cyan-300" : ""} />
                  {texto}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-xl border border-panel-borde bg-slate-900/40 p-3 text-xs text-slate-400">
          <div className="etiqueta mb-1">Red vial</div>
          <div className="text-slate-200">{simulacion?.distrito?.nombre ?? "Sin distrito"}</div>
          {simulacion?.grafo && (
            <div className="num mt-1 text-[11px]">{simulacion.grafo.nodos.toLocaleString("es-PE")} nodos · {simulacion.grafo.aristas.toLocaleString("es-PE")} aristas</div>
          )}
          <div className="mt-2 text-[10px] text-slate-500">Datos © colaboradores de OpenStreetMap</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[60px] shrink-0 items-center justify-between gap-3 border-b border-panel-borde bg-fondo/70 px-4 backdrop-blur-xl lg:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="lg:hidden"><Logo /></div>
            <div className="hidden min-w-0 items-center gap-2 md:flex">
              <span className="truncate text-sm font-medium text-white">{simulacion?.distrito?.nombre ?? "—"}</span>
              <span className="text-slate-600">/</span>
              <Insignia valor={simulacion?.estado ?? "DETENIDA"} />
              {simulacion?.configuracion && <Insignia valor={simulacion.configuracion.modo} texto={`Modo ${simulacion.configuracion.modo === "AUTOMATICO" ? "automático" : "manual"}`} />}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:block"><ControlesSimulacion compacto /></div>
            <EstadoConexion />
          </div>
        </header>
        <div className="flex justify-center border-b border-panel-borde px-3 py-2 md:hidden">
          <ControlesSimulacion compacto />
        </div>
        <nav className="flex gap-1 overflow-x-auto border-b border-panel-borde px-3 py-2 lg:hidden">
          {NAVEGACION.map(({ a, texto }) => (
            <NavLink key={a} to={a} end={a === "/"} className={({ isActive }) => `whitespace-nowrap rounded-md px-3 py-1.5 text-xs ${isActive ? "bg-acento/15 text-white" : "text-slate-400"}`}>{texto}</NavLink>
          ))}
        </nav>
        <main className={`relative min-h-0 flex-1 ${pantallaCompleta ? "overflow-hidden" : "overflow-y-auto"}`}>
          <AnimatePresence mode="wait">
            <motion.div key={ubicacion.pathname} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }} className="h-full">
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <Notificaciones />
    </div>
  );
}

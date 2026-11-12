import { useEffect, useState } from "react";
import { BarChart3, FlaskConical } from "lucide-react";
import { api } from "@/services/api";
import { Cargando, EncabezadoTarjeta, Tarjeta, Vacio } from "@/components/ui/Primitivos";
import { formatoNumero } from "@/components/ui/formato";

interface FilaBusqueda {
  conductores: number;
  lineal: { promedio_ms: number; minimo_ms: number; maximo_ms: number; desviacion_ms: number; examinados_promedio: number };
  quadtree: { promedio_ms: number; minimo_ms: number; maximo_ms: number; desviacion_ms: number; examinados_promedio: number };
  aceleracion: number;
  coincidencias: number;
  consultas: number;
  memoria_quadtree_kb?: number;
}

export function Benchmarks() {
  const [datos, setDatos] = useState<{ resultados: Record<string, any>; graficos: string[] } | null>(null);
  useEffect(() => {
    api.benchmarks().then(setDatos).catch(() => setDatos({ resultados: {}, graficos: [] }));
  }, []);
  if (!datos) return <Cargando />;
  const busqueda = datos.resultados.busqueda_lineal_vs_quadtree;
  const dijkstra = datos.resultados.dijkstra_vs_networkx;

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 p-4 lg:p-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Benchmarks</h1>
        <p className="text-sm text-slate-400">Mediciones reales generadas por <code className="text-cyan-300">python -m benchmark.ejecutar_benchmarks</code> (no simuladas).</p>
      </div>
      {!busqueda && !dijkstra && <Tarjeta><Vacio titulo="Aún no hay resultados" descripcion="Ejecute el módulo de benchmarks para generar los resultados y gráficos." /></Tarjeta>}

      {busqueda && (
        <Tarjeta>
          <EncabezadoTarjeta titulo="Búsqueda de k=5 vecinos: lineal vs. Quadtree" icono={FlaskConical}
            subtitulo={`${busqueda.parametros?.consultas} consultas × ${busqueda.parametros?.repeticiones} repeticiones · distrito ${busqueda.parametros?.distrito} · Python ${busqueda.entorno?.python ?? "—"}`} />
          <div className="overflow-x-auto">
            <table className="tabla w-full">
              <thead className="border-b border-panel-borde"><tr>
                <th>Conductores</th><th className="text-right">Lineal prom.</th><th className="text-right">Lineal mín–máx</th><th className="text-right">Quadtree prom.</th>
                <th className="text-right">Quadtree mín–máx</th><th className="text-right">σ Quadtree</th><th className="text-right">Examinados (lineal / QT)</th><th className="text-right">Aceleración</th><th className="text-right">Exactitud</th>
              </tr></thead>
              <tbody className="divide-y divide-panel-borde">
                {(busqueda.filas as FilaBusqueda[]).map((f) => (
                  <tr key={f.conductores}>
                    <td className="num">{formatoNumero(f.conductores)}</td>
                    <td className="num text-right">{formatoNumero(f.lineal.promedio_ms, 3)} ms</td>
                    <td className="num text-right text-slate-400">{formatoNumero(f.lineal.minimo_ms, 3)}–{formatoNumero(f.lineal.maximo_ms, 3)}</td>
                    <td className="num text-right text-cyan-300">{formatoNumero(f.quadtree.promedio_ms, 3)} ms</td>
                    <td className="num text-right text-slate-400">{formatoNumero(f.quadtree.minimo_ms, 3)}–{formatoNumero(f.quadtree.maximo_ms, 3)}</td>
                    <td className="num text-right">{formatoNumero(f.quadtree.desviacion_ms, 4)}</td>
                    <td className="num text-right">{formatoNumero(f.lineal.examinados_promedio)} / {formatoNumero(f.quadtree.examinados_promedio, 1)}</td>
                    <td className="num text-right font-semibold text-green-400">×{formatoNumero(f.aceleracion, 1)}</td>
                    <td className="num text-right">{f.coincidencias}/{f.consultas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      )}

      {dijkstra && (
        <Tarjeta>
          <EncabezadoTarjeta titulo="Dijkstra propio vs. NetworkX (validación)" icono={FlaskConical} subtitulo={`${dijkstra.parametros?.pares} pares de nodos por distrito`} />
          <div className="overflow-x-auto">
            <table className="tabla w-full">
              <thead className="border-b border-panel-borde"><tr>
                <th>Distrito</th><th className="text-right">Nodos</th><th className="text-right">Aristas</th><th className="text-right">Propio prom.</th><th className="text-right">NetworkX prom.</th>
                <th className="text-right">Nodos explorados</th><th className="text-right">Long. ruta (nodos)</th><th className="text-right">Dif. máx. distancia</th><th className="text-right">Coinciden</th>
              </tr></thead>
              <tbody className="divide-y divide-panel-borde">
                {(dijkstra.filas as any[]).map((f) => (
                  <tr key={f.distrito}>
                    <td>{f.distrito}</td><td className="num text-right">{formatoNumero(f.nodos)}</td><td className="num text-right">{formatoNumero(f.aristas)}</td>
                    <td className="num text-right text-cyan-300">{formatoNumero(f.propio_promedio_ms, 3)} ms</td><td className="num text-right">{formatoNumero(f.networkx_promedio_ms, 3)} ms</td>
                    <td className="num text-right">{formatoNumero(f.nodos_explorados_promedio, 0)}</td><td className="num text-right">{formatoNumero(f.longitud_ruta_promedio, 1)}</td>
                    <td className="num text-right">{f.diferencia_maxima_m.toExponential(2)} m</td><td className="num text-right text-green-400">{f.coincidencias}/{f.pares_validos}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      )}

      {datos.graficos.length > 0 && (
        <Tarjeta>
          <EncabezadoTarjeta titulo="Gráficos (Matplotlib)" subtitulo="benchmark/resultados/*.png" icono={BarChart3} />
          <div className="grid gap-4 p-5 lg:grid-cols-2">
            {datos.graficos.map((g) => (
              <figure key={g} className="overflow-hidden rounded-xl border border-panel-borde bg-white">
                <img src={api.urlGrafico(g)} alt={g} loading="lazy" className="w-full" />
                <figcaption className="bg-panel-solido px-3 py-2 text-xs text-slate-400">{g}</figcaption>
              </figure>
            ))}
          </div>
        </Tarjeta>
      )}
    </div>
  );
}

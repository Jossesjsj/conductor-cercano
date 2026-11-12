import { CheckCircle2, CircleSlash } from "lucide-react";
import type { Candidato } from "@/services/tipos";
import { formatoDistancia } from "@/components/ui/formato";

/** Los k candidatos evaluados, con distancias Haversine y por calles y su ETA. */
export function TablaCandidatos({ candidatos, compacta = false }: { candidatos: Candidato[]; compacta?: boolean }) {
  const ordenados = [...candidatos].sort((a, b) => a.distancia_haversine_m - b.distancia_haversine_m);
  const etaMaximo = Math.max(1, ...candidatos.map((c) => c.eta_segundos ?? 0));
  return (
    <div className="overflow-x-auto">
      <table className="tabla w-full">
        <thead className="border-b border-panel-borde">
          <tr>
            <th>#</th>
            <th>Conductor</th>
            {!compacta && <th>Velocidad</th>}
            <th className="text-right">Haversine</th>
            <th className="text-right">Por calles</th>
            <th>ETA</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-panel-borde">
          {ordenados.map((c, i) => (
            <tr key={c.id_conductor} className={c.seleccionado ? "bg-cyan-500/[0.07]" : ""}>
              <td className="num text-slate-500">{i + 1}</td>
              <td>
                <div className="flex items-center gap-2">
                  {c.seleccionado ? <CheckCircle2 size={14} className="text-cyan-300" /> : !c.valido ? <CircleSlash size={14} className="text-slate-500" /> : <span className="w-3.5" />}
                  <div>
                    <div className={c.seleccionado ? "font-semibold text-cyan-200" : ""}>#{c.id_conductor} {!compacta && <span className="text-slate-400">· {c.nombre}</span>}</div>
                    {!compacta && <div className="text-[11px] text-slate-500">{c.placa} · {c.motivo}</div>}
                  </div>
                </div>
              </td>
              {!compacta && <td className="num text-slate-300">{c.velocidad_kmh} km/h</td>}
              <td className="num text-right">{formatoDistancia(c.distancia_haversine_m)}</td>
              <td className="num text-right">{c.valido ? formatoDistancia(c.distancia_ruta_m) : "sin ruta"}</td>
              <td className="min-w-[130px]">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
                    <div className={`h-full rounded-full ${c.seleccionado ? "bg-gradient-to-r from-blue-500 to-cyan-400" : "bg-slate-500"}`}
                      style={{ width: `${c.eta_segundos ? (c.eta_segundos / etaMaximo) * 100 : 0}%` }} />
                  </div>
                  <span className="num w-[72px] text-right text-xs">{c.eta_texto}</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

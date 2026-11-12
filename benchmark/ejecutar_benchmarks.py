"""Ejecuta todos los benchmarks y guarda resultados (JSON) y gráficos (PNG) en benchmark/resultados/.

Uso:  python -m benchmark.ejecutar_benchmarks [--distrito san-juan-de-lurigancho] [--rapido]
Requiere los grafos descargados (python -m benchmark.descargar_distritos ...).
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.configuracion.ajustes import obtener_ajustes
from backend.servicios.catalogo_distritos import CatalogoDistritos
from backend.servicios.gestor_grafos import GestorGrafos
from benchmark import benchmark_busqueda, benchmark_dijkstra, graficos

DIRECTORIO = Path(__file__).resolve().parent / "resultados"
DISTRITOS_DIJKSTRA = ["miraflores", "san-isidro", "lima", "santiago-de-surco", "callao", "san-juan-de-lurigancho"]


def entorno() -> dict[str, str]:
    import psutil

    return {
        "fecha": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "sistema": f"{platform.system()} {platform.release()}",
        "procesador": platform.processor() or platform.machine(),
        "nucleos_logicos": str(psutil.cpu_count()),
        "memoria_gb": f"{psutil.virtual_memory().total / 2**30:.1f}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--distrito", default="san-juan-de-lurigancho", help="distrito para el benchmark de búsqueda")
    parser.add_argument("--rapido", action="store_true", help="menos consultas (verificación rápida)")
    args = parser.parse_args()

    ajustes = obtener_ajustes()
    gestor = GestorGrafos(ajustes, CatalogoDistritos(ajustes))
    datos_entorno = entorno()
    DIRECTORIO.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Búsqueda lineal vs Quadtree en {args.distrito}")
    grafo = gestor.cargar_grafo(args.distrito)
    busqueda = benchmark_busqueda.ejecutar(grafo, args.distrito, consultas=60 if args.rapido else 200,
                                           repeticiones=2 if args.rapido else 5)
    busqueda["entorno"] = datos_entorno

    print("[2/3] Dijkstra propio vs NetworkX")
    filas, muestras = [], {}
    for id_distrito in DISTRITOS_DIJKSTRA:
        if not gestor.esta_descargado(id_distrito):
            print(f"  (omitido: {id_distrito} no descargado)")
            continue
        fila, tiempos = benchmark_dijkstra.ejecutar_distrito(gestor.cargar_grafo(id_distrito), id_distrito,
                                                             pares=30 if args.rapido else 100)
        filas.append(fila)
        muestras[id_distrito] = tiempos
    dijkstra = {"parametros": {"pares": 30 if args.rapido else 100, "tolerancia_m": benchmark_dijkstra.TOLERANCIA_M},
                "filas": filas, "muestras": muestras, "entorno": datos_entorno}

    (DIRECTORIO / "busqueda_lineal_vs_quadtree.json").write_text(json.dumps(busqueda, ensure_ascii=False, indent=1), encoding="utf-8")
    (DIRECTORIO / "dijkstra_vs_networkx.json").write_text(json.dumps(dijkstra, ensure_ascii=False, indent=1), encoding="utf-8")

    print("[3/3] Gráficos")
    for ruta in graficos.generar(busqueda, dijkstra, DIRECTORIO):
        print(f"  {ruta.relative_to(DIRECTORIO.parent.parent)}")
    if any(f["coincidencias"] != f["pares"] for f in filas) or any(f["coincidencias"] != f["consultas"] for f in busqueda["filas"]):
        print("ADVERTENCIA: hay discrepancias de exactitud; revise los JSON")
        sys.exit(1)


if __name__ == "__main__":
    main()

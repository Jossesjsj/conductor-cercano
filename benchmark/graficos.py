"""Gráficos Matplotlib de los benchmarks (a partir de mediciones reales en JSON).

Paleta validada (CVD ΔE ≥ 24): azul = estructura/algoritmo propio, naranja = referencia.
Un solo eje Y por gráfico; leyenda + etiquetas directas selectivas.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AZUL, NARANJA, GRIS, TINTA, TINTA_2 = "#2a78d6", "#eb6834", "#8a8a85", "#1f1f1e", "#5c5c58"


def _estilo() -> None:
    plt.rcParams.update({
        "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.facecolor": "#fcfcfb",
        "axes.edgecolor": "#d6d5d0", "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
        "axes.grid": True, "grid.color": "#ebeae6", "grid.linewidth": 0.8, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10, "axes.titlesize": 12,
        "axes.titleweight": "bold", "axes.titlecolor": TINTA, "legend.frameon": False, "figure.dpi": 110,
    })


def _guardar(figura, ruta: Path) -> None:
    figura.tight_layout()
    figura.savefig(ruta, dpi=160)
    plt.close(figura)


def generar(busqueda: dict[str, Any], dijkstra: dict[str, Any], directorio: Path) -> list[Path]:
    _estilo()
    directorio.mkdir(parents=True, exist_ok=True)
    rutas: list[Path] = []
    filas = busqueda["filas"]
    tamanos = [f["conductores"] for f in filas]
    etiquetas = [f"{n:,}".replace(",", " ") for n in tamanos]
    lineal = [f["lineal"]["promedio_ms"] for f in filas]
    quadtree = [f["quadtree"]["promedio_ms"] for f in filas]

    # 1. Tiempo de búsqueda lineal vs Quadtree (barras agrupadas, escala log).
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    x = range(len(tamanos))
    ancho = 0.36
    b1 = ax.bar([i - ancho / 2 - 0.01 for i in x], lineal, ancho, color=NARANJA, label="Búsqueda lineal")
    b2 = ax.bar([i + ancho / 2 + 0.01 for i in x], quadtree, ancho, color=AZUL, label="Quadtree propio")
    ax.set_yscale("log")
    ax.set_xticks(list(x), etiquetas)
    ax.set_xlabel("Conductores en la flota")
    ax.set_ylabel("Tiempo medio por consulta (ms, escala log)")
    ax.set_title("Búsqueda de los 5 disponibles más cercanos")
    for barras in (b1, b2):
        for b in barras:
            ax.annotate(f"{b.get_height():.3f}", (b.get_x() + b.get_width() / 2, b.get_height()), ha="center", va="bottom",
                        fontsize=8, color=TINTA_2, xytext=(0, 2), textcoords="offset points")
    ax.legend(loc="upper left")
    rutas.append(directorio / "01_tiempo_lineal_vs_quadtree.png")
    _guardar(fig, rutas[-1])

    # 2. Escalabilidad (log-log) con etiquetas directas.
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot(tamanos, lineal, "-o", color=NARANJA, lw=2, ms=8, label="Búsqueda lineal  O(n)")
    ax.plot(tamanos, quadtree, "-o", color=AZUL, lw=2, ms=8, label="Quadtree  ≈O(log n + k)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(tamanos, etiquetas)
    ax.set_xlabel("Conductores (escala log)")
    ax.set_ylabel("Tiempo medio por consulta (ms, log)")
    ax.set_title("Escalabilidad según el tamaño de la flota")
    ax.annotate(f"×{filas[-1]['aceleracion']:.0f} más rápido", (tamanos[-1], quadtree[-1]), xytext=(-110, 18),
                textcoords="offset points", color=TINTA, fontsize=9, arrowprops={"arrowstyle": "-", "color": GRIS})
    ax.legend(loc="upper left")
    rutas.append(directorio / "02_escalabilidad.png")
    _guardar(fig, rutas[-1])

    # 3. Variabilidad (diagramas de caja por método y tamaño) - un panel por método, mismo eje.
    fig, ejes = plt.subplots(1, 2, figsize=(9, 4), sharey=False)
    for ax, (metodo, color, titulo) in zip(ejes, (("lineal", NARANJA, "Búsqueda lineal"), ("quadtree", AZUL, "Quadtree propio"))):
        datos = [busqueda["muestras"][str(n)][metodo] for n in tamanos]
        caja = ax.boxplot(datos, patch_artist=True, showfliers=False, widths=0.5)
        for parche in caja["boxes"]:
            parche.set(facecolor=color, alpha=0.35, edgecolor=color)
        for elemento in ("whiskers", "caps", "medians"):
            for linea in caja[elemento]:
                linea.set(color=color, linewidth=1.5)
        ax.set_xticks(range(1, len(tamanos) + 1), etiquetas)
        ax.set_title(titulo)
        ax.set_xlabel("Conductores")
        ax.set_ylabel("ms por consulta")
    fig.suptitle("Variabilidad de los tiempos de consulta (sin valores atípicos)", fontweight="bold", color=TINTA)
    rutas.append(directorio / "03_variabilidad_tiempos.png")
    _guardar(fig, rutas[-1])

    # 4. Dijkstra propio vs NetworkX por distrito.
    filas_d = sorted(dijkstra["filas"], key=lambda f: f["nodos"])
    nombres = [f"{f['distrito']}\n({f['nodos']:,} nodos)".replace(",", " ") for f in filas_d]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    x = range(len(filas_d))
    ax.bar([i - 0.19 for i in x], [f["propio_promedio_ms"] for f in filas_d], 0.36, color=AZUL, label="Dijkstra propio (heapq)")
    ax.bar([i + 0.19 for i in x], [f["networkx_promedio_ms"] for f in filas_d], 0.36, color=NARANJA, label="NetworkX (referencia)")
    for i, f in enumerate(filas_d):
        ax.annotate(f"{f['coincidencias']}/{f['pares']} iguales", (i, max(f["propio_promedio_ms"], f["networkx_promedio_ms"])),
                    ha="center", va="bottom", fontsize=8, color=TINTA_2, xytext=(0, 3), textcoords="offset points")
    ax.set_xticks(list(x), nombres, fontsize=8)
    ax.set_ylabel("Tiempo medio por ruta (ms)")
    ax.set_title("Dijkstra propio vs. NetworkX sobre redes viales reales")
    ax.legend(loc="upper left")
    rutas.append(directorio / "04_dijkstra_vs_networkx.png")
    _guardar(fig, rutas[-1])

    # 5. Métricas complementarias: elementos examinados (un eje) y fracción del grafo explorada.
    fig, ejes = plt.subplots(1, 2, figsize=(9.5, 4))
    ax = ejes[0]
    ax.plot(tamanos, [f["lineal"]["examinados_promedio"] for f in filas], "-o", color=NARANJA, lw=2, ms=8, label="Lineal")
    ax.plot(tamanos, [f["quadtree"]["examinados_promedio"] for f in filas], "-o", color=AZUL, lw=2, ms=8, label="Quadtree")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(tamanos, etiquetas)
    ax.set_title("Conductores examinados por consulta")
    ax.set_xlabel("Conductores")
    ax.legend(loc="upper left")
    ax = ejes[1]
    ax.bar(range(len(filas_d)), [100 * f["fraccion_explorada"] for f in filas_d], color=AZUL, width=0.6)
    ax.set_xticks(range(len(filas_d)), [f["distrito"] for f in filas_d], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("% de nodos explorados")
    ax.set_title("Dijkstra con parada temprana")
    rutas.append(directorio / "05_metricas_complementarias.png")
    _guardar(fig, rutas[-1])
    return rutas

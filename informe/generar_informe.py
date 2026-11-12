"""Genera informe.pdf (3–5 páginas) a partir de los resultados reales de benchmark/resultados/.

Uso:  python -m informe.generar_informe
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "benchmark" / "resultados"
AZUL = colors.HexColor("#1c5cab")
GRIS = colors.HexColor("#5c5c58")


def miles(n: float) -> str:
    """Separador de miles con espacio (norma SI), sin alterar el texto circundante."""
    return f"{n:,.0f}".replace(",", " ")


def estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("t", parent=base["Title"], fontSize=17, leading=21, textColor=AZUL, spaceAfter=2),
        "subtitulo": ParagraphStyle("st", parent=base["Normal"], fontSize=9, textColor=GRIS, alignment=1, spaceAfter=8),
        "h1": ParagraphStyle("h1", parent=base["Heading2"], fontSize=11.5, leading=14, textColor=AZUL, spaceBefore=7, spaceAfter=3),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontSize=8.9, leading=11.6, alignment=TA_JUSTIFY, spaceAfter=4),
        "celda": ParagraphStyle("c", parent=base["BodyText"], fontSize=7.6, leading=9.2),
        "pie": ParagraphStyle("pie", parent=base["BodyText"], fontSize=7.4, leading=9, textColor=GRIS, alignment=1, spaceAfter=6),
    }


def tabla(filas, anchos, e):
    datos = [[Paragraph(str(c), e["celda"]) for c in fila] for fila in filas]
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, AZUL),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#d6d5d0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    ]))
    return t


def figura(nombre: str, ancho_cm: float, pie: str, e):
    ruta = RESULTADOS / nombre
    imagen = Image(str(ruta))
    escala = ancho_cm * cm / imagen.imageWidth
    imagen.drawWidth, imagen.drawHeight = imagen.imageWidth * escala, imagen.imageHeight * escala
    return KeepTogether([imagen, Paragraph(pie, e["pie"])])


def generar(salida: Path = RAIZ / "informe.pdf") -> Path:
    e = estilos()
    b = json.loads((RESULTADOS / "busqueda_lineal_vs_quadtree.json").read_text(encoding="utf-8"))
    d = json.loads((RESULTADOS / "dijkstra_vs_networkx.json").read_text(encoding="utf-8"))
    ent = b["entorno"]
    fb = {f["conductores"]: f for f in b["filas"]}
    f30 = fb[max(fb)]
    total_pares = sum(f["pares"] for f in d["filas"])
    total_coinciden = sum(f["coincidencias"] for f in d["filas"])
    P = lambda texto: Paragraph(texto, e["p"])  # noqa: E731
    H = lambda texto: Paragraph(texto, e["h1"])  # noqa: E731

    h: list = [
        Paragraph("CONDUCTOR CERCANO", e["titulo"]),
        Paragraph("Informe técnico · Asignación de conductores con Quadtree, Haversine, heap y Dijkstra propios "
                  f"sobre la red vial real de Lima Metropolitana y Callao · {ent['fecha'][:10]}", e["subtitulo"]),
        H("1. Introducción y planteamiento del problema"),
        P("Una plataforma de movilidad debe responder, en milisegundos, a la pregunta: <i>entre miles de conductores en "
          "movimiento, ¿cuál puede llegar primero al pasajero?</i> La respuesta ingenua (medir la distancia a todos) escala "
          "linealmente y además usa la distancia en línea recta, que no refleja calles de sentido único ni la topología "
          "vial. CONDUCTOR CERCANO resuelve ambos problemas: un <b>Quadtree propio</b> reduce la búsqueda a una vecindad, "
          "<b>Haversine</b> y un <b>heap</b> seleccionan los k=5 candidatos globalmente más cercanos, y <b>Dijkstra propio</b> "
          "sobre el grafo vial dirigido de OpenStreetMap calcula la distancia real y el ETA de cada uno; se asigna el de "
          "menor ETA. Todo se ejecuta en un backend real con simulación de la flota sobre las calles de 46 distritos."),
        H("2. Arquitectura del sistema"),
        P("<b>Backend</b> (Python, FastAPI, Uvicorn): capas separadas en <i>algoritmos/</i> (Haversine, Dijkstra), "
          "<i>estructuras/</i> (NodoQuadtree, Quadtree, GrafoVial), <i>simulacion/</i> (Conductor, Pasajero, Flota, "
          "Despachador, MotorSimulacion, sin dependencias web) y <i>backend/</i> (API REST, WebSocket, servicios, "
          "SQLAlchemy/SQLite). <b>Datos</b>: los límites de distritos se extraen de las relaciones administrativas de OSM; "
          "la red vial se obtiene con OSMnx (<i>network_type=drive</i>, grafo dirigido con sentidos de circulación) desde "
          "Overpass o, si no responde, desde un extracto PBF de OSM recortado al polígono del distrito; se guarda en "
          "<i>datos/grafos/</i> (GraphML) y no se vuelve a descargar. <b>Tiempo real</b>: en cada turno el servidor consulta "
          "el Quadtree con la vista de cada cliente y envía solo los conductores que cambiaron (deltas cuantizados a ~1 m), "
          "con control de frecuencia por cliente y reconexión automática. <b>Frontend</b> (React, TypeScript, Vite, Tailwind, "
          "Framer Motion, Zustand, MapLibre GL y Three.js): dashboard, centro de operaciones 2D/3D (vehículos en "
          "InstancedMesh orientados por rumbo, edificios extruidos, rutas con profundidad), solicitud de servicio con "
          "geocodificación Nominatim, historial y configuración. Persistencia de solicitudes, asignaciones, rutas, "
          "configuraciones, semillas, resultados y métricas; las posiciones por turno no se guardan."),
        H("3. Diseño e implementación del Quadtree"),
        P("Cada <b>NodoQuadtree</b> guarda sus límites, sus elementos (diccionario id→entrada), la capacidad, la profundidad, "
          "su padre, un contador del subárbol y referencias a cuatro hijos (SO, SE, NO, NE). Una hoja se subdivide al superar "
          "la capacidad (16), salvo que alcance la profundidad máxima (20) o que todos sus elementos compartan coordenadas, lo "
          "que evita subdivisiones infinitas. Un índice auxiliar id→hoja permite eliminar en O(profundidad) y garantiza que no "
          "haya duplicados; al eliminar se fusionan los subárboles que vuelven a caber en un nodo. <b>actualizar_posicion</b> "
          "comprueba en O(1) si el punto sigue en la misma hoja (región semiabierta [mín, máx)); si no, elimina y reinserta. "
          "<b>k vecinos exactos</b>: se consulta el rectángulo R(r) que contiene al círculo de radio r (Δφ = δ, "
          "Δλ = asin(sin δ / cos φ), exacto en la esfera), empezando en r = 250 m y duplicando r. Todo punto fuera de R(r) "
          "está a más de r: es la <i>cota inferior de las regiones no exploradas</i>. Cuando hay k candidatos disponibles a "
          "distancia ≤ r, ningún punto no explorado puede superarlos y el resultado es globalmente óptimo; los k mejores se "
          "eligen con <i>heapq.nsmallest</i>. El mismo Quadtree indexa los nodos del grafo para ubicar direcciones en la red "
          "vial (sin índices espaciales de OSMnx)."),
        H("4. Implementación de Haversine y Dijkstra"),
        P("<b>Haversine</b>: d = 2R·asin(√(sin²(Δφ/2) + cos φ<sub>1</sub> cos φ<sub>2</sub> sin²(Δλ/2))) con R = 6 371 008,8 m (radio medio IUGG), "
          "validación de rangos y recorte numérico; se prueba con puntos idénticos, 0,001° (111,195 m), Plaza Mayor–Parque "
          "Kennedy (≈8,4 km), antípodas y antimeridiano. <b>Dijkstra</b>: lista de adyacencia dirigida (se conserva la arista "
          "paralela más corta, longitudes en metros de OSM), cola de prioridad con heapq y <i>lazy deletion</i>, "
          "predecesores para reconstruir la ruta, parada temprana al extraer el destino y manejo explícito de nodos "
          "inexistentes y de destinos inalcanzables. El ETA de recogida es (resto de la arista actual + distancia Dijkstra "
          "desde el siguiente nodo) / velocidad en m/s; la velocidad media configurable es 30 km/h con variación individual "
          "±15 %. La ruta del viaje se calcula después de elegir al conductor."),
        H("5. Integración de las estructuras de datos"),
        P("El <b>Despachador</b> ejecuta, bajo un cerrojo compartido con el motor (sin doble asignación): validación → "
          "ubicación de origen y destino en nodos circulables (Quadtree de nodos, máx. 400 m; si no hay red se informa "
          "«no existe una ruta válida») → k=5 disponibles más cercanos (Quadtree + Haversine + heap) → Dijkstra por candidato "
          "(los que no tienen ruta se descartan sin detener el proceso; si ninguno sirve se evalúa un nuevo lote) → menor ETA "
          "→ cambio de estado → registro y notificación por WebSocket con una justificación textual. El <b>motor</b> avanza a "
          "cada conductor por aristas válidas del grafo dirigido (sin giros en U salvo en calles ciegas), actualiza el "
          "Quadtree tras cada movimiento y gestiona el ciclo DISPONIBLE → OCUPADO → EN_SERVICIO → DISPONIBLE. Tres "
          "generadores derivados de una semilla (flota, movimiento y demanda) hacen la simulación reproducible."),
    ]

    h += [KeepTogether([H("6. Análisis Big-O"), tabla([
        ["Operación", "Complejidad", "Comentario"],
        ["Haversine", "O(1)", "Operaciones trigonométricas constantes"],
        ["Quadtree: insertar / eliminar", "O(h), h ≤ 20", "h ≈ log<sub>4</sub>(n/c) con distribución urbana; fusión amortizada"],
        ["Quadtree: actualizar posición", "O(1) misma hoja; O(h) si cambia", "La mayoría de movimientos de 2 s no cambia de hoja"],
        ["Quadtree: rectángulo", "O(h + m + nodos visitados)", "m = elementos en las hojas intersecadas"],
        ["k vecinos (expansión de radio)", "O(Σ iteraciones · (h + m)) + O(m log k)", "La serie geométrica acota el total a O(última consulta)"],
        ["Búsqueda lineal", "O(n log k)", "Examina siempre los n conductores"],
        ["Dijkstra (heap binario)", "O((V + E) log V)", "Parada temprana: explora una fracción del grafo"],
        ["Turno de simulación", "O(n · h)", "Avance por aristas + actualización del índice"],
        ["Asignación completa", "O(h + m + k (V + E) log V)", "Dominada por las k ejecuciones de Dijkstra"],
    ], [4.6 * cm, 5.0 * cm, 7.4 * cm], e)])]

    filas_b = [["Conductores", "Lineal (ms)", "Quadtree (ms)", "σ QT (ms)", "Examinados lineal / QT", "Aceleración", "Exactitud", "Act. QT (µs/cond.)"]]
    for n in sorted(fb):
        f = fb[n]
        filas_b.append([f"{n:,}".replace(",", " "), f"{f['lineal']['promedio_ms']:.3f}", f"{f['quadtree']['promedio_ms']:.4f}",
                        f"{f['quadtree']['desviacion_ms']:.4f}", f"{miles(f['lineal']['examinados_promedio'])} / {f['quadtree']['examinados_promedio']:.1f}",
                        f"×{f['aceleracion']:.1f}", f"{f['coincidencias']}/{f['consultas']}", f"{f['actualizacion_por_conductor_us']:.1f}"])
    filas_d = [["Distrito", "Nodos", "Aristas", "Propio (ms)", "NetworkX (ms)", "Nodos explorados", "Coinciden", "Dif. máx. (m)"]]
    for f in sorted(d["filas"], key=lambda x: x["nodos"]):
        filas_d.append([f["distrito"], f"{f['nodos']:,}".replace(",", " "), f"{f['aristas']:,}".replace(",", " "),
                        f"{f['propio_promedio_ms']:.2f}", f"{f['networkx_promedio_ms']:.2f}",
                        f"{f['nodos_explorados_promedio']:.0f} ({100 * f['fraccion_explorada']:.0f} %)", f"{f['coincidencias']}/{f['pares']}",
                        f"{f['diferencia_maxima_m']:.1e}"])
    p = b["parametros"]
    h += [
        H("7. Resultados de los benchmarks"),
        P(f"Mediciones reales en {ent['sistema']}, Python {ent['python']}, {ent['nucleos_logicos']} núcleos lógicos, "
          f"{ent['memoria_gb']} GB. Búsqueda: distrito {p['distrito']} ({miles(p['nodos_grafo'])} nodos), conductores ubicados sobre "
          f"calles reales, 30 % ocupados, {p['consultas']} consultas × {p['repeticiones']} repeticiones, k = {p['k']}, mismos "
          "datos para ambas estructuras. Exactitud = coincidencia de los k identificadores con la búsqueda exhaustiva."),
        tabla(filas_b, [2.1 * cm, 1.7 * cm, 2.0 * cm, 1.6 * cm, 3.1 * cm, 2.0 * cm, 1.7 * cm, 2.4 * cm], e),
        Spacer(1, 4),
        figura("02_escalabilidad.png", 12.5, "Figura 1. Tiempo medio por consulta según el tamaño de la flota (escala log-log).", e),
        P(f"Con {miles(max(fb))} conductores el Quadtree responde en {f30['quadtree']['promedio_ms']:.3f} ms frente a "
          f"{f30['lineal']['promedio_ms']:.1f} ms de la búsqueda lineal (×{f30['aceleracion']:.0f}) examinando "
          f"{f30['quadtree']['examinados_promedio']:.0f} elementos en vez de {miles(f30['lineal']['examinados_promedio'])}. Con 300 "
          "conductores la ventaja es menor porque la flota es dispersa y el radio debe expandirse varias veces. La memoria "
          f"del índice para {miles(max(fb))} conductores es ≈{f30['memoria_quadtree_kb'] / 1024:.1f} MB ({f30['nodos_quadtree']} nodos, "
          f"profundidad {f30['profundidad_quadtree']})."),
        P(f"<b>Dijkstra</b>: {d['parametros']['pares']} pares aleatorios de nodos por distrito sobre el mismo DiGraph. "
          f"NetworkX se usa exclusivamente como referencia: {total_coinciden}/{total_pares} distancias coinciden (tolerancia "
          f"{d['parametros']['tolerancia_m']:g} m)."),
        tabla(filas_d, [3.5 * cm, 1.4 * cm, 1.5 * cm, 1.7 * cm, 1.9 * cm, 2.6 * cm, 1.9 * cm, 1.7 * cm], e),
        Spacer(1, 4),
        figura("04_dijkstra_vs_networkx.png", 13.0, "Figura 2. Tiempo medio por ruta: Dijkstra propio frente a NetworkX en seis distritos reales.", e),
        figura("03_variabilidad_tiempos.png", 13.0, "Figura 3. Variabilidad de los tiempos de consulta por método y tamaño de flota.", e),
        KeepTogether([H("8. Comparación con H3 de Uber"), tabla([
            ["Criterio", "Búsqueda lineal", "Quadtree (este proyecto)", "H3 (Uber)"],
            ["Organización espacial", "Ninguna (lista)", "Árbol adaptativo: subdivide solo donde hay densidad", "Malla jerárquica fija de hexágonos (16 resoluciones)"],
            ["Complejidad de consulta", "O(n)", "O(h + m) por rectángulo; k-NN exacto con cota inferior", "O(1) por celda; k-ring de celdas vecinas O(k²)"],
            ["Actualización de posición", "O(1)", "O(1) en la misma hoja; O(h) si cambia", "O(1): recalcular índice de celda y mover entre cubetas"],
            ["Consultas por cercanía", "Exactas pero costosas", "Exactas (radio creciente + cota inferior)", "Aproximadas por anillos; exactitud requiere verificar distancias"],
            ["Ventajas", "Simple, sin estructura", "Se adapta a densidades muy desiguales (centro vs. periferia)", "Vecinos equidistantes, agregación analítica, celdas estables"],
            ["Desventajas", "No escala", "Rebalanceo con movimientos; rectángulos distorsionados en latitudes altas", "Resolución fija: celdas vacías o saturadas; dependencia externa"],
            ["Escalabilidad", "Mala (lineal)", "Buena en memoria de un proceso", "Muy buena y distribuible (claves de celda en cachés/particiones)"],
        ], [3.0 * cm, 2.9 * cm, 5.4 * cm, 5.7 * cm], e)]),
        P("H3 es superior para sistemas distribuidos a escala de ciudad entera (las claves de celda se reparten entre "
          "servidores y sirven para análisis de oferta y demanda), mientras que el Quadtree brilla dentro de un proceso con "
          "distribuciones heterogéneas y garantiza resultados exactos. H3 no se utiliza en la implementación: es solo un "
          "punto de comparación conceptual."),
        H("9. Conclusiones"),
        P(f"(1) El Quadtree propio logra búsquedas exactas de los 5 conductores disponibles más cercanos hasta "
          f"×{f30['aceleracion']:.0f} más rápidas que la búsqueda lineal con {miles(max(fb))} conductores, con "
          f"{sum(f['coincidencias'] for f in b['filas'])}/{sum(f['consultas'] for f in b['filas'])} resultados idénticos a la fuerza bruta. "
          f"(2) El Dijkstra propio reproduce las distancias de NetworkX en {total_coinciden}/{total_pares} casos y, gracias a la "
          "parada temprana y a la lista de adyacencia compacta, es más rápido en todos los distritos medidos. (3) La distancia "
          "en línea recta no basta: en los mapas generados el candidato más cercano en Haversine a menudo no es el de menor ETA "
          "por los sentidos de circulación, lo que justifica evaluar rutas reales. (4) La arquitectura separa dominio, servicios "
          "y presentación, persiste el historial en SQLite, transmite deltas por WebSocket y es reproducible por semilla. "
          "Como trabajo futuro: Dijkstra multiobjetivo inverso (una sola ejecución para los k candidatos), A* con heurística "
          "Haversine y velocidades por tipo de vía."),
    ]
    doc = SimpleDocTemplate(str(salida), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title="CONDUCTOR CERCANO - Informe técnico", author="Equipo CONDUCTOR CERCANO")

    def pie_pagina(lienzo, documento):
        lienzo.saveState()
        lienzo.setFont("Helvetica", 7.5)
        lienzo.setFillColor(GRIS)
        lienzo.drawString(1.8 * cm, 0.9 * cm, "CONDUCTOR CERCANO · Informe técnico · Datos © colaboradores de OpenStreetMap")
        lienzo.drawRightString(A4[0] - 1.8 * cm, 0.9 * cm, f"Página {documento.page}")
        lienzo.restoreState()

    doc.build(h, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    return salida


if __name__ == "__main__":
    ruta = generar()
    print(f"Informe generado: {ruta}")

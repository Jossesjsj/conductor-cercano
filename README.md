# CONDUCTOR CERCANO

**Plataforma inteligente de movilidad, geolocalización y asignación de conductores** sobre la red vial real de
Lima Metropolitana y Callao (OpenStreetMap).

Entre miles de conductores en movimiento, CONDUCTOR CERCANO encuentra al **conductor disponible que llega más rápido**
a un pasajero:

1. **Quadtree propio**: localiza conductores disponibles cerca del pasajero.
2. **Haversine + heap**: selecciona los *k = 5* candidatos **globalmente** más cercanos en línea recta.
3. **Dijkstra propio**: calcula la ruta real de cada candidato sobre el grafo vial **dirigido** (respeta los sentidos de circulación).
4. **Asignación**: elige el conductor con **menor ETA** de recogida y justifica la elección.

Todo se calcula en el backend. El frontend solo representa los resultados: mapas 2D/3D en vivo, historial y benchmarks.

---

## Índice
- [Características](#características)
- [Arquitectura](#arquitectura)
- [Tecnologías](#tecnologías)
- [Requisitos e instalación local](#requisitos-e-instalación-local)
- [Variables de entorno](#variables-de-entorno)
- [Descarga de redes viales](#descarga-de-redes-viales)
- [Ejecución del backend y del frontend](#ejecución-del-backend-y-del-frontend)
- [Ejecución con Docker](#ejecución-con-docker)
- [Pruebas](#pruebas)
- [Benchmarks](#benchmarks)
- [Mapas HTML (Folium)](#mapas-html-folium)
- [Informe técnico](#informe-técnico)
- [Despliegue en Render](#despliegue-en-render)
- [API y WebSocket](#api-y-websocket)
- [Decisiones de diseño y limitaciones](#decisiones-de-diseño-y-limitaciones)

---

## Características

| Área | Qué hace |
|---|---|
| Distritos | Catálogo de **46 distritos** de Lima Metropolitana y Callao con sus **límites oficiales de OSM**. Solo admite los de área ≥ 3 km² (41 elegibles), con descarga bajo demanda, reutilización local, actualización manual y estado de progreso. |
| Red vial | Grafo **dirigido** `drive` de OSMnx: nodos con lat/lon, longitudes en metros, sentidos de circulación e intersecciones simplificadas. |
| Quadtree | `NodoQuadtree` y `Quadtree` propios: inserción, eliminación, búsqueda por rectángulo, actualización de posición, conteo, subdivisión, fusión, sin duplicados y **k-NN exacto** con cota inferior. |
| Algoritmos | **Haversine** y **Dijkstra** implementados desde cero. Solo se usa `heapq` como cola de prioridad. |
| Despacho | `Despachador`: k = 5 candidatos, radio inicial de 250 m con expansión, descarte de candidatos sin ruta, menor ETA, cerrojo contra la doble asignación y justificación textual. |
| Simulación | Movimiento por turnos sobre aristas reales (sin giros en U), modos **automático** (con demanda Poisson) y **manual**, controles iniciar/pausar/reanudar/avanzar/reiniciar/velocidad y **semilla reproducible**. La velocidad está atada al reloj real: cada turno avanza `intervalo × multiplicador` segundos, así que ×1 es tiempo real. |
| Tiempo real | WebSocket con **deltas por vista** (consulta al Quadtree por cliente), control de frecuencia, fusión de turnos para clientes lentos y reconexión con *backoff*. |
| Persistencia | SQLite + SQLAlchemy: configuraciones, semillas, flota, solicitudes, asignaciones, rutas, resultados y métricas. El historial sobrevive al reinicio del servidor. |
| Pedir un viaje | Primero se ven los conductores **disponibles** (en el distrito y a menos de 1 km) y los 5 candidatos con su ETA real. El de menor ETA viene **recomendado y preseleccionado**, pero el pasajero puede elegir otro, en la lista o tocándolo en el mapa. Si el elegido acepta otro viaje antes de confirmar, se asigna el mejor disponible con un aviso. |
| Seguimiento del viaje | Tras confirmar se sigue el viaje en vivo: el auto se acerca por la ruta real, el pasajero sube y viaja hasta su destino. Muestra fases, progreso, ETA y distancia restantes, controles de velocidad, cámara que sigue al auto y un resumen final con la espera real y la duración. |
| Interfaz | Dashboard, centro de operaciones 2D/3D (MapLibre + Three.js con `InstancedMesh`, edificios 3D y rutas extruidas), solicitud de servicio con geocodificación, historial con detalle y Folium, configuración y benchmarks. |
| Calidad | 51 pruebas Pytest (unitarias y de integración), benchmarks reales con Matplotlib, 3 mapas Folium e informe PDF. |

## Arquitectura

```
                 ┌──────────────── Frontend (React + TS + Vite) ────────────────┐
                 │ Dashboard · Operaciones 2D/3D · Solicitar · Historial · ...  │
                 │ Zustand (estado) · flotaVisual (búfer mutable, interpolación)│
                 └───────────────┬──────────────────────────┬───────────────────┘
                         REST /api/*                  WebSocket /ws/tiempo-real
                 ┌───────────────▼──────────────────────────▼───────────────────┐
                 │ backend/  FastAPI: api/ (routers, esquemas Pydantic)          │
                 │           servicios/ (simulación, tiempo real, grafos,        │
                 │           catálogo, geocodificación, repositorio, Folium)     │
                 │           modelos/ (SQLAlchemy → SQLite)                      │
                 └───────────────┬──────────────────────────────────────────────┘
                                 │ (sin dependencias web)
   ┌─────────────────────────────▼─────────────────────────────────────────────┐
   │ simulacion/  Conductor · Pasajero · Flota · Despachador · MotorSimulacion │
   │ estructuras/ NodoQuadtree · Quadtree · GrafoVial · utilidades_geograficas │
   │ algoritmos/  haversine · dijkstra                                         │
   └───────────────────────────────────────────────────────────────────────────┘
   datos/grafos (GraphML)  ·  datos/cache (extracto PBF, catálogo)  ·  datos/base_datos (SQLite)
```

**Flujo de una solicitud**: validación → nodo vial más cercano (Quadtree de nodos) → k = 5 disponibles
(Quadtree + Haversine + heap) → Dijkstra por candidato → menor ETA → estado `OCUPADO` → SQLite → evento WebSocket → mapa.

```
proyecto-conductor-cercano/
├── backend/        api/ modelos/ servicios/ configuracion/ main.py
├── frontend/       src/{components,pages,features,hooks,services,stores,styles}
├── estructuras/    quadtree.py nodo_quadtree.py utilidades_geograficas.py grafo_vial.py
├── algoritmos/     dijkstra.py haversine.py
├── simulacion/     conductor.py pasajero.py flota.py despachador.py motor_simulacion.py
├── benchmark/      benchmark_busqueda.py benchmark_dijkstra.py graficos.py ejecutar_benchmarks.py resultados/
├── mapas/          generar_mapas.py mapa_*.html
├── tests/          Pytest (Quadtree, Haversine, Dijkstra, Despachador, simulación, API)
├── informe/        generar_informe.py
├── datos/          grafos/ cache/ base_datos/
├── Dockerfile · docker-compose.yml · render.yaml · .env.example · informe.pdf
```

## Tecnologías

- **Backend**: Python 3.12+ (probado con 3.14), FastAPI, Uvicorn, Pydantic, SQLAlchemy, SQLite, OSMnx, NetworkX (solo gestión y validación de grafos), pyosmium (lectura del extracto PBF), Folium, Matplotlib, ReportLab y Pytest.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Zustand, MapLibre GL JS, Three.js y lucide-react.
- **Infraestructura**: Docker, Docker Compose y Render (Blueprint `render.yaml`).

> **Restricciones académicas respetadas**: no se usa `networkx.shortest_path`, `single_source_dijkstra`, `dijkstra_path`,
> ni las rutas o `nearest_nodes` de OSMnx, ni KDTree, Rtree, STRtree o H3 en la aplicación. NetworkX solo calcula rutas en
> `tests/` y `benchmark/`, como referencia de validación. La componente fuertemente conexa también es propia (Tarjan iterativo).

## Requisitos e instalación local

- Python ≥ 3.11 · Node.js ≥ 18 · 4 GB de RAM (8 GB recomendados para 30 000 conductores).

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt

# Frontend
cd frontend && npm ci && cd ..
```

## Variables de entorno

Copie `.env.example` a `.env`. Todas las variables usan el prefijo `CC_`:

| Variable | Por defecto | Descripción |
|---|---|---|
| `CC_DIRECTORIO_DATOS` | `./datos` | Grafos, caché y SQLite (en Render: el disco persistente). |
| `CC_URL_BASE_DATOS` | *(vacío)* | Vacío = SQLite en `datos/base_datos/`. |
| `CC_ORIGENES_CORS` | `http://localhost:5173` | Orígenes permitidos si el frontend se sirve aparte. |
| `CC_FUENTE_OSM` | `auto` | `auto` (Overpass y, si falla, extracto), `overpass` o `extracto`. |
| `CC_URL_EXTRACTO_OSM` | BBBike Lima | Extracto PBF de respaldo (o Geofabrik Perú). |
| `CC_URL_NOMINATIM` | nominatim.openstreetmap.org | Geocodificación (máx. 1 solicitud/s, con caché). |
| `CC_DISTRITO_POR_DEFECTO` | `miraflores` | Distrito precargado al iniciar. |
| `CC_CONDUCTORES_POR_DEFECTO` | `1500` | Flota inicial. |
| `CC_MAXIMO_CONDUCTORES_POR_MENSAJE` | `6000` | Tope de vehículos dibujados por cliente (reducción visual determinista). |
| `VITE_API_URL` (frontend) | *(vacío)* | URL del backend si el frontend se despliega por separado. |

## Descarga de redes viales

Los grafos se descargan **una sola vez por distrito** y se guardan en `datos/grafos/<distrito>.graphml`, junto a un JSON de
metadatos (fuente, fecha, nodos y aristas).

```bash
python -m benchmark.descargar_distritos                       # lista el catálogo (✔ = descargado)
python -m benchmark.descargar_distritos miraflores san-isidro santiago-de-surco
python -m benchmark.descargar_distritos --forzar miraflores    # actualización manual
```

También se puede hacer desde **Configuración → Distrito → Descargar / Actualizar**, con progreso en vivo.

**Fuente de datos**: primero se intenta Overpass mediante `osmnx.graph_from_polygon(network_type="drive")`. Si Overpass no
responde (los servidores públicos limitan los clientes automatizados), se usa el extracto **BBBike Lima** (OSM, ~30 MB):
pyosmium filtra las vías conducibles con el mismo criterio que OSMnx, `osmnx.graph_from_xml` crea el grafo dirigido y luego
se recorta al polígono oficial del distrito y se simplifica.

Ejemplos reales: Miraflores tiene 1 681 nodos y 3 233 aristas; San Juan de Lurigancho, 14 336 nodos y 38 095 aristas.

## Ejecución del backend y del frontend

```bash
# Backend (desde la raíz): API en http://localhost:8000 · documentación en /docs
uvicorn backend.main:app --reload --port 8000

# Frontend en desarrollo (proxy /api y /ws hacia :8000): http://localhost:5173
cd frontend && npm run dev

# Producción local: el backend sirve el build de frontend/dist en http://localhost:8000
cd frontend && npm run build && cd .. && uvicorn backend.main:app --port 8000
```

Al iniciar, el backend precarga el último distrito configurado desde la aplicación (o Miraflores) con la simulación **detenida**. Pulse **Iniciar**.

**Pedir y seguir un viaje**: en *Solicitar servicio* elija el origen y el destino (dirección, clic en el mapa o coordenadas) y pulse **Ver conductores disponibles**. Verá cuántos conductores hay disponibles y los candidatos con su tiempo real de llegada. Confirme el recomendado o elija otro. El panel *Tu viaje* muestra al conductor en camino, el momento en que sube el pasajero y el trayecto hasta el destino. Si la simulación estaba detenida o pausada, se pone en marcha al confirmar. ×1 es tiempo real; ×2, ×4 y ×8 aceleran el viaje.

### Ejemplos de uso (API real)

```bash
# Configurar: Santiago de Surco, 3 000 conductores, semilla 7, modo manual
curl -X POST localhost:8000/api/simulacion/configurar -H "Content-Type: application/json" \
     -d '{"id_distrito":"santiago-de-surco","cantidad_conductores":3000,"semilla":7,"modo":"MANUAL"}'

# Solicitar servicio (Parque Kennedy → Larcomar) en Miraflores
curl -X POST localhost:8000/api/solicitudes -H "Content-Type: application/json" \
     -d '{"origen":{"latitud":-12.1219,"longitud":-77.0300},"destino":{"latitud":-12.1336,"longitud":-77.0228}}'

curl -X POST localhost:8000/api/simulacion/avanzar      # un turno (modo manual)
curl "localhost:8000/api/asignaciones?tamano=5"          # historial
curl localhost:8000/api/asignaciones/1/mapa > mapa.html  # mapa Folium de una asignación
```

Fragmento de una respuesta real de `/api/solicitudes`:

```
ASIGNADO · Conductor 845 asignado: ETA 0 min 02 s
candidatos: #845 68 m (Haversine) / 14 m (calles) · #1282 85 m / 466 m · #1491 147 m / 632 m · ...
tiempos_ms: localización 0.40 · Quadtree 0.35 · Dijkstra candidatos 0.80 · viaje 2.32 · total 4.06
```

## Ejecución con Docker

```bash
docker compose up --build        # http://localhost:8000
```

El `Dockerfile` (multietapa) compila el frontend con Node y lo sirve desde FastAPI en una imagen Python *slim* con un
usuario sin privilegios y un *health check* sobre `/api/salud`. El volumen `datos` conserva los grafos y SQLite. En el primer
arranque se descarga el extracto OSM y se procesa el distrito por defecto (alrededor de 1 minuto).

## Pruebas

```bash
pytest                 # 51 pruebas
pytest -m "not red"    # omite la validación sobre el grafo real descargado
```

| Archivo | Cubre |
|---|---|
| `test_quadtree.py` | Inserción en árbol vacío, eliminación, rectángulo frente a fuerza bruta, actualización sin duplicados, puntos idénticos (sin subdivisión infinita), k-NN exacto global, menos elementos que k. |
| `test_haversine.py` | Puntos idénticos, 0,001°, Plaza Mayor → Parque Kennedy, simetría, antípodas, polos, antimeridiano y rangos inválidos. |
| `test_dijkstra.py` | Ruta válida, sin conexión, sentido de las aristas, destino inexistente, comparación con NetworkX en grafos aleatorios y **en la red real de Miraflores**, conversión a ETA. |
| `test_despachador.py` | **Menor ETA en vez del más cercano** (sentido único), exclusión de ocupados e inactivos, sin conductores, **zona sin conexión vial**, candidato sin ruta descartado y 30 hilos concurrentes sin doble asignación. |
| `test_simulacion.py` | **Quadtree actualizado durante los movimientos**, circulación solo por aristas y sin giros en U, **reproducibilidad de la semilla**, ciclo completo del servicio, **seguimiento del viaje** (fases en orden y distancia restante siempre decreciente) y más de 100 000 movimientos automáticos. |
| `test_api_integracion.py` | FastAPI + SQLite + WebSocket: configuración, solicitud, historial, mapa, sin conexión vial, control manual, deltas incrementales, seguimiento del viaje por API y precarga que ignora las configuraciones de scripts. |

## Benchmarks

```bash
python -m benchmark.ejecutar_benchmarks          # JSON y PNG en benchmark/resultados/
python -m benchmark.ejecutar_benchmarks --rapido
```

Resultados **medidos** (Windows 11, Python 3.14, 16 núcleos lógicos), San Juan de Lurigancho, con 200 consultas × 5
repeticiones, k = 5 y 30 % de la flota ocupada:

| Conductores | Lineal | Quadtree | Examinados (lineal / QT) | Aceleración | Exactitud |
|---:|---:|---:|---:|---:|---:|
| 300 | 0,629 ms | 0,146 ms | 300 / 82 | ×4,3 | 200/200 |
| 3 000 | 6,002 ms | 0,168 ms | 3 000 / 59 | ×35,8 | 200/200 |
| 30 000 | 63,901 ms | 0,556 ms | 30 000 / 161 | ×114,9 | 200/200 |

Dijkstra propio frente a NetworkX, con 100 pares por distrito: **600/600 distancias idénticas** (diferencia máxima de 0 m).
El propio es más rápido en todos los distritos; por ejemplo, 20,9 ms frente a 39,5 ms en SJL, que tiene 14 336 nodos.

Gráficos: `01_tiempo_lineal_vs_quadtree.png`, `02_escalabilidad.png`, `03_variabilidad_tiempos.png`,
`04_dijkstra_vs_networkx.png` y `05_metricas_complementarias.png`. También se ven en la página **Benchmarks** de la app.

**Rendimiento de la simulación** (turno completo con movimiento y actualización del Quadtree en SJL): ~60 ms con
3 000 conductores y ~475 ms con 30 000. El bucle se adapta solo: espera `max(0, intervalo − duración del turno)`.

## Mapas HTML (Folium)

```bash
python -m mapas.generar_mapas
```

Genera `mapas/mapa_1_miraflores.html`, `mapa_2_san-isidro.html` y `mapa_3_santiago-de-surco.html` a partir de
**asignaciones reales** del `Despachador`, guardadas en SQLite con el origen `script`. Cada mapa muestra al pasajero, los
conductores disponibles y ocupados, los 5 candidatos, el conductor seleccionado, la ruta de recogida y la ruta del viaje.
Cualquier asignación del historial puede abrirse como mapa Folium con `GET /api/asignaciones/{id}/mapa`.

## Informe técnico

```bash
python -m informe.generar_informe      # → informe.pdf (4 páginas, con datos de benchmark/resultados/)
```

## Despliegue en Render

El archivo `render.yaml` es un Blueprint con:

1. **`conductor-cercano`**, un *Web Service* Docker que sirve la API, el WebSocket y el frontend compilado.
   - *Health check*: `/api/salud`.
   - **Disco persistente** de 2 GB montado en `/app/datos`, para los grafos y SQLite.
   - Requiere el plan **Starter o superior**. Los discos no existen en el plan gratuito.
2. **`conductor-cercano-web`** *(opcional)*, el frontend como *Static Site* con `VITE_API_URL` apuntando al backend y una
   regla de reescritura para la SPA. En ese caso, agregue su URL a `CC_ORIGENES_CORS`.

Pasos: suba el repositorio a GitHub → Render → **New → Blueprint** → elija el repositorio → **Apply**.

Consideraciones:
- **Almacenamiento**: en el plan gratuito el sistema de archivos es **efímero**. Los grafos se volverían a descargar en cada
  despliegue o reinicio y el historial de SQLite se perdería. Para producción use un disco persistente o
  `CC_URL_BASE_DATOS` con PostgreSQL.
- **Memoria**: Miraflores con 1 500 conductores usa unos 280 MB medidos en el contenedor, porque las librerías geoespaciales pesan. Para
  30 000 conductores o distritos grandes se recomiendan 2 GB (plan *Standard*).
- **CPU**: el motor corre en un solo proceso. Ejecute **una sola instancia** (sin autoescalado), porque el estado de la
  simulación vive en memoria.
- **WebSockets**: Render los admite de forma nativa en los Web Services. El cliente se reconecta solo tras los reinicios.
- **Inactividad**: los servicios gratuitos se suspenden y el primer acceso tarda en despertar.

## API y WebSocket

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/salud` | *Health check*. |
| GET | `/api/distritos` · `/api/distritos/{id}` · `/api/distritos/limites` | Catálogo, límite y estado. |
| POST | `/api/distritos/{id}/descargar?forzar=` | Descarga en segundo plano (202). |
| GET | `/api/distritos/{id}/estado` · `/red-vial` | Progreso · calles, sentidos e intersecciones del grafo. |
| GET/POST/PATCH | `/api/simulacion` · `/configurar` · `/parametros` | Estado · regenerar flota · parámetros en caliente. |
| POST | `/api/simulacion/{iniciar,pausar,reanudar,detener,avanzar,reiniciar,acelerar,desacelerar,modo}` | Control. |
| GET | `/api/estadisticas` · `/api/metricas` · `/api/simulacion/resultados` · `/configuraciones` | Indicadores y persistencia. |
| GET | `/api/conductores?limites=&estado=` · `/api/conductores/{id}` · `/api/servicios/activos` | Flota y servicios. |
| POST | `/api/solicitudes/cotizar` | Vista previa **sin asignar**: disponibles, candidatos con ETA real y ruta de recogida, recomendado y estimación del viaje. |
| POST | `/api/solicitudes` | Solicitar servicio. Admite `id_conductor` opcional (el elegido por el pasajero); devuelve candidatos, rutas, ETA y justificación. |
| GET | `/api/seguimiento/{id_pasajero}` | Viaje en vivo: fase (`recogida`, `viaje`, `finalizado`, `cancelado`), posición y rumbo del conductor, ruta y distancia restantes, ETA restante, espera real y duración. |
| GET | `/api/asignaciones` · `/{id}` · `/{id}/mapa` · `/api/solicitudes/rechazadas` | Historial. |
| GET | `/api/geocodificar?q=` · `/api/geocodificar/inversa` | Nominatim (vía backend, con límite y caché). |
| GET | `/api/benchmarks` · `/api/benchmarks/graficos/{png}` | Resultados reales. |

**WebSocket `/ws/tiempo-real`**
- El cliente envía `{"tipo":"vista","limites":[o,s,e,n],"zoom":z}`, además de `sincronizar` y `ping`.
- El servidor envía `bienvenida`, `posiciones` (`actualizados: [[id, lat, lon, rumbo, estado]]`, `eliminados: [id]`),
  `estadisticas`, `asignacion`, `solicitud_rechazada`, `recogida`, `finalizacion` y `simulacion`.

## Decisiones de diseño y limitaciones

- **k-NN exacto**: el rectángulo de búsqueda contiene exactamente el círculo de radio *r* (Δλ = asin(sin δ / cos φ)). Así,
  todo lo no explorado está a más de *r*, y se termina cuando hay *k* candidatos a distancia ≤ *r*. Se verificó contra fuerza
  bruta en 600 de 600 consultas.
- **ETA de recogida** = (resto de la arista actual + Dijkstra desde el siguiente nodo) / velocidad del conductor. La media
  configurable es de 30 km/h con ±15 % por conductor; con `variacion_velocidad = 0` la velocidad es homogénea.
- **Ubicación en el grafo**: los puntos se ajustan al nodo **circulable** (componente fuertemente conexa) más cercano, hasta
  400 m. Fuera de ese rango se informa que no existe una ruta válida.
- **Callejones sin salida**: el giro en U solo se permite cuando es la única salida real.
- **Cobertura**: 4 distritos (Ancón, Carabayllo, Pucusana y Santa María del Mar) quedan fuera de la caja del extracto BBBike.
  Para incluirlos, use Overpass o `CC_URL_EXTRACTO_OSM` con el extracto de Geofabrik Perú. Barranco, Lince y otros distritos
  pequeños miden menos de 3 km² según sus polígonos de OSM y no son elegibles.
- **Geocodificación**: Nominatim (OSM) desde el backend, con un máximo de 1 solicitud/s, `User-Agent` propio y caché. Si no
  está disponible, se puede elegir el punto en el mapa o introducir coordenadas.
- **Visualización a gran escala**: el servidor envía como máximo `CC_MAXIMO_CONDUCTORES_POR_MENSAJE` vehículos por vista,
  con un submuestreo estable por identificador. El backend mantiene siempre el estado completo de toda la flota.

---
Datos © colaboradores de OpenStreetMap (ODbL). Teselas: OpenFreeMap / OpenMapTiles.

// Capa personalizada de MapLibre que dibuja con Three.js:
// - vehículos 3D (InstancedMesh: una sola llamada de dibujo para miles de autos),
//   orientados según el rumbo y coloreados por estado;
// - marcadores elevados de pasajeros y destinos.
// Coordenadas locales en metros (x = este, y = norte, z = altura) respecto a un origen.
import maplibregl, { type CustomLayerInterface } from "maplibre-gl";
import * as THREE from "three";
import { flotaVisual } from "@/stores/flotaVisual";
import { COLORES_ESTADO } from "./estiloBase";

const CAPACIDAD_VEHICULOS = 8000;
const CAPACIDAD_MARCADORES = 600;

export interface MarcadorElevado {
  lon: number;
  lat: number;
  color: string;
}

export class CapaVehiculos3D implements CustomLayerInterface {
  id = "vehiculos-3d";
  type = "custom" as const;
  renderingMode = "3d" as const;

  visible = true;
  filtroEstados: Record<string, boolean> = { DISPONIBLE: true, OCUPADO: true, EN_SERVICIO: true, INACTIVO: false };
  seleccionado: number | null = null;

  private map!: maplibregl.Map;
  private renderer!: THREE.WebGLRenderer;
  private escena = new THREE.Scene();
  private camara = new THREE.Camera();
  private origen = maplibregl.MercatorCoordinate.fromLngLat([-77.03, -12.12], 0);
  private escalaMercator = 1;
  private carrocerias!: THREE.InstancedMesh;
  private cabinas!: THREE.InstancedMesh;
  private pines!: THREE.InstancedMesh;
  private anillos!: THREE.InstancedMesh;
  private marcadores: MarcadorElevado[] = [];
  private matriz = new THREE.Matrix4();
  private posicion = new THREE.Vector3();
  private rotacion = new THREE.Quaternion();
  private escala = new THREE.Vector3();
  private ejeZ = new THREE.Vector3(0, 0, 1);
  private colores: Record<string, THREE.Color> = Object.fromEntries(
    Object.entries(COLORES_ESTADO).map(([k, v]) => [k, new THREE.Color(v)]),
  );
  private colorSeleccion = new THREE.Color("#22d3ee");

  fijarOrigen(lon: number, lat: number) {
    this.origen = maplibregl.MercatorCoordinate.fromLngLat([lon, lat], 0);
    this.escalaMercator = this.origen.meterInMercatorCoordinateUnits();
  }

  fijarMarcadores(marcadores: MarcadorElevado[]) {
    this.marcadores = marcadores.slice(0, CAPACIDAD_MARCADORES);
  }

  onAdd(map: maplibregl.Map, gl: WebGLRenderingContext | WebGL2RenderingContext) {
    this.map = map;
    this.escalaMercator = this.origen.meterInMercatorCoordinateUnits();
    this.renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl as WebGL2RenderingContext, antialias: true });
    this.renderer.autoClear = false;

    this.escena.add(new THREE.HemisphereLight(0xdbeafe, 0x0f172a, 1.6));
    const sol = new THREE.DirectionalLight(0xffffff, 1.4);
    sol.position.set(-0.5, -0.7, 1).normalize();
    this.escena.add(sol);

    // Auto estilizado (largo sobre el eje +y = "hacia adelante"): carrocería + cabina.
    const carroceria = new THREE.BoxGeometry(1.9, 4.5, 1.0);
    carroceria.translate(0, 0, 0.6);
    const cabina = new THREE.BoxGeometry(1.6, 2.2, 0.7);
    cabina.translate(0, -0.3, 1.45);
    this.carrocerias = new THREE.InstancedMesh(carroceria, new THREE.MeshStandardMaterial({ roughness: 0.45, metalness: 0.35 }), CAPACIDAD_VEHICULOS);
    this.cabinas = new THREE.InstancedMesh(cabina, new THREE.MeshStandardMaterial({ color: 0x0b1220, roughness: 0.15, metalness: 0.8 }), CAPACIDAD_VEHICULOS);
    for (const malla of [this.carrocerias, this.cabinas]) {
      malla.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      malla.frustumCulled = false;
      this.escena.add(malla);
    }
    this.carrocerias.setColorAt(0, this.colores.DISPONIBLE);

    // Marcador elevado: pin (cono invertido + esfera) y anillo en el suelo.
    const pin = new THREE.ConeGeometry(2.2, 9, 20);
    pin.rotateX(-Math.PI / 2);
    pin.translate(0, 0, 4.5);
    const cabeza = new THREE.SphereGeometry(3.2, 20, 16);
    cabeza.translate(0, 0, 11);
    this.pines = new THREE.InstancedMesh(mezclar(pin, cabeza), new THREE.MeshStandardMaterial({ roughness: 0.3, emissive: 0x111111 }), CAPACIDAD_MARCADORES);
    const anillo = new THREE.RingGeometry(3.5, 5, 32);
    this.anillos = new THREE.InstancedMesh(anillo, new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.55, side: THREE.DoubleSide }), CAPACIDAD_MARCADORES);
    for (const malla of [this.pines, this.anillos]) {
      malla.frustumCulled = false;
      this.escena.add(malla);
    }
    this.pines.setColorAt(0, new THREE.Color("#ffffff"));
    this.anillos.setColorAt(0, new THREE.Color("#ffffff"));
  }

  private metrosLocales(lon: number, lat: number): [number, number] {
    const m = maplibregl.MercatorCoordinate.fromLngLat([lon, lat], 0);
    return [(m.x - this.origen.x) / this.escalaMercator, -(m.y - this.origen.y) / this.escalaMercator];
  }

  private factorExageracion(): number {
    // A bajo zoom un auto real (4.5 m) mide menos de un píxel: se escala para que mida ~9 px.
    const zoom = this.map.getZoom();
    const latitud = this.map.getCenter().lat;
    const metrosPorPixel = (156543.03392 * Math.cos((latitud * Math.PI) / 180)) / Math.pow(2, zoom);
    return Math.max(1, (metrosPorPixel * 9) / 4.5);
  }

  private actualizarInstancias() {
    const ahora = performance.now();
    const exageracion = this.factorExageracion();
    let i = 0;
    if (this.visible) {
      for (const v of flotaVisual.vehiculos.values()) {
        if (!this.filtroEstados[v.estado]) continue;
        if (i >= CAPACIDAD_VEHICULOS) break;
        const [lat, lon, rumbo] = flotaVisual.interpolar(v, ahora);
        const [x, y] = this.metrosLocales(lon, lat);
        const factor = v.id === this.seleccionado ? exageracion * 1.6 : exageracion;
        this.posicion.set(x, y, 0);
        this.rotacion.setFromAxisAngle(this.ejeZ, (-rumbo * Math.PI) / 180);
        this.escala.set(factor, factor, factor);
        this.matriz.compose(this.posicion, this.rotacion, this.escala);
        this.carrocerias.setMatrixAt(i, this.matriz);
        this.cabinas.setMatrixAt(i, this.matriz);
        this.carrocerias.setColorAt(i, v.id === this.seleccionado ? this.colorSeleccion : this.colores[v.estado]);
        i++;
      }
    }
    this.carrocerias.count = this.cabinas.count = i;
    this.carrocerias.instanceMatrix.needsUpdate = this.cabinas.instanceMatrix.needsUpdate = true;
    if (this.carrocerias.instanceColor) this.carrocerias.instanceColor.needsUpdate = true;

    const escalaPin = Math.max(1, exageracion / 3.5);
    let j = 0;
    const color = new THREE.Color();
    for (const m of this.marcadores) {
      const [x, y] = this.metrosLocales(m.lon, m.lat);
      color.set(m.color);
      this.posicion.set(x, y, 0);
      this.rotacion.identity();
      this.escala.set(escalaPin, escalaPin, escalaPin);
      this.matriz.compose(this.posicion, this.rotacion, this.escala);
      this.pines.setMatrixAt(j, this.matriz);
      this.anillos.setMatrixAt(j, this.matriz);
      this.pines.setColorAt(j, color);
      this.anillos.setColorAt(j, color);
      j++;
    }
    this.pines.count = this.anillos.count = j;
    this.pines.instanceMatrix.needsUpdate = this.anillos.instanceMatrix.needsUpdate = true;
    if (this.pines.instanceColor) this.pines.instanceColor.needsUpdate = true;
    if (this.anillos.instanceColor) this.anillos.instanceColor.needsUpdate = true;
  }

  render(_gl: WebGLRenderingContext | WebGL2RenderingContext, matriz: any) {
    this.actualizarInstancias();
    const transformacion = new THREE.Matrix4()
      .makeTranslation(this.origen.x, this.origen.y, this.origen.z ?? 0)
      .scale(new THREE.Vector3(this.escalaMercator, -this.escalaMercator, this.escalaMercator));
    this.camara.projectionMatrix = new THREE.Matrix4().fromArray(matriz as number[]).multiply(transformacion);
    this.renderer.resetState();
    this.renderer.render(this.escena, this.camara);
    this.map.triggerRepaint();
  }
}

function mezclar(a: THREE.BufferGeometry, b: THREE.BufferGeometry): THREE.BufferGeometry {
  // Fusión mínima de dos geometrías no indexadas (evita importar BufferGeometryUtils).
  const ga = a.toNonIndexed();
  const gb = b.toNonIndexed();
  const resultado = new THREE.BufferGeometry();
  for (const atributo of ["position", "normal"]) {
    const x = ga.getAttribute(atributo).array as Float32Array;
    const y = gb.getAttribute(atributo).array as Float32Array;
    const z = new Float32Array(x.length + y.length);
    z.set(x);
    z.set(y, x.length);
    resultado.setAttribute(atributo, new THREE.BufferAttribute(z, 3));
  }
  return resultado;
}

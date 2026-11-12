"""Flota de conductores: generación reproducible y mantenimiento del índice espacial."""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

from estructuras.grafo_vial import GrafoVial
from estructuras.quadtree import Quadtree
from simulacion.conductor import Conductor, EstadoConductor, Vehiculo

NOMBRES = ["Luis", "Carlos", "José", "María", "Rosa", "Jorge", "Ana", "Miguel", "Lucía", "Pedro",
           "Carmen", "Juan", "Elena", "Víctor", "Patricia", "Raúl", "Sofía", "Diego", "Gabriela", "Martín"]
APELLIDOS = ["Quispe", "Flores", "Sánchez", "Rodríguez", "García", "Rojas", "Huamán", "Mendoza", "Torres",
             "Chávez", "Ramírez", "Vargas", "Castillo", "Espinoza", "Díaz", "Mamani", "Gutiérrez", "Paredes"]
MODELOS = [("Toyota", "Yaris"), ("Kia", "Rio"), ("Hyundai", "Accent"), ("Nissan", "Versa"), ("Chevrolet", "Sail"),
           ("Suzuki", "Swift"), ("Toyota", "Corolla"), ("Kia", "Soluto"), ("Hyundai", "Elantra"), ("Mazda", "2")]
COLORES = ["Blanco", "Plata", "Negro", "Gris", "Rojo", "Azul"]
LETRAS = "ABCDEFGHJKLMNPRSTUVWXYZ"


@dataclass(slots=True)
class ParametrosFlota:
    cantidad_conductores: int = 1000
    semilla: int = 42
    velocidad_promedio_kmh: float = 30.0
    variacion_velocidad: float = 0.15  # ±15 % alrededor de la media (0 = homogénea)
    proporcion_inactivos: float = 0.03
    capacidad_quadtree: int = 16


class Flota:
    """Contenedor de conductores sincronizado con un Quadtree propio."""

    def __init__(self, grafo: GrafoVial, parametros: ParametrosFlota) -> None:
        self.grafo = grafo
        self.parametros = parametros
        self.conductores: dict[int, Conductor] = {}
        self.indice = Quadtree(grafo.limites_ampliados, capacidad=parametros.capacidad_quadtree)

    # ------------------------------------------------------------ generación
    def generar_flota(self, generador: random.Random) -> None:
        """Ubica cada conductor en una arista válida de la componente circulable."""
        if self.parametros.cantidad_conductores < 0:
            raise ValueError("La cantidad de conductores no puede ser negativa")
        nodos = self.grafo.lista_nodos_circulables
        if not nodos:
            raise ValueError("El grafo no tiene nodos circulables")
        self.conductores.clear()
        self.indice = Quadtree(self.grafo.limites_ampliados, capacidad=self.parametros.capacidad_quadtree)
        p = self.parametros
        for id_conductor in range(1, p.cantidad_conductores + 1):
            nodo = nodos[generador.randrange(len(nodos))]
            salidas = [v for v, _ in self.grafo.obtener_sucesores(nodo) if v in self.grafo.nodos_circulables]
            siguiente = salidas[generador.randrange(len(salidas))]
            longitud = self.grafo.obtener_geometria(nodo, siguiente).longitud
            marca, modelo = MODELOS[generador.randrange(len(MODELOS))]
            vehiculo = Vehiculo(
                placa=f"{''.join(generador.choice(LETRAS) for _ in range(3))}-{generador.randrange(100, 1000)}",
                marca=marca,
                modelo=modelo,
                color=generador.choice(COLORES),
                anio=generador.randrange(2014, 2026),
            )
            factor = 1.0 + generador.uniform(-p.variacion_velocidad, p.variacion_velocidad)
            conductor = Conductor(
                id_conductor=id_conductor,
                nombre=f"{generador.choice(NOMBRES)} {generador.choice(APELLIDOS)}",
                vehiculo=vehiculo,
                velocidad=max(5.0, p.velocidad_promedio_kmh * factor),
                nodo_actual=nodo,
                ruta_actual=[nodo, siguiente],
                distancia_en_arista=generador.uniform(0.0, longitud),
            )
            if generador.random() < p.proporcion_inactivos:
                conductor.estado = EstadoConductor.INACTIVO
            conductor.sincronizar_posicion(self.grafo)
            self.conductores[id_conductor] = conductor
            self.indice.insertar_conductor(conductor)

    # ------------------------------------------------------------ acceso
    def __len__(self) -> int:
        return len(self.conductores)

    def __iter__(self) -> Iterator[Conductor]:
        return iter(self.conductores.values())

    def obtener_conductor(self, id_conductor: int) -> Optional[Conductor]:
        return self.conductores.get(id_conductor)

    def actualizar_indice(self, conductor: Conductor) -> None:
        self.indice.actualizar_posicion(conductor.id_conductor, conductor.latitud, conductor.longitud)

    def contar_por_estado(self) -> dict[str, int]:
        conteo = Counter(c.estado.value for c in self.conductores.values())
        return {estado.value: conteo.get(estado.value, 0) for estado in EstadoConductor}

    def conductores_en_area(self, rectangulo, maximo: Optional[int] = None) -> list[Conductor]:
        entradas = self.indice.buscar_en_rectangulo(rectangulo)
        conductores = [e.objeto for e in entradas]
        conductores.sort(key=lambda c: c.id_conductor)
        return conductores if maximo is None else conductores[:maximo]

    def iterar_activos(self) -> Iterable[Conductor]:
        return (c for c in self.conductores.values() if c.estado is not EstadoConductor.INACTIVO)

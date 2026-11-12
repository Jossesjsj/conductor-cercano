"""Comunicación en tiempo real por WebSocket con actualizaciones incrementales.

Cada cliente informa su vista del mapa (rectángulo + zoom). En cada turno el servidor:
1. Consulta el Quadtree de la flota con ese rectángulo (no recorre toda la flota).
2. Compara con lo último que envió a ESE cliente (posición cuantizada a ~1 m y estado).
3. Envía solo los conductores que cambiaron y la lista de los que salieron de la vista.
Si un cliente es lento, los turnos intermedios se fusionan (el delta siempre se calcula
contra lo realmente enviado, por lo que nunca se pierde consistencia).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from fastapi import WebSocket

from estructuras.utilidades_geograficas import LimitesGeograficos
from simulacion.conductor import CODIGO_ESTADO

logger = logging.getLogger(__name__)

CUANTIZACION = 1e5  # 1e-5 grados ≈ 1.1 m


@dataclass
class ClienteTiempoReal:
    websocket: WebSocket
    identificador: int
    vista: Optional[LimitesGeograficos] = None
    zoom: float = 14.0
    intervalo_minimo_s: float = 0.2
    enviados: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    eventos: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=500))
    hay_posiciones: asyncio.Event = field(default_factory=asyncio.Event)
    ultimo_envio: float = 0.0
    activo: bool = True
    forzar_completo: bool = False


class GestorTiempoReal:
    def __init__(self, maximo_por_mensaje: int = 6000) -> None:
        self.clientes: dict[int, ClienteTiempoReal] = {}
        self.maximo_por_mensaje = maximo_por_mensaje
        self._secuencia = 0
        self.proveedor_delta: Optional[Callable[[ClienteTiempoReal], Optional[dict[str, Any]]]] = None
        self.mensajes_enviados = 0
        self.bytes_enviados = 0

    # ------------------------------------------------------------ conexión
    async def conectar(self, websocket: WebSocket) -> ClienteTiempoReal:
        await websocket.accept()
        self._secuencia += 1
        cliente = ClienteTiempoReal(websocket, self._secuencia)
        self.clientes[cliente.identificador] = cliente
        return cliente

    def desconectar(self, cliente: ClienteTiempoReal) -> None:
        cliente.activo = False
        cliente.hay_posiciones.set()
        self.clientes.pop(cliente.identificador, None)

    def actualizar_vista(self, cliente: ClienteTiempoReal, mensaje: dict[str, Any]) -> None:
        limites = mensaje.get("limites")
        if isinstance(limites, list) and len(limites) == 4:
            oeste, sur, este, norte = (float(v) for v in limites)
            if oeste <= este and sur <= norte:
                cliente.vista = LimitesGeograficos(sur, oeste, norte, este)
        cliente.zoom = float(mensaje.get("zoom", cliente.zoom))
        if "intervalo_minimo_ms" in mensaje:
            cliente.intervalo_minimo_s = min(5.0, max(0.05, float(mensaje["intervalo_minimo_ms"]) / 1000))
        cliente.hay_posiciones.set()

    # ------------------------------------------------------------ difusión
    def difundir_evento(self, mensaje: dict[str, Any]) -> None:
        """Eventos discretos (asignación, recogida, estadísticas...). No se descartan
        salvo que la cola de un cliente esté saturada (cliente bloqueado)."""
        texto = json.dumps(mensaje, ensure_ascii=False, separators=(",", ":"))
        for cliente in list(self.clientes.values()):
            try:
                cliente.eventos.put_nowait(texto)
            except asyncio.QueueFull:
                logger.warning("Cliente %s saturado: se descarta un evento", cliente.identificador)

    def notificar_turno(self) -> None:
        for cliente in self.clientes.values():
            cliente.hay_posiciones.set()

    def reiniciar_clientes(self) -> None:
        """Tras reconfigurar la flota se fuerza un envío completo."""
        for cliente in self.clientes.values():
            cliente.forzar_completo = True
            cliente.hay_posiciones.set()

    # ------------------------------------------------------------ delta
    @staticmethod
    def calcular_delta(cliente: ClienteTiempoReal, conductores: list[Any], total_en_vista: int, turno: int,
                       maximo: int) -> Optional[dict[str, Any]]:
        """Compara los conductores visibles con lo último enviado al cliente."""
        if cliente.forzar_completo:
            cliente.enviados.clear()
            cliente.forzar_completo = False
        if total_en_vista > maximo:
            # Reducción visual determinista: siempre los mismos ids (sin parpadeo).
            paso = -(-total_en_vista // maximo)
            conductores = [c for c in conductores if c.id_conductor % paso == 0]
        actualizados: list[list[Any]] = []
        visibles: set[int] = set()
        enviados = cliente.enviados
        for c in conductores:
            visibles.add(c.id_conductor)
            clave = (round(c.latitud * CUANTIZACION), round(c.longitud * CUANTIZACION), CODIGO_ESTADO[c.estado])
            if enviados.get(c.id_conductor) != clave:
                enviados[c.id_conductor] = clave
                actualizados.append([c.id_conductor, round(c.latitud, 6), round(c.longitud, 6), round(c.rumbo), clave[2]])
        eliminados = [i for i in enviados if i not in visibles]
        for i in eliminados:
            del enviados[i]
        if not actualizados and not eliminados:
            return None
        return {"tipo": "posiciones", "turno": turno, "actualizados": actualizados, "eliminados": eliminados,
                "total_en_vista": total_en_vista, "mostrados": len(visibles)}

    # ------------------------------------------------------------ bucles por cliente
    async def bucle_envio(self, cliente: ClienteTiempoReal) -> None:
        ws = cliente.websocket
        while cliente.activo:
            tarea_evento = asyncio.ensure_future(cliente.eventos.get())
            tarea_posiciones = asyncio.ensure_future(cliente.hay_posiciones.wait())
            hechas, pendientes = await asyncio.wait({tarea_evento, tarea_posiciones}, return_when=asyncio.FIRST_COMPLETED)
            for p in pendientes:
                p.cancel()
            if not cliente.activo:
                break
            if tarea_evento in hechas:
                await self._enviar_texto(ws, tarea_evento.result())
                while not cliente.eventos.empty():
                    await self._enviar_texto(ws, cliente.eventos.get_nowait())
            if cliente.hay_posiciones.is_set():
                espera = cliente.intervalo_minimo_s - (time.monotonic() - cliente.ultimo_envio)
                if espera > 0:
                    await asyncio.sleep(espera)  # control de frecuencia por cliente
                cliente.hay_posiciones.clear()
                if self.proveedor_delta is not None and cliente.vista is not None:
                    delta = await asyncio.to_thread(self.proveedor_delta, cliente)
                    if delta is not None:
                        await self._enviar_texto(ws, json.dumps(delta, separators=(",", ":")))
                cliente.ultimo_envio = time.monotonic()

    async def _enviar_texto(self, ws: WebSocket, texto: str) -> None:
        await ws.send_text(texto)
        self.mensajes_enviados += 1
        self.bytes_enviados += len(texto)

"""Endpoint WebSocket /ws/tiempo-real."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/tiempo-real")
async def tiempo_real(websocket: WebSocket) -> None:
    contenedor = websocket.app.state.contenedor
    gestor = contenedor.tiempo_real
    cliente = await gestor.conectar(websocket)
    await websocket.send_text(json.dumps({
        "tipo": "bienvenida",
        "id_cliente": cliente.identificador,
        "simulacion": contenedor.simulacion.estado_simulacion(),
    }, ensure_ascii=False))
    tarea_envio = asyncio.create_task(gestor.bucle_envio(cliente))
    try:
        while True:
            mensaje = json.loads(await websocket.receive_text())
            tipo = mensaje.get("tipo")
            if tipo == "vista":
                gestor.actualizar_vista(cliente, mensaje)
            elif tipo == "sincronizar":
                cliente.forzar_completo = True
                cliente.hay_posiciones.set()
            elif tipo == "ping":
                await cliente.eventos.put(json.dumps({"tipo": "pong", "t": mensaje.get("t")}))
    except (WebSocketDisconnect, RuntimeError):
        pass
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        logger.info("Mensaje WebSocket inválido: %s", error)
    finally:
        gestor.desconectar(cliente)
        tarea_envio.cancel()

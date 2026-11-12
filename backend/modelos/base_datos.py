"""Motor y sesiones SQLAlchemy."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.modelos.tablas import Base


def crear_motor(url: str) -> Engine:
    argumentos = {"check_same_thread": False} if url.startswith("sqlite") else {}
    motor = create_engine(url, connect_args=argumentos, pool_pre_ping=True)
    if url.startswith("sqlite"):
        @event.listens_for(motor, "connect")
        def _pragmas(conexion, _registro) -> None:  # pragma: no cover - configuración
            cursor = conexion.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    Base.metadata.create_all(motor)
    return motor


class BaseDatos:
    def __init__(self, url: str) -> None:
        self.motor = crear_motor(url)
        self._fabrica = sessionmaker(self.motor, expire_on_commit=False)

    @contextmanager
    def sesion(self) -> Iterator[Session]:
        sesion = self._fabrica()
        try:
            yield sesion
            sesion.commit()
        except Exception:
            sesion.rollback()
            raise
        finally:
            sesion.close()

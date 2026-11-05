"""Esqueleto en rojo."""

from a2a.types.a2a_pb2 import Task


async def crear_esquema(dsn: str) -> None:
    return None


async def leer_task(dsn: str, task_id: str, identidad: str) -> Task | None:
    raise NotImplementedError

"""Esqueleto en rojo."""

from dataclasses import dataclass
from uuid import uuid4

from a2a.types.a2a_pb2 import Message, Task

from orquestador.peticiones import Origen


@dataclass(frozen=True)
class Entorno:
    dsn: str
    instancia: str
    origenes: frozenset[Origen]


@dataclass(frozen=True)
class Recepcion:
    task: Task
    sesiones: list[str]


async def recibir_peticion(
    entorno: Entorno, mensaje: Message, extensiones: set[str], identidad: str
) -> Recepcion:
    raise NotImplementedError(uuid4)


async def comprobar_sesion(entorno: Entorno, session_id: str) -> None:
    raise NotImplementedError

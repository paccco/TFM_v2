"""Acceso a PostgreSQL y conversión de las Tasks guardadas (D-69, D-97, D-127)."""

from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from a2a.types.a2a_pb2 import Task
from google.protobuf.json_format import MessageToDict, ParseDict
from psycopg.types.json import Jsonb


async def conectar(dsn: str) -> psycopg.AsyncConnection[Any]:
    """Una conexión por transacción: `async with` confirma al salir y deshace si hay excepción.

    shortcut: abre una conexión por transacción; usar un pool si la carga lo pide.
    """
    return await psycopg.AsyncConnection.connect(dsn)


async def crear_esquema(dsn: str) -> None:
    """Crea las tablas si no existen."""
    sql = Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8")
    async with await conectar(dsn) as c:
        await c.execute(sql)  # type: ignore[arg-type]


def task_a_json(task: Task) -> Jsonb:
    """Forma JSON de A2A con la que se guarda la Task, tal como se respondió."""
    return Jsonb(MessageToDict(task))


def task_de_json(datos: dict[str, Any]) -> Task:
    return ParseDict(datos, Task())


async def leer_task(dsn: str, task_id: str, identidad: str) -> Task | None:
    """`GetTask` (D-97): solo la identidad que la creó la ve; para otra no existe (D-128)."""
    try:
        UUID(task_id)
    except ValueError:
        return None
    async with await conectar(dsn) as c:
        cursor = await c.execute(
            "SELECT datos FROM tareas WHERE task_id = %s AND identidad = %s",
            (task_id, identidad),
        )
        fila = await cursor.fetchone()
    return task_de_json(fila[0]) if fila else None

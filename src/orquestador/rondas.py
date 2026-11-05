"""Aceptar `OPEN_ROUND` y arrancar la ronda: pasos 2 a 10 de CU-04.

Todo el estado vive en PostgreSQL (D-04): `recibir_peticion` escribe la aceptación o el rechazo
en una transacción (D-63, D-97) y `comprobar_sesion` saca cada sesión de `CREATED` (D-99).
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
import psycopg
from a2a.client.card_resolver import parse_agent_card
from a2a.types.a2a_pb2 import Artifact, Message, Part, Role, Task, TaskState, TaskStatus
from a2a.utils.constants import TransportProtocol
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value
from psycopg.types.json import Jsonb

from orquestador.almacen import conectar, task_a_json, task_de_json
from orquestador.peticiones import (
    MEDIA_RESULTADO,
    OPEN_ROUND,
    URI_EXTENSION,
    Origen,
    PeticionValidada,
    origen,
    validar_peticion,
)

ORCHESTRATOR = "ORCHESTRATOR"
# D-65: duración del arrendamiento. `bigint` porque `turnTimeoutSeconds` no tiene máximo.
FIN_ARRENDAMIENTO = """clock_timestamp() + make_interval(secs =>
    (config->>'turnTimeoutSeconds')::bigint + (config->>'pollIntervalSeconds')::bigint)"""
# D-98, D-128: duplicado de `sender` + `messageId`; nunca es una colisión de identificadores.
INDICE_DUPLICADOS = "registro_peticiones_unica"


@dataclass(frozen=True)
class Entorno:
    """Lo que una instancia necesita saber: base de datos, su nombre y los orígenes (D-129)."""

    dsn: str
    instancia: str
    origenes: frozenset[Origen]


@dataclass(frozen=True)
class Recepcion:
    """La Task con la que se responde y las sesiones que quedan por comprobar."""

    task: Task
    sesiones: list[str]


class _PeticionCambiada(Exception):
    """Otra transacción escribió antes el registro de petición (D-63)."""


async def recibir_peticion(
    entorno: Entorno, mensaje: Message, extensiones: set[str], identidad: str
) -> Recepcion:
    """Valida y escribe el rechazo o la aceptación (CU-04, pasos 3 a 6, flujos 3a a 5a)."""
    validada = validar_peticion(mensaje, extensiones, identidad, entorno.origenes)
    if validada.fallos:
        task = await _rechazar(entorno, mensaje, validada, identidad)
        return Recepcion(task, [])
    while True:
        try:
            return await _aceptar(entorno, mensaje, validada, identidad)
        except psycopg.errors.UniqueViolation as error:
            if error.diag.constraint_name == INDICE_DUPLICADOS:
                # shortcut: duplicado como error A2A, feature/rechazos-peticiones devuelve su Task (D-98).
                raise
            # Flujo 6c, D-67: un identificador generado ya existe; se genera otro.


async def _rechazar(
    entorno: Entorno, mensaje: Message, validada: PeticionValidada, identidad: str
) -> Task:
    """Flujos 1a y 3a a 5a: Task en `TASK_STATE_REJECTED` y entrada, sin más cambios (D-89, D-97)."""
    task_id = str(uuid4())
    codigos = [f.code for f in validada.fallos]
    rechazos = [{"code": f.code, "field": f.field} for f in validada.fallos]
    aviso = Message(
        message_id=str(uuid4()),
        role=Role.ROLE_AGENT,
        extensions=[URI_EXTENSION],
        parts=[_parte_resultado({"rejections": rechazos})],
    )
    # D-106: sin un `type` de petición válido no hay valor que poner en el sobre.
    if validada.tipo is not None:
        ParseDict({URI_EXTENSION: _sobre(validada.tipo)}, aviso.metadata)
    task = Task(
        id=task_id,
        context_id=str(uuid4()),
        status=TaskStatus(state=TaskState.TASK_STATE_REJECTED, message=aviso),
    )
    async with await conectar(entorno.dsn) as c:
        await _insertar_task(c, task, identidad)
        await _anotar_entrada(
            c,
            validada,
            identidad,
            mensaje.message_id,
            task_id,
            "RECHAZADA",
            codigos,
        )
    return task


async def _aceptar(
    entorno: Entorno, mensaje: Message, validada: PeticionValidada, identidad: str
) -> Recepcion:
    """Paso 6: petición, sesiones, Task y entrada en una sola transacción (AC-04-03)."""
    request_id = str(uuid4())
    task_id = str(uuid4())
    # Ronda 1 (D-83): `requestId` nuevo; la ronda ≥ 2 llega con feature/varias-sesiones.
    ronda = 1
    sesiones = [(str(uuid4()), s) for s in validada.sesiones]
    registro_ronda = {
        "numero": ronda,
        "sesiones": [{"itemId": s.item_id, "sessionId": i} for i, s in sesiones],
        "mantenidas": [],
        "taskId": task_id,
    }
    task = Task(
        id=task_id,
        context_id=str(uuid4()),
        status=TaskStatus(state=TaskState.TASK_STATE_WORKING),
    )
    async with await conectar(entorno.dsn) as c:
        await c.execute(
            "INSERT INTO peticiones (request_id, comprador, version, rondas)"
            " VALUES (%s, %s, 1, %s)",
            (request_id, validada.sender, Jsonb([registro_ronda])),
        )
        for session_id, sesion in sesiones:
            await c.execute(
                """
                INSERT INTO sesiones (session_id, request_id, ronda, item_id, config, version,
                                      instancia, estado)
                VALUES (%s, %s, %s, %s, %s, 1, %s, 'CREATED')
                """,
                (
                    session_id,
                    request_id,
                    ronda,
                    sesion.item_id,
                    Jsonb(sesion.config),
                    entorno.instancia,
                ),
            )
            await c.execute(
                f"UPDATE sesiones SET arrendamiento_hasta = {FIN_ARRENDAMIENTO}"
                " WHERE session_id = %s",
                (session_id,),
            )
        await _insertar_task(c, task, identidad)
        await _anotar_entrada(
            c,
            validada,
            identidad,
            mensaje.message_id,
            task_id,
            "ACEPTADA",
            [],
            request_id,
            ronda,
        )
    return Recepcion(task, [i for i, _ in sesiones])


async def comprobar_sesion(entorno: Entorno, session_id: str) -> None:
    """Pasos 8 a 10: renueva el arrendamiento, comprueba las AgentCards y sale de `CREATED`."""
    async with await conectar(entorno.dsn) as c:
        cursor = await c.execute(
            f"""
            UPDATE sesiones
            SET version = version + 1, arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND estado = 'CREATED' AND instancia = %s
            RETURNING version, config
            """,
            (session_id, entorno.instancia),
        )
        fila = await cursor.fetchone()
    if fila is None:
        return  # D-63: otra instancia la ha tomado.
    version, config = fila

    plazo = config["turnTimeoutSeconds"]
    # D-99: el único tiempo máximo es el de `_agentcard_correcta`. D-129: sin redirecciones.
    async with httpx.AsyncClient(follow_redirects=False, timeout=None) as cliente:
        urls = await asyncio.gather(
            *[
                _url_de_servicio(
                    cliente, parte["agentCardUrl"], plazo, entorno.origenes
                )
                for parte in config["parties"]
            ]
        )
    # D-99: si fallan las dos, la primera según el orden de `parties`.
    fallida = next(
        (p["partyId"] for p, url in zip(config["parties"], urls) if url is None), None
    )
    servicio = {p["partyId"]: url for p, url in zip(config["parties"], urls)}
    await _salir_de_created(entorno, session_id, version, fallida, servicio)


async def _url_de_servicio(
    cliente: httpx.AsyncClient, url: str, plazo: int, origenes: frozenset[Origen]
) -> str | None:
    """URL JSON-RPC de la parte, o None si su AgentCard no es válida (D-25, D-99, D-131).

    Un intento; cualquier fallo al obtenerla o interpretarla cuenta como fallo.
    """
    try:
        async with asyncio.timeout(plazo):
            respuesta = await cliente.get(url)
            respuesta.raise_for_status()
            tarjeta = parse_agent_card(respuesta.json())
    except Exception:  # noqa: BLE001 - D-99: cualquier fallo es «no se puede obtener»
        return None
    if not any(
        e.uri == URI_EXTENSION and e.required for e in tarjeta.capabilities.extensions
    ):
        return None
    jsonrpc = [
        i.url
        for i in tarjeta.supported_interfaces
        if i.protocol_binding == TransportProtocol.JSONRPC
    ]
    # D-131: es la dirección que se llama de verdad, con el mismo límite que D-129.
    if not jsonrpc or origen(jsonrpc[0]) not in origenes:
        return None
    return jsonrpc[0]


async def _salir_de_created(
    entorno: Entorno,
    session_id: str,
    version: int,
    fallida: str | None,
    servicio: dict[str, str | None],
) -> None:
    """Transición de salida, con el registro de petición por versión (D-63, D-97).

    Dos salidas a la vez se serializan en esa fila: la perdedora repite, ya viendo la otra
    sesión fuera de `CREATED`, así que solo una completa la Task.
    """
    while True:
        try:
            async with await conectar(entorno.dsn) as c:
                await _transicion(c, session_id, version, fallida, servicio)
            return
        except _PeticionCambiada:
            continue


async def _transicion(
    c: psycopg.AsyncConnection[Any],
    session_id: str,
    version: int,
    fallida: str | None,
    servicio: dict[str, str | None],
) -> None:
    if fallida is None:
        cursor = await c.execute(
            f"""
            UPDATE sesiones
            SET estado = 'NEGOTIATING', subestado = 'READY', turn = 1, attempt = 1,
                message_id = %s, urls_servicio = %s, version = version + 1,
                arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND version = %s
            RETURNING request_id, ronda
            """,
            (str(uuid4()), Jsonb(servicio), session_id, version),
        )
    else:
        cursor = await c.execute(
            """
            UPDATE sesiones
            SET estado = 'NOT_STARTED', failed_party_id = %s, version = version + 1
            WHERE session_id = %s AND version = %s
            RETURNING request_id, ronda
            """,
            (fallida, session_id, version),
        )
    fila = await cursor.fetchone()
    if fila is None:
        return  # Flujo 9a, D-63: la versión cambió; se descarta el trabajo.
    request_id, ronda = fila

    cursor = await c.execute(
        "SELECT version, rondas FROM peticiones WHERE request_id = %s", (request_id,)
    )
    version_peticion, rondas = await cursor.fetchone()  # type: ignore[misc]
    cursor = await c.execute(
        "UPDATE peticiones SET version = version + 1 WHERE request_id = %s AND version = %s",
        (request_id, version_peticion),
    )
    if cursor.rowcount == 0:
        raise _PeticionCambiada

    cursor = await c.execute(
        "SELECT count(*) FROM sesiones"
        " WHERE request_id = %s AND ronda = %s AND estado = 'CREATED'",
        (request_id, ronda),
    )
    pendientes = await cursor.fetchone()
    if pendientes == (0,):
        task_id = next(r["taskId"] for r in rondas if r["numero"] == ronda)
        await _completar_task(c, task_id, str(request_id), ronda)


async def _completar_task(
    c: psycopg.AsyncConnection[Any], task_id: str, request_id: str, ronda: int
) -> None:
    """Paso 10: Task en `TASK_STATE_COMPLETED` con el Artifact de resultado (D-92, D-94, D-104)."""
    cursor = await c.execute(
        "SELECT item_id, session_id::text, estado, failed_party_id FROM sesiones"
        " WHERE request_id = %s AND ronda = %s ORDER BY item_id",
        (request_id, ronda),
    )
    sesiones: list[dict[str, Any]] = []
    for item_id, session_id, estado, fallida in await cursor.fetchall():
        entrada = {
            "itemId": item_id,
            "sessionId": session_id,
            "started": estado != "NOT_STARTED",
        }
        if fallida is not None:
            entrada["failedPartyId"] = fallida
        sesiones.append(entrada)

    artefacto = Artifact(
        artifact_id=str(uuid4()),
        extensions=[URI_EXTENSION],
        parts=[
            _parte_resultado(
                {"requestId": request_id, "round": ronda, "sessions": sesiones}
            )
        ],
    )
    ParseDict({URI_EXTENSION: _sobre(OPEN_ROUND)}, artefacto.metadata)

    cursor = await c.execute("SELECT datos FROM tareas WHERE task_id = %s", (task_id,))
    fila = await cursor.fetchone()
    assert fila is not None  # se creó en la transacción de aceptación (D-97)
    task = task_de_json(fila[0])
    task.status.state = TaskState.TASK_STATE_COMPLETED
    task.artifacts.append(artefacto)
    await c.execute(
        "UPDATE tareas SET datos = %s WHERE task_id = %s",
        (task_a_json(task), task_id),
    )


def _sobre(tipo: str) -> dict[str, str]:
    """D-104: sobre del resultado, sin `sessionId` ni `turn`."""
    return {"type": tipo, "sender": ORCHESTRATOR}


def _parte_resultado(datos: dict[str, Any]) -> Part:
    valor = Value()
    ParseDict(datos, valor)
    return Part(data=valor, media_type=MEDIA_RESULTADO)


async def _insertar_task(
    c: psycopg.AsyncConnection[Any], task: Task, identidad: str
) -> None:
    await c.execute(
        "INSERT INTO tareas (task_id, identidad, datos) VALUES (%s, %s, %s)",
        (task.id, identidad, task_a_json(task)),
    )


async def _anotar_entrada(
    c: psycopg.AsyncConnection[Any],
    validada: PeticionValidada,
    identidad: str,
    message_id: str,
    task_id: str,
    resultado: str,
    codigos: list[str],
    request_id: str | None = None,
    ronda: int | None = None,
) -> None:
    """Entrada del registro de peticiones (D-89, D-103, D-128)."""
    await c.execute(
        """
        INSERT INTO registro_peticiones (tipo, request_id, ronda, sender, identidad, message_id,
                                         task_id, resultado, codigos)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            validada.tipo,
            request_id,
            ronda,
            validada.sender,
            identidad,
            message_id,
            task_id,
            resultado,
            codigos,
        ),
    )

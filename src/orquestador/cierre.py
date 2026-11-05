"""Cierre de una sesión en `CLOSING`: CU-02 (D-49, D-55, D-64, D-70, D-71).

Envía `SESSION_CLOSE` a las partes pendientes a la vez, con un intento por parte y sin validar
la respuesta. Cada envío se marca en el registro de sesión y se anota en el registro de envíos
de control en una transacción; la que marca el último pendiente pasa la sesión a `CLOSED`.
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from orquestador.cliente_agentes import ErrorA2A, ErrorTransporte, llamar
from orquestador.rondas import FIN_ARRENDAMIENTO, Entorno
from orquestador.turnos import (
    PENDIENTE,
    conexion_exacta,
    envio_de_control,
    jsonb_exacto,
    texto_valido,
)

SESSION_CLOSE = "SESSION_CLOSE"
ENVIADO = "ENVIADO"
FALLIDO = "FALLIDO"
# AC-02-03: campos de `SESSION_CLOSE` según el `outcome`. El `reason` de un `WITHDRAW` no viaja.
CAMPOS = {
    "AGREEMENT": ("agreedOffer",),
    "WITHDRAWN": ("withdrawnBy", "lastOffers"),
    "NO_AGREEMENT": ("lastOffers",),
    "ABORTED": ("abortReason", "lastFailure", "lastOffers"),
    "RELEASED": ("releaseReason", "lastOffers"),
}


@dataclass
class _Envio:
    """Lo que se anota de un envío en el registro de envíos de control (D-70)."""

    resultado: str
    task_id: str | None = None
    estado_task: str | None = None
    con_message: bool = False
    code: str | None = None


@dataclass
class _Cierre:
    session_id: str
    version: int
    turn: int
    pendientes: set[str]
    descartado: bool = False


async def cerrar(entorno: Entorno, session_id: str) -> None:
    """Pasos 1 a 5 de CU-02. No hace nada si la sesión no está en `CLOSING` con el
    arrendamiento de esta instancia (D-63)."""
    async with await conexion_exacta(entorno.dsn) as c:
        # Paso 3 y AC-02-14: renueva el arrendamiento antes de lanzar los envíos.
        cursor = await c.execute(
            f"""
            UPDATE sesiones
            SET version = version + 1, arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND instancia = %s AND estado = 'CLOSING'
            RETURNING version, config, turn, resultado, urls_servicio, context_ids,
                      envios_close
            """,
            (session_id, entorno.instancia),
        )
        fila = await cursor.fetchone()
    if fila is None:
        return
    version, config, turn, resultado, urls, contextos, envios = fila
    pendientes = {p for p, estado in envios.items() if estado == PENDIENTE}
    cierre = _Cierre(session_id, version, turn, pendientes)
    cuerpo = {
        "outcome": resultado["outcome"],
        **{k: resultado[k] for k in CAMPOS[resultado["outcome"]] if k in resultado},
    }
    marcas = asyncio.Lock()  # D-63: las marcas se escriben una tras otra

    async def enviar(cliente: httpx.AsyncClient, parte: str) -> None:
        params = envio_de_control(
            session_id, turn, SESSION_CLOSE, cuerpo, str(uuid4()), contextos.get(parte)
        )
        envio = await _enviar(
            cliente, urls[parte], params, config["turnTimeoutSeconds"]
        )
        async with marcas:
            await _marcar(entorno, cierre, parte, envio)

    async with httpx.AsyncClient(follow_redirects=False, timeout=None) as cliente:
        # D-64: envíos independientes; un fallo al marcar uno no corta el otro.
        errores = await asyncio.gather(
            *[enviar(cliente, p) for p in sorted(pendientes)], return_exceptions=True
        )
    for error in errores:
        if isinstance(error, BaseException):
            raise error


async def _enviar(
    cliente: httpx.AsyncClient, url: str, params: dict[str, Any], plazo: float
) -> _Envio:
    """Un intento, sin sondeo ni `CancelTask` (D-49, D-64). La respuesta no se valida."""
    try:
        async with asyncio.timeout(plazo):
            respuesta = await llamar(cliente, url, "SendMessage", params)
    except TimeoutError:
        return _Envio(FALLIDO, code="TURN_TIMEOUT")
    except ErrorTransporte:
        return _Envio(FALLIDO, code="AGENT_UNREACHABLE")
    except ErrorA2A:
        return _Envio(FALLIDO, code="AGENT_ERROR")  # D-71
    task = respuesta.get("task") if isinstance(respuesta, dict) else None
    if isinstance(task, dict):
        status = task.get("status")
        estado = status.get("state") if isinstance(status, dict) else None
        return _Envio(
            ENVIADO,
            task.get("id") if texto_valido(task.get("id")) else None,
            estado if texto_valido(estado) else None,
        )
    if isinstance(respuesta, dict) and "message" in respuesta:
        return _Envio(ENVIADO, con_message=True)
    # shortcut: una respuesta que no es Task ni Message no está en la especificación; se
    # anota como error A2A hasta que se decida.
    return _Envio(FALLIDO, code="AGENT_ERROR")


async def _marcar(entorno: Entorno, cierre: _Cierre, parte: str, envio: _Envio) -> None:
    """Marca y entrada del registro en una transacción (AC-02-11), condicionada a versión e
    instancia (D-63). Si otra instancia escribió antes, se descarta todo (AC-02-13)."""
    if cierre.descartado:
        return
    quedan = cierre.pendientes - {parte}
    async with await conexion_exacta(entorno.dsn) as c:
        cursor = await c.execute(
            f"""
            UPDATE sesiones
            SET envios_close = envios_close || %s, version = version + 1,
                estado = CASE WHEN %s THEN 'CLOSED' ELSE estado END,
                arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND version = %s AND instancia = %s
            RETURNING clock_timestamp()
            """,
            (
                jsonb_exacto({parte: envio.resultado}),
                not quedan,  # paso 5: la que marca el último pasa a CLOSED
                cierre.session_id,
                cierre.version,
                entorno.instancia,
            ),
        )
        fila = await cursor.fetchone()
        if fila is None:
            cierre.descartado = True
            return
        await c.execute(
            """
            INSERT INTO envios_control (session_id, tipo, parte, turn, instante, resultado,
                                        task_id, estado_task, con_message, code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                cierre.session_id,
                SESSION_CLOSE,
                parte,
                cierre.turn,
                fila[0],  # D-69: el instante de la escritura de la marca
                envio.resultado,
                envio.task_id,
                envio.estado_task,
                envio.con_message,
                envio.code,
            ),
        )
    cierre.version += 1
    cierre.pendientes = quedan

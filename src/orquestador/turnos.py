"""Turnos de una sesión en `NEGOTIATING`: CU-01 y CU-03 (D-58, `maquina-estados.md` §2).

Cada punto de espera queda en PostgreSQL (D-04): `READY` antes de `SendMessage`,
`AWAITING_TASK` mientras se sondea. Cada transición es una escritura condicional por versión
y por arrendamiento (D-63); si falla, la instancia descarta su trabajo.

En v0.1.0 toda sesión es `STRICT` con `maxRetries = 0` (`roadmap.md`, H1), así que el primer
fallo de un intento agota los reintentos y la sesión pasa a `CLOSING` con `ABORTED`.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx
import psycopg
from psycopg.types.json import Jsonb, set_json_loads

from orquestador.actos import CON_OFERTA, texto_seguro, validar_acto
from orquestador.almacen import conectar
from orquestador.cliente_agentes import (
    TASK_NOT_FOUND,
    ErrorA2A,
    ErrorTransporte,
    a_json,
    leer_json,
    llamar,
)
from orquestador.peticiones import URI_EXTENSION, Fallo
from orquestador.rondas import FIN_ARRENDAMIENTO, ORCHESTRATOR, Entorno

MEDIA_CONTROL = "application/vnd.tfm.negociacion.control+json"  # D-19
EN_CURSO = ("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING")  # D-59
# D-23, D-60: estados finales que no son `TASK_STATE_COMPLETED`.
FINALES = {
    "TASK_STATE_FAILED": "TASK_FAILED",
    "TASK_STATE_REJECTED": "TASK_REJECTED",
    "TASK_STATE_CANCELED": "TASK_CANCELED",
}
PENDIENTE = "PENDIENTE"


@dataclass
class _Sesion:
    """Lo leído al tomar la sesión; `version` sigue a cada escritura propia."""

    session_id: str
    version: int
    config: dict[str, Any]
    subestado: str
    turn: int
    message_id: str
    urls: dict[str, str]
    context_ids: dict[str, str]
    task_id: str | None
    inicio: datetime
    oferta_vigente: dict[str, Any] | None

    @property
    def parte(self) -> str:
        """D-33: la que abre tiene los turnos impares."""
        abre = self.config["openingPartyId"]
        otra = next(p for p in self._ids() if p != abre)
        return abre if self.turn % 2 else otra

    def _ids(self) -> list[str]:
        return [p["partyId"] for p in self.config["parties"]]


def _jsonb(valor: Any) -> Jsonb:
    return Jsonb(valor, dumps=a_json)


async def _conexion(dsn: str) -> psycopg.AsyncConnection[Any]:
    """Conexión que lee los JSON con los decimales exactos (D-37)."""
    c = await conectar(dsn)
    set_json_loads(leer_json, context=c)
    return c


async def negociar(entorno: Entorno, session_id: str) -> None:
    """Repite turnos mientras la sesión siga en `NEGOTIATING` con el arrendamiento de esta
    instancia. Los `CancelTask` se lanzan sin esperarlos y se recogen al final (D-52, D-60)."""
    cancelaciones: list[asyncio.Task[None]] = []
    async with httpx.AsyncClient(follow_redirects=False, timeout=None) as cliente:
        try:
            while await _turno(entorno, cliente, session_id, cancelaciones):
                pass
        finally:
            await asyncio.gather(*cancelaciones, return_exceptions=True)


async def _turno(
    entorno: Entorno,
    cliente: httpx.AsyncClient,
    session_id: str,
    cancelaciones: list[asyncio.Task[None]],
) -> bool:
    """Un intento completo. Devuelve si la sesión sigue en `READY` para otro turno."""
    s = await _tomar(entorno, session_id)
    if s is None:
        return False
    url = s.urls[s.parte]
    plazo = s.config["turnTimeoutSeconds"]

    def cancelar(task_id: str) -> None:
        """D-52, D-60: `CancelTask` sin esperar resultado."""
        cancelaciones.append(
            asyncio.create_task(_cancelar(cliente, url, task_id, plazo))
        )

    task: Any = None
    if s.subestado == "READY":
        # Paso 3: el tiempo del turno cuenta desde justo antes de `SendMessage`.
        try:
            async with asyncio.timeout(plazo):
                resultado = await llamar(cliente, url, "SendMessage", _peticion(s))
        except TimeoutError:
            return await _resolver(entorno, s, None, Fallo("TURN_TIMEOUT", "task"))
        except ErrorTransporte:
            return await _resolver(entorno, s, None, Fallo("AGENT_UNREACHABLE", "task"))
        except ErrorA2A:
            return await _resolver(
                entorno, s, None, Fallo("AGENT_ERROR", "task")
            )  # D-71
        task = resultado.get("task") if isinstance(resultado, dict) else None
        if not isinstance(task, dict) or not _texto_valido(task.get("id")):
            return await _resolver(
                entorno, s, None, Fallo("MISSING_ACT", "task")
            )  # D-62
        if not await _esperar_task(entorno, s, task):
            return False
    assert s.task_id is not None

    while _estado(task) in (None, *EN_CURSO):
        await asyncio.sleep(s.config["pollIntervalSeconds"])
        restante = await _renovar(entorno, s)
        if restante is None:
            return False
        if restante <= 0:
            cancelar(s.task_id)
            return await _resolver(entorno, s, s.task_id, Fallo("TURN_TIMEOUT", "task"))
        try:
            async with asyncio.timeout(restante):
                task = await llamar(cliente, url, "GetTask", {"id": s.task_id})
        except TimeoutError:
            cancelar(s.task_id)
            return await _resolver(entorno, s, s.task_id, Fallo("TURN_TIMEOUT", "task"))
        except ErrorTransporte:
            task = None  # Flujo 5b: se sigue sondeando.
        except ErrorA2A as error:
            if error.code == TASK_NOT_FOUND:  # D-68
                return await _resolver(
                    entorno, s, s.task_id, Fallo("MISSING_ACT", "task")
                )
            # shortcut: otro error A2A en `GetTask` no está en la especificación; se trata como
            # el de transporte (5b) hasta que se decida.
            task = None
        if task is not None and not isinstance(task, dict):
            return await _resolver(entorno, s, s.task_id, Fallo("MISSING_ACT", "task"))

    estado = _estado(task)
    if estado in FINALES:
        return await _resolver(entorno, s, s.task_id, Fallo(FINALES[estado], "task"))
    if estado != "TASK_STATE_COMPLETED":
        cancelar(s.task_id)
        return await _resolver(entorno, s, s.task_id, Fallo("TASK_INTERRUPTED", "task"))
    # Pasos 6 a 9.
    acto = validar_acto(task, s.session_id, s.turn, s.parte, s.config["fixedTerms"])
    if acto.fallos:
        return await _resolver(entorno, s, s.task_id, *acto.fallos)
    assert acto.tipo is not None  # sin fallos, el acto tiene tipo
    return await _aceptar(entorno, s, acto.tipo, acto.oferta, acto.reason)


def _estado(task: Any) -> Any:
    """`status.state` de la Task, o «otro» si no lo tiene (D-60). None: aún no hay Task."""
    if task is None:
        return None
    status = task.get("status")
    estado = status.get("state") if isinstance(status, dict) else None
    return estado if isinstance(estado, str) else ""


def _texto_valido(valor: Any) -> bool:
    """Un identificador que PostgreSQL puede guardar tal cual."""
    return isinstance(valor, str) and texto_seguro(valor) == valor


def _peticion(s: _Sesion) -> dict[str, Any]:
    """`TURN_REQUEST` del intento (paso 2 de CU-01 y CU-03, D-46, D-47)."""
    config = s.config
    rol = next(p["role"] for p in config["parties"] if p["partyId"] == s.parte)
    cuerpo: dict[str, Any] = {
        "role": rol,
        "fixedTerms": config["fixedTerms"],
        "allowedActs": (
            ["PROPOSE", "WITHDRAW"]
            if s.turn == 1
            else ["COUNTEROFFER", "ACCEPT", "WITHDRAW"]
        ),
        "turnsLeft": config["maxTurns"] - s.turn + 1,
        "attempt": 1,
    }
    if s.turn > 1:
        cuerpo["lastOffer"] = s.oferta_vigente
    mensaje: dict[str, Any] = {
        "messageId": s.message_id,  # D-66
        "role": "ROLE_USER",
        "parts": [{"data": cuerpo, "mediaType": MEDIA_CONTROL}],
        "metadata": {
            URI_EXTENSION: {
                "sessionId": s.session_id,
                "turn": s.turn,
                "type": "TURN_REQUEST",
                "sender": ORCHESTRATOR,
            }
        },
        "extensions": [URI_EXTENSION],
    }
    if (
        s.parte in s.context_ids
    ):  # D-20: sin `contextId` en el primer turno de cada parte
        mensaje["contextId"] = s.context_ids[s.parte]
    return {"message": mensaje, "configuration": {"returnImmediately": True}}  # D-58


async def _tomar(entorno: Entorno, session_id: str) -> _Sesion | None:
    """Renueva el arrendamiento y toma el instante de inicio del intento (D-63, D-65)."""
    async with await _conexion(entorno.dsn) as c:
        cursor = await c.execute(
            f"""
            UPDATE sesiones
            SET version = version + 1, arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND instancia = %s AND estado = 'NEGOTIATING'
            RETURNING version, config, subestado, turn, message_id, urls_servicio,
                      context_ids, task_id, coalesce(inicio_intento, clock_timestamp()),
                      oferta_vigente
            """,
            (session_id, entorno.instancia),
        )
        fila = await cursor.fetchone()
    return None if fila is None else _Sesion(session_id, *fila)


async def _esperar_task(entorno: Entorno, s: _Sesion, task: dict[str, Any]) -> bool:
    """`READY` → `AWAITING_TASK`: `taskId`, instante de inicio y `contextId` si es nuevo."""
    contexto = task.get("contextId")
    nuevo = (
        {s.parte: contexto}
        if s.parte not in s.context_ids and _texto_valido(contexto)
        else {}
    )
    async with await _conexion(entorno.dsn) as c:
        cursor = await c.execute(
            f"""
            UPDATE sesiones
            SET subestado = 'AWAITING_TASK', task_id = %s, inicio_intento = %s,
                context_ids = context_ids || %s, version = version + 1,
                arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND version = %s AND instancia = %s
            """,
            (
                task["id"],
                s.inicio,
                _jsonb(nuevo),
                s.session_id,
                s.version,
                entorno.instancia,
            ),
        )
    if cursor.rowcount == 0:
        return False
    s.version += 1
    s.task_id = task["id"]
    return True


async def _renovar(entorno: Entorno, s: _Sesion) -> float | None:
    """Renueva el arrendamiento en cada sondeo (D-65) y devuelve los segundos que quedan del
    turno, medidos con el reloj de la base de datos (D-69). None si ya no es suyo."""
    async with await conectar(entorno.dsn) as c:
        cursor = await c.execute(
            f"""
            UPDATE sesiones SET arrendamiento_hasta = {FIN_ARRENDAMIENTO}
            WHERE session_id = %s AND version = %s AND instancia = %s
            RETURNING extract(epoch FROM inicio_intento - clock_timestamp()
                + make_interval(secs => (config->>'turnTimeoutSeconds')::bigint))
            """,
            (s.session_id, s.version, entorno.instancia),
        )
        fila = await cursor.fetchone()
    return None if fila is None else float(fila[0])


async def _cancelar(
    cliente: httpx.AsyncClient, url: str, task_id: str, plazo: float
) -> None:
    """La respuesta, o su falta, no cambia nada (D-52, D-60)."""
    try:
        async with asyncio.timeout(plazo):
            await llamar(cliente, url, "CancelTask", {"id": task_id})
    except TimeoutError, ErrorTransporte, ErrorA2A:
        pass


async def _reservar(
    c: psycopg.AsyncConnection[Any], entorno: Entorno, s: _Sesion
) -> datetime | None:
    """Abre la transición por versión y arrendamiento (D-63) y da su instante único (D-69).
    Renueva el arrendamiento, como toda transición (D-65).

    None si otra instancia ha escrito antes: se descarta el trabajo.
    """
    cursor = await c.execute(
        f"""
        UPDATE sesiones
        SET version = version + 1, arrendamiento_hasta = {FIN_ARRENDAMIENTO}
        WHERE session_id = %s AND version = %s AND instancia = %s
        RETURNING clock_timestamp()
        """,
        (s.session_id, s.version, entorno.instancia),
    )
    fila = await cursor.fetchone()
    return None if fila is None else fila[0]


async def _resolver(
    entorno: Entorno, s: _Sesion, task_id: str | None, *fallos: Fallo
) -> bool:
    """Intento fallido: fallos al registro y, agotados los reintentos, `ABORTED` (D-07, D-53).

    shortcut: con `maxRetries = 0` (v0.1.0) todo fallo agota los reintentos;
    feature/reintentos-aborto añade el paso a `READY` con `attempt + 1`.
    """
    async with await _conexion(entorno.dsn) as c:
        ahora = await _reservar(c, entorno, s)
        if ahora is None:
            return False
        for f in fallos:
            await c.execute(
                """
                INSERT INTO fallos (session_id, turn, attempt, task_id, code, field, instante)
                VALUES (%s, %s, 1, %s, %s, %s, %s)
                """,
                (s.session_id, s.turn, task_id, f.code, f.field, ahora),
            )
        primero = fallos[0]  # D-61: los fallos ya vienen en orden de validación
        await _a_closing(
            c,
            s,
            {
                "outcome": "ABORTED",
                "abortReason": "RETRIES_EXHAUSTED",
                "lastFailure": {"code": primero.code, "field": primero.field},
            },
        )
    return False


async def _aceptar(
    entorno: Entorno,
    s: _Sesion,
    tipo: str,
    oferta: dict[str, Any] | None,
    reason: str | None,
) -> bool:
    """Paso 10 y flujos 10a a 10c: acto al registro y transición, en una transacción."""
    if reason is not None:
        reason = texto_seguro(reason)
    async with await _conexion(entorno.dsn) as c:
        ahora = await _reservar(c, entorno, s)
        if ahora is None:
            return False
        await c.execute(
            """
            INSERT INTO actos_aceptados (session_id, turn, emisor, tipo, oferta, reason,
                                         task_id, instante)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                s.session_id,
                s.turn,
                s.parte,
                tipo,
                None if oferta is None else _jsonb(oferta),
                reason,
                s.task_id,
                ahora,
            ),
        )
        if tipo in CON_OFERTA and s.turn < s.config["maxTurns"]:
            await c.execute(
                """
                UPDATE sesiones
                SET turn = turn + 1, attempt = 1, message_id = %s, subestado = 'READY',
                    task_id = NULL, inicio_intento = NULL,
                    oferta_vigente = %s, emisor_oferta = %s
                WHERE session_id = %s
                """,
                (str(uuid4()), _jsonb(oferta), s.parte, s.session_id),
            )
            return True
        if tipo == "ACCEPT":  # D-42, D-84 a D-86: acuerdo provisional, no cierre
            await c.execute(
                """
                UPDATE sesiones
                SET estado = 'HELD', subestado = NULL, task_id = NULL, inicio_intento = NULL,
                    oferta_acordada = oferta_vigente, envios_agreement = %s,
                    held_until = %s
                        + make_interval(secs => (config->>'holdTimeoutSeconds')::bigint)
                WHERE session_id = %s
                """,
                (_jsonb(_pendientes(s)), ahora, s.session_id),
            )
            return False
        if tipo == "WITHDRAW":
            resultado: dict[str, Any] = {"outcome": "WITHDRAWN", "withdrawnBy": s.parte}
            if reason is not None:
                resultado["reason"] = reason
        else:  # D-54, D-57: `COUNTEROFFER` del último turno; la oferta vigente no cambia
            resultado = {"outcome": "NO_AGREEMENT"}
        await _a_closing(c, s, resultado)
    return False


def _pendientes(s: _Sesion) -> dict[str, str]:
    return {p: PENDIENTE for p in s._ids()}


async def _a_closing(
    c: psycopg.AsyncConnection[Any], s: _Sesion, resultado: dict[str, Any]
) -> None:
    """Entrada en `CLOSING` con el resultado y `lastOffers` (D-82) y `SESSION_CLOSE` pendiente."""
    cursor = await c.execute(
        """
        SELECT DISTINCT ON (emisor) emisor, oferta FROM actos_aceptados
        WHERE session_id = %s AND oferta IS NOT NULL
        ORDER BY emisor, turn DESC
        """,
        (s.session_id,),
    )
    ofertas = [{"partyId": e, "offer": o} for e, o in await cursor.fetchall()]
    if ofertas:
        resultado["lastOffers"] = ofertas
    await c.execute(
        """
        UPDATE sesiones
        SET estado = 'CLOSING', subestado = NULL, task_id = NULL, inicio_intento = NULL,
            resultado = %s, envios_close = %s
        WHERE session_id = %s
        """,
        (_jsonb(resultado), _jsonb(_pendientes(s)), s.session_id),
    )

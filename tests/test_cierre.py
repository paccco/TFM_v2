"""Capa del orquestador de CU-02: envío de `SESSION_CLOSE` y paso a `CLOSED` (D-49, D-64, D-70).

Las sesiones se siembran en `CLOSING` con cada `outcome`, también los que aún no se alcanzan en
H1 (`AGREEMENT`, `RELEASED`), y se cierran contra un agente A2A de prueba que responde por parte.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from orquestador.cierre import cerrar
from orquestador.cliente_agentes import a_json
from orquestador.peticiones import URI_EXTENSION
from orquestador.rondas import Entorno
from orquestador.turnos import MEDIA_CONTROL
from tests.conftest import ServidorHttp
from tests.test_turnos import (
    COMPRADOR,
    RUTAS,
    VENDEDOR,
    oferta,
    preparar,
    registro,
    sesion,
)

MENSAJE = "MENSAJE"
ERROR_A2A = "ERROR_A2A"
CAIDA = "CAIDA"
COLGADO = "COLGADO"
OFERTAS = [
    {"partyId": COMPRADOR, "offer": oferta()},
    {"partyId": VENDEDOR, "offer": oferta("11.75")},
]


@dataclass
class Tarea:
    estado: str = "TASK_STATE_WORKING"
    retraso: float = 0


@dataclass
class Llamada:
    parte: str
    metodo: str
    cabeceras: dict[str, str]
    peticion: dict[str, Any]
    arrendamiento: tuple[
        Any, ...
    ]  # (arrendamiento_hasta, clock_timestamp()) al recibirla


@dataclass
class AgenteCierre:
    """Responde a cada parte según `pasos`; por defecto, con una Task en curso."""

    dsn: str
    pasos: dict[str, Any] = field(default_factory=dict)
    al_recibir: Any = None
    llamadas: list[Llamada] = field(default_factory=list)

    async def __call__(self, request: Request) -> Response:
        peticion = json.loads(await request.body(), parse_float=Decimal)
        parte = RUTAS[request.url.path]
        with psycopg.connect(self.dsn) as c:
            arrendamiento = c.execute(
                "SELECT arrendamiento_hasta, clock_timestamp() FROM sesiones"
            ).fetchone()
            if self.al_recibir:
                c.execute(self.al_recibir)
        self.llamadas.append(
            Llamada(
                parte,
                peticion["method"],
                dict(request.headers),
                peticion,
                arrendamiento,  # type: ignore[arg-type]
            )
        )
        paso = self.pasos.get(parte, Tarea())
        id_rpc = peticion["id"]
        if paso == CAIDA:
            return PlainTextResponse("caído", status_code=500)
        if paso == COLGADO:
            await asyncio.sleep(5)
            return PlainTextResponse("tarde", status_code=500)
        if paso == ERROR_A2A:
            error = {"code": -32603, "message": "x"}
            return JSONResponse({"jsonrpc": "2.0", "id": id_rpc, "error": error})
        if paso == MENSAJE:
            resultado: dict[str, Any] = {
                "message": {"messageId": "r", "role": "ROLE_AGENT"}
            }
        else:
            await asyncio.sleep(paso.retraso)
            resultado = {
                "task": {
                    "id": f"c-{parte}",
                    "contextId": "x",
                    "status": {"state": paso.estado},
                }
            }
        return JSONResponse({"jsonrpc": "2.0", "id": id_rpc, "result": resultado})

    def de(self, parte: str) -> Llamada:
        [llamada] = [ll for ll in self.llamadas if ll.parte == parte]
        return llamada


def sembrar(
    dsn: str,
    agentes: ServidorHttp,
    resultado: dict[str, Any],
    turn: int = 1,
    contextos: dict[str, str] | None = None,
    pasos: dict[str, Any] | None = None,
    **cambios: Any,
) -> tuple[Entorno, str, AgenteCierre]:
    """Sesión en `CLOSING` con los dos envíos pendientes y el arrendamiento de esta instancia."""
    ent, sid, _ = preparar(dsn, agentes, {}, **cambios)
    with psycopg.connect(dsn) as c:
        c.execute(
            """
            UPDATE sesiones
            SET estado = 'CLOSING', subestado = NULL, turn = %s, resultado = %s::jsonb,
                envios_close = %s::jsonb, context_ids = %s::jsonb
            """,
            (
                turn,
                a_json(resultado),
                a_json({COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}),
                a_json(contextos or {}),
            ),
        )
    agente = AgenteCierre(dsn, pasos or {})
    agentes.rpc = agente
    return ent, sid, agente


def envios(dsn: str) -> list[tuple[Any, ...]]:
    return registro(
        dsn,
        """
        SELECT tipo, parte, turn, resultado, task_id, estado_task, con_message, code
        FROM envios_control ORDER BY parte
        """,
    )


def cuerpo_de(llamada: Llamada) -> dict[str, Any]:
    [parte] = llamada.peticion["params"]["message"]["parts"]
    assert parte["mediaType"] == MEDIA_CONTROL
    return parte["data"]


RETIRADA = {"outcome": "WITHDRAWN", "withdrawnBy": COMPRADOR}


# --- Mensaje ------------------------------------------------------------------------------


def test_ac_02_01_02_y_04_session_close_a_las_dos_partes(
    dsn: str, agentes: ServidorHttp
) -> None:
    """Cierre en el turno 1: la parte que no abre nunca tuvo turno, así que va sin `contextId`."""
    ent, sid, agente = sembrar(dsn, agentes, RETIRADA, contextos={COMPRADOR: "ctx-c"})
    message_id = sesion(dsn)["message_id"]
    asyncio.run(cerrar(ent, sid))

    assert sorted(ll.parte for ll in agente.llamadas) == [COMPRADOR, VENDEDOR]
    ids = set()
    for ll in agente.llamadas:
        assert ll.metodo == "SendMessage"
        assert ll.cabeceras["a2a-extensions"] == URI_EXTENSION
        params = ll.peticion["params"]
        assert params["configuration"] == {"returnImmediately": True}
        m = params["message"]
        assert (m["role"], m["extensions"]) == ("ROLE_USER", [URI_EXTENSION])
        assert m["metadata"] == {
            URI_EXTENSION: {
                "sessionId": sid,
                "turn": 1,
                "type": "SESSION_CLOSE",
                "sender": "ORCHESTRATOR",
            }
        }
        ids.add(m["messageId"])
    assert len(ids) == 2 and message_id not in ids
    assert agente.de(COMPRADOR).peticion["params"]["message"]["contextId"] == "ctx-c"
    assert "contextId" not in agente.de(VENDEDOR).peticion["params"]["message"]


@pytest.mark.parametrize(
    ("resultado", "turn", "cuerpo"),
    [
        pytest.param(
            {
                "outcome": "WITHDRAWN",
                "withdrawnBy": VENDEDOR,
                "reason": "precio",
                "lastOffers": OFERTAS,
            },
            2,
            {"outcome": "WITHDRAWN", "withdrawnBy": VENDEDOR, "lastOffers": OFERTAS},
            id="withdrawn-sin-reason",
        ),
        pytest.param(RETIRADA, 1, RETIRADA, id="ac-02-17-sin-ofertas"),
        pytest.param(
            {"outcome": "NO_AGREEMENT", "lastOffers": OFERTAS},
            10,
            {"outcome": "NO_AGREEMENT", "lastOffers": OFERTAS},
            id="no-agreement",
        ),
        pytest.param(
            {
                "outcome": "ABORTED",
                "abortReason": "RETRIES_EXHAUSTED",
                "lastFailure": {"code": "TURN_TIMEOUT", "field": "task"},
            },
            1,
            {
                "outcome": "ABORTED",
                "abortReason": "RETRIES_EXHAUSTED",
                "lastFailure": {"code": "TURN_TIMEOUT", "field": "task"},
            },
            id="aborted",
        ),
        pytest.param(
            {"outcome": "AGREEMENT", "agreedOffer": oferta("11.75")},
            3,
            {"outcome": "AGREEMENT", "agreedOffer": oferta("11.75")},
            id="ac-02-15-agreement",
        ),
        pytest.param(
            {
                "outcome": "RELEASED",
                "releaseReason": "BUYER_DECISION",
                "lastOffers": OFERTAS,
            },
            3,
            {
                "outcome": "RELEASED",
                "releaseReason": "BUYER_DECISION",
                "lastOffers": OFERTAS,
            },
            id="ac-02-15-released-buyer",
        ),
        pytest.param(
            {
                "outcome": "RELEASED",
                "releaseReason": "HOLD_EXPIRED",
                "lastOffers": OFERTAS,
            },
            3,
            {
                "outcome": "RELEASED",
                "releaseReason": "HOLD_EXPIRED",
                "lastOffers": OFERTAS,
            },
            id="ac-02-15-released-expired",
        ),
    ],
)
def test_ac_02_03_15_16_y_17_cuerpo_segun_outcome(
    dsn: str,
    agentes: ServidorHttp,
    resultado: dict[str, Any],
    turn: int,
    cuerpo: dict[str, Any],
) -> None:
    ent, sid, agente = sembrar(dsn, agentes, resultado, turn=turn)
    asyncio.run(cerrar(ent, sid))
    assert len(agente.llamadas) == 2
    for ll in agente.llamadas:
        assert cuerpo_de(ll) == cuerpo
        assert (
            ll.peticion["params"]["message"]["metadata"][URI_EXTENSION]["turn"] == turn
        )


# --- Respuestas ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paso", "fila"),
    [
        pytest.param(
            Tarea("TASK_STATE_WORKING"),
            ("ENVIADO", "c-comprador-1", "TASK_STATE_WORKING", False, None),
            id="task-en-curso",
        ),
        pytest.param(
            Tarea("TASK_STATE_FAILED"),
            ("ENVIADO", "c-comprador-1", "TASK_STATE_FAILED", False, None),
            id="task-final",
        ),
        pytest.param(MENSAJE, ("ENVIADO", None, None, True, None), id="message"),
        pytest.param(
            CAIDA, ("FALLIDO", None, None, False, "AGENT_UNREACHABLE"), id="ac-02-06"
        ),
        pytest.param(
            COLGADO, ("FALLIDO", None, None, False, "TURN_TIMEOUT"), id="ac-02-07"
        ),
        pytest.param(
            ERROR_A2A, ("FALLIDO", None, None, False, "AGENT_ERROR"), id="ac-02-08"
        ),
    ],
)
def test_ac_02_05_a_08_y_11_respuesta_registrada(
    dsn: str, agentes: ServidorHttp, paso: Any, fila: tuple[Any, ...]
) -> None:
    ent, sid, agente = sembrar(
        dsn,
        agentes,
        RETIRADA,
        pasos={COMPRADOR: paso},
        turnTimeoutSeconds=2,
        pollIntervalSeconds=1,
    )
    asyncio.run(cerrar(ent, sid))

    assert [ll.metodo for ll in agente.llamadas] == [
        "SendMessage"
    ] * 2  # AC-02-05, AC-02-09
    assert envios(dsn) == [
        ("SESSION_CLOSE", COMPRADOR, 1, *fila),
        (
            "SESSION_CLOSE",
            VENDEDOR,
            1,
            "ENVIADO",
            "c-vendedor-1",
            "TASK_STATE_WORKING",
            False,
            None,
        ),
    ]
    s = sesion(dsn)
    assert s["envios_close"] == {COMPRADOR: fila[0], VENDEDOR: "ENVIADO"}
    assert s["estado"] == "CLOSED"


def test_ac_02_09_un_envio_lento_no_retrasa_el_otro_y_cada_uno_lleva_su_instante(
    dsn: str, agentes: ServidorHttp
) -> None:
    """D-69: el instante de cada entrada es el de la escritura de su marca."""
    ent, sid, _ = sembrar(dsn, agentes, RETIRADA, pasos={COMPRADOR: Tarea(retraso=1.5)})
    inicio = time.monotonic()
    asyncio.run(cerrar(ent, sid))
    assert time.monotonic() - inicio < 2.5  # los dos van a la vez
    [(lento,), (rapido,)] = registro(
        dsn, "SELECT instante FROM envios_control ORDER BY parte"
    )
    assert lento - rapido >= timedelta(seconds=1)


def test_ac_02_10_closed_aunque_fallen_los_dos(dsn: str, agentes: ServidorHttp) -> None:
    resultado = {"outcome": "NO_AGREEMENT", "lastOffers": OFERTAS}
    ent, sid, _ = sembrar(
        dsn, agentes, resultado, pasos={COMPRADOR: CAIDA, VENDEDOR: ERROR_A2A}
    )
    asyncio.run(cerrar(ent, sid))
    s = sesion(dsn)
    assert s["estado"] == "CLOSED"
    assert s["resultado"] == resultado
    assert s["envios_close"] == {COMPRADOR: "FALLIDO", VENDEDOR: "FALLIDO"}
    assert [f[3] for f in envios(dsn)] == ["FALLIDO", "FALLIDO"]


def test_ac_02_11_marca_y_entrada_en_la_misma_transaccion(
    dsn: str, agentes: ServidorHttp
) -> None:
    """Si la entrada no se puede escribir, la marca tampoco queda."""
    ent, sid, _ = sembrar(dsn, agentes, RETIRADA)
    with psycopg.connect(dsn) as c:
        c.execute("DROP TABLE envios_control")
    with pytest.raises(psycopg.errors.UndefinedTable):
        asyncio.run(cerrar(ent, sid))
    s = sesion(dsn)
    assert s["envios_close"] == {COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}
    assert s["estado"] == "CLOSING"


def test_ac_02_13_version_cambiada_descarta_el_trabajo(
    dsn: str, agentes: ServidorHttp
) -> None:
    ent, sid, agente = sembrar(dsn, agentes, RETIRADA)
    agente.al_recibir = "UPDATE sesiones SET version = version + 100"
    asyncio.run(cerrar(ent, sid))
    assert envios(dsn) == []
    s = sesion(dsn)
    assert s["estado"] == "CLOSING"
    assert s["envios_close"] == {COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}


def test_ac_02_14_renueva_el_arrendamiento_antes_de_enviar(
    dsn: str, agentes: ServidorHttp
) -> None:
    ent, sid, agente = sembrar(dsn, agentes, RETIRADA)
    with psycopg.connect(dsn) as c:
        c.execute("UPDATE sesiones SET arrendamiento_hasta = now() - interval '1 hour'")
    asyncio.run(cerrar(ent, sid))
    assert len(agente.llamadas) == 2
    for ll in agente.llamadas:
        hasta, ahora = ll.arrendamiento
        assert hasta > ahora


def test_sin_el_arrendamiento_no_cierra(dsn: str, agentes: ServidorHttp) -> None:
    """D-63: otra instancia tiene la sesión."""
    ent, sid, agente = sembrar(dsn, agentes, RETIRADA)
    with psycopg.connect(dsn) as c:
        c.execute("UPDATE sesiones SET instancia = 'otra'")
    asyncio.run(cerrar(ent, sid))
    assert agente.llamadas == []
    assert sesion(dsn)["estado"] == "CLOSING"

"""Capa del orquestador de CU-01 y CU-03: turnos contra agentes A2A reales (D-58, D-130).

El agente de prueba responde a cada turno con un guion y anota cada llamada. La sesión se crea
como en producción: `OPEN_ROUND` aceptado y AgentCards comprobadas. En v0.1.0 la sesión es
`STRICT` con `maxRetries = 0`, así que el primer fallo aborta (`roadmap.md`, H1).
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types.a2a_pb2 import (
    AgentCard,
    Part,
    SendMessageRequest,
    Task,
    TaskState,
    TaskStatus,
)
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from orquestador.actos import MEDIA_ACTO
from orquestador.peticiones import URI_EXTENSION, origen
from orquestador.rondas import Entorno, comprobar_sesion
from orquestador.turnos import MEDIA_CONTROL, negociar
from tests.conftest import RUTA_AGENTE, ServidorHttp, levantar, tarjeta
from tests.test_rondas import COMPRADOR, VENDEDOR, config, entorno, mensaje, recibir

TERMINOS = {"productId": "p1", "unit": "kg", "currency": "EUR"}
RUTAS = {f"{RUTA_AGENTE}/con.json": COMPRADOR, f"{RUTA_AGENTE}/otro.json": VENDEDOR}

# Pasos del guion que no son una Task.
MENSAJE = "MENSAJE"
ERROR_A2A = "ERROR_A2A"
CAIDA = "CAIDA"
COLGADO = "COLGADO"
NO_EXISTE = "NO_EXISTE"


def oferta_json(precio: str = "12.50", quantity: str = "10") -> str:
    """Cuerpo de una oferta en JSON crudo: así los números llegan tal cual (D-37, D-130)."""
    return (
        '{"offer":{"productId":"p1","unit":"kg","currency":"EUR",'
        f'"quantity":{quantity},"unitPrice":{precio},"deliveryDays":30,"paymentDays":60}}}}'
    )


def oferta(precio: str = "12.50", quantity: int = 10) -> dict[str, Any]:
    return {
        **TERMINOS,
        "quantity": quantity,
        "unitPrice": Decimal(precio),
        "deliveryDays": 30,
        "paymentDays": 60,
    }


@dataclass
class Tarea:
    """Respuesta con una Task. Con `tipo`, lleva un Artifact de acto con ese sobre y `cuerpo`."""

    estado: str = "TASK_STATE_COMPLETED"
    tipo: str | None = None
    cuerpo: str = "{}"


def acto(tipo: str, cuerpo: str = "{}") -> Tarea:
    return Tarea("TASK_STATE_COMPLETED", tipo, cuerpo)


TRABAJANDO = Tarea("TASK_STATE_WORKING")


@dataclass
class Llamada:
    ruta: str
    metodo: str
    cabeceras: dict[str, str]
    peticion: dict[str, Any]
    sesion: tuple[Any, ...]  # (subestado, task_id, context_ids) al recibir la llamada


@dataclass
class Agente:
    """Agente A2A guionizado: por turno, el primer paso responde a `SendMessage` y los demás a
    cada `GetTask`, repitiendo el último. El eco del sobre sigue D-28."""

    dsn: str
    guion: dict[int, list[Any]]
    llamadas: list[Llamada] = field(default_factory=list)
    _turno: int = 0
    _sondeo: int = 0

    async def __call__(self, request: Request) -> Response:
        peticion = json.loads(await request.body(), parse_float=Decimal)
        metodo = peticion["method"]
        with psycopg.connect(self.dsn) as c:
            sesion = c.execute(
                "SELECT subestado, task_id, context_ids FROM sesiones"
            ).fetchone()
        self.llamadas.append(
            Llamada(request.url.path, metodo, dict(request.headers), peticion, sesion)
        )
        if metodo == "CancelTask":
            return _rpc(
                peticion["id"], '{"id":"x","status":{"state":"TASK_STATE_CANCELED"}}'
            )
        if metodo == "SendMessage":
            self._turno = peticion["params"]["message"]["metadata"][URI_EXTENSION][
                "turn"
            ]
            self._sondeo = 0
        else:
            self._sondeo += 1
        pasos = self.guion[self._turno]
        paso = pasos[min(self._sondeo, len(pasos) - 1)]
        return await self._responder(request.url.path, peticion["id"], metodo, paso)

    async def _responder(
        self, ruta: str, id_rpc: Any, metodo: str, paso: Any
    ) -> Response:
        if paso == CAIDA:
            return PlainTextResponse("caído", status_code=500)
        if paso == COLGADO:
            await asyncio.sleep(5)
            return PlainTextResponse("tarde", status_code=500)
        if paso in (ERROR_A2A, NO_EXISTE):
            codigo = -32001 if paso == NO_EXISTE else -32603
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": id_rpc,
                    "error": {"code": codigo, "message": "x"},
                }
            )
        if paso == MENSAJE:
            return _rpc(id_rpc, '{"message":{"messageId":"r1","role":"ROLE_AGENT"}}')
        sobre = {
            "sessionId": self.sesion_id(),
            "turn": self._turno,
            "type": paso.tipo,
            "sender": RUTAS[ruta],
        }
        artefactos = (
            f'[{{"artifactId":"a1","extensions":["{URI_EXTENSION}"],'
            f'"metadata":{{"{URI_EXTENSION}":{json.dumps(sobre)}}},'
            f'"parts":[{{"data":{paso.cuerpo},"mediaType":"{MEDIA_ACTO}"}}]}}]'
            if paso.tipo
            else "[]"
        )
        task = (
            f'{{"id":"t{self._turno}","contextId":"ctx-{RUTAS[ruta]}",'
            f'"status":{{"state":"{paso.estado}"}},"artifacts":{artefactos}}}'
        )
        return _rpc(id_rpc, f'{{"task":{task}}}' if metodo == "SendMessage" else task)

    def sesion_id(self) -> str:
        primera = next(ll for ll in self.llamadas if ll.metodo == "SendMessage")
        return primera.peticion["params"]["message"]["metadata"][URI_EXTENSION][
            "sessionId"
        ]

    def envios(self) -> list[Llamada]:
        return [ll for ll in self.llamadas if ll.metodo == "SendMessage"]

    def metodos(self) -> list[str]:
        return [ll.metodo for ll in self.llamadas]


def _rpc(id_rpc: Any, resultado: str) -> Response:
    texto = f'{{"jsonrpc":"2.0","id":{json.dumps(id_rpc)},"result":{resultado}}}'
    return Response(texto, media_type="application/json")


def preparar(
    dsn: str, agentes: ServidorHttp, guion: dict[int, list[Any]], **cambios: Any
) -> tuple[Entorno, str, Agente]:
    """Sesión en `NEGOTIATING` (`READY`): comprador en `/a2a/con.json`, vendedor en `otro`."""
    ent = entorno(dsn, agentes)
    sesion = recibir(
        ent, mensaje(config(agentes, vendedor="otro", **cambios))
    ).sesiones[0]
    asyncio.run(comprobar_sesion(ent, sesion))
    agente = Agente(dsn, guion)
    agentes.rpc = agente
    return ent, sesion, agente


def sesion(dsn: str) -> dict[str, Any]:
    """Registro de sesión, con los números de los JSON exactos (D-37)."""
    with psycopg.connect(dsn) as c:
        psycopg.types.json.set_json_loads(
            lambda s: json.loads(s, parse_float=Decimal), context=c
        )
        cursor = c.execute("SELECT * FROM sesiones")
        fila = cursor.fetchone()
        assert fila is not None
        return {d.name: v for d, v in zip(cursor.description, fila)}


def registro(dsn: str, sql: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(dsn) as c:
        psycopg.types.json.set_json_loads(
            lambda s: json.loads(s, parse_float=Decimal), context=c
        )
        return c.execute(sql).fetchall()


def actos_aceptados(dsn: str) -> list[tuple[Any, ...]]:
    return registro(
        dsn,
        "SELECT turn, emisor, tipo, oferta, reason, task_id FROM actos_aceptados ORDER BY turn",
    )


def mensaje_de(llamada: Llamada) -> dict[str, Any]:
    return llamada.peticion["params"]["message"]


def cuerpo_de(llamada: Llamada) -> dict[str, Any]:
    [parte] = mensaje_de(llamada)["parts"]
    assert parte["mediaType"] == MEDIA_CONTROL
    return parte["data"]


# --- TURN_REQUEST ------------------------------------------------------------------------


def test_ac_01_01_turn_request_del_turno_1(dsn: str, agentes: ServidorHttp) -> None:
    ent, sid, agente = preparar(dsn, agentes, {1: [acto("WITHDRAW")]}, maxTurns=4)
    message_id = sesion(dsn)["message_id"]
    asyncio.run(negociar(ent, sid))

    [envio] = agente.envios()
    assert envio.ruta == f"{RUTA_AGENTE}/con.json"
    assert envio.cabeceras["a2a-extensions"] == URI_EXTENSION
    assert envio.cabeceras["a2a-version"] == "1.0"
    params = envio.peticion["params"]
    assert params["configuration"] == {"returnImmediately": True}
    m = mensaje_de(envio)
    assert "contextId" not in m
    assert m["messageId"] == message_id
    assert m["role"] == "ROLE_USER"
    assert m["extensions"] == [URI_EXTENSION]
    assert m["metadata"] == {
        URI_EXTENSION: {
            "sessionId": sid,
            "turn": 1,
            "type": "TURN_REQUEST",
            "sender": "ORCHESTRATOR",
        }
    }
    assert cuerpo_de(envio) == {
        "role": "BUYER",
        "fixedTerms": TERMINOS,
        "allowedActs": ["PROPOSE", "WITHDRAW"],
        "turnsLeft": 4,
        "attempt": 1,
    }
    ParseDict(params, SendMessageRequest())  # el SDK la entiende


def test_ac_03_01_turn_request_de_un_turno_2(dsn: str, agentes: ServidorHttp) -> None:
    guion = {1: [acto("PROPOSE", oferta_json())], 2: [acto("WITHDRAW")]}
    ent, sid, agente = preparar(dsn, agentes, guion, maxTurns=4)
    asyncio.run(negociar(ent, sid))

    segundo = agente.envios()[1]
    assert segundo.ruta == f"{RUTA_AGENTE}/otro.json"
    assert (
        mensaje_de(segundo)["messageId"] != mensaje_de(agente.envios()[0])["messageId"]
    )
    assert mensaje_de(segundo)["metadata"][URI_EXTENSION]["turn"] == 2
    assert cuerpo_de(segundo) == {
        "role": "SELLER",
        "fixedTerms": TERMINOS,
        "allowedActs": ["COUNTEROFFER", "ACCEPT", "WITHDRAW"],
        "turnsLeft": 3,
        "lastOffer": oferta(),
        "attempt": 1,
    }


@pytest.mark.parametrize(
    ("abre", "rutas"), [(COMPRADOR, "con otro con"), (VENDEDOR, "otro con otro")]
)
def test_ac_03_02_paridad_de_turnos(
    dsn: str, agentes: ServidorHttp, abre: str, rutas: str
) -> None:
    guion = {
        1: [acto("PROPOSE", oferta_json())],
        2: [acto("COUNTEROFFER", oferta_json("11"))],
        3: [acto("WITHDRAW")],
    }
    ent, sid, agente = preparar(dsn, agentes, guion, openingPartyId=abre)
    asyncio.run(negociar(ent, sid))
    assert [ll.ruta for ll in agente.envios()] == [
        f"{RUTA_AGENTE}/{r}.json" for r in rutas.split()
    ]


def test_ac_01_02_y_ac_03_03_identificadores_guardados_antes_del_sondeo(
    dsn: str, agentes: ServidorHttp
) -> None:
    guion = {
        1: [TRABAJANDO, acto("PROPOSE", oferta_json())],
        2: [TRABAJANDO, acto("COUNTEROFFER", oferta_json())],
        3: [acto("WITHDRAW")],
    }
    ent, sid, agente = preparar(dsn, agentes, guion, pollIntervalSeconds=1)
    asyncio.run(negociar(ent, sid))

    assert agente.metodos() == ["SendMessage", "GetTask"] * 2 + ["SendMessage"]
    sondeo_1, sondeo_2 = [ll for ll in agente.llamadas if ll.metodo == "GetTask"]
    assert sondeo_1.peticion["params"] == {"id": "t1"}
    assert sondeo_1.sesion == ("AWAITING_TASK", "t1", {COMPRADOR: "ctx-comprador-1"})
    assert sondeo_2.sesion == (
        "AWAITING_TASK",
        "t2",
        {COMPRADOR: "ctx-comprador-1", VENDEDOR: "ctx-vendedor-1"},
    )
    envios = agente.envios()
    assert "contextId" not in mensaje_de(
        envios[1]
    )  # AC-03-03: primer turno del vendedor
    assert mensaje_de(envios[2])["contextId"] == "ctx-comprador-1"


# --- Actos aceptados ---------------------------------------------------------------------


def test_ac_01_03_ac_03_04_y_ac_03_06_hasta_held(
    dsn: str, agentes: ServidorHttp
) -> None:
    guion = {
        1: [acto("PROPOSE", oferta_json())],
        2: [acto("COUNTEROFFER", oferta_json("11.75"))],
        3: [acto("ACCEPT")],
    }
    ent, sid, agente = preparar(dsn, agentes, guion, holdTimeoutSeconds=90)
    asyncio.run(negociar(ent, sid))

    assert cuerpo_de(agente.envios()[2])["lastOffer"] == oferta("11.75")
    assert actos_aceptados(dsn) == [
        (1, COMPRADOR, "PROPOSE", oferta(), None, "t1"),
        (2, VENDEDOR, "COUNTEROFFER", oferta("11.75"), None, "t2"),
        (3, COMPRADOR, "ACCEPT", None, None, "t3"),
    ]
    s = sesion(dsn)
    assert (s["estado"], s["subestado"], s["turn"]) == ("HELD", None, 3)
    assert (s["oferta_vigente"], s["emisor_oferta"]) == (oferta("11.75"), VENDEDOR)
    assert s["oferta_acordada"] == oferta("11.75")
    assert s["envios_agreement"] == {COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}
    assert (s["task_id"], s["inicio_intento"], s["resultado"]) == (None, None, None)
    [(instante,)] = registro(dsn, "SELECT instante FROM actos_aceptados WHERE turn = 3")
    assert s["held_until"] == instante + timedelta(seconds=90)


def test_ac_01_03_propose_deja_el_turno_2_en_ready(
    dsn: str, agentes: ServidorHttp
) -> None:
    """La transición del turno 1 se ve en el registro de sesión al recibir el turno 2."""
    guion = {1: [acto("PROPOSE", oferta_json())], 2: [TRABAJANDO, acto("WITHDRAW")]}
    ent, sid, agente = preparar(dsn, agentes, guion)
    primer_id = sesion(dsn)["message_id"]
    asyncio.run(negociar(ent, sid))
    segundo = agente.envios()[1]
    assert segundo.sesion[0] == "READY"
    assert mensaje_de(segundo)["messageId"] not in (primer_id, None)


def test_ac_03_05_counteroffer_del_ultimo_turno(
    dsn: str, agentes: ServidorHttp
) -> None:
    guion = {
        1: [acto("PROPOSE", oferta_json())],
        2: [acto("COUNTEROFFER", oferta_json("11"))],
    }
    ent, sid, _ = preparar(dsn, agentes, guion, maxTurns=2)
    asyncio.run(negociar(ent, sid))

    assert [a[2] for a in actos_aceptados(dsn)] == ["PROPOSE", "COUNTEROFFER"]
    s = sesion(dsn)
    assert (s["estado"], s["subestado"], s["turn"]) == ("CLOSING", None, 2)
    assert (s["oferta_vigente"], s["emisor_oferta"]) == (oferta(), COMPRADOR)
    assert s["resultado"] == {
        "outcome": "NO_AGREEMENT",
        "lastOffers": [
            {"partyId": COMPRADOR, "offer": oferta()},
            {"partyId": VENDEDOR, "offer": oferta("11")},
        ],
    }
    assert s["envios_close"] == {COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}


def test_ac_03_16_y_ac_03_07_counteroffer_identico_y_withdraw(
    dsn: str, agentes: ServidorHttp
) -> None:
    guion = {
        1: [acto("PROPOSE", oferta_json())],
        2: [acto("COUNTEROFFER", oferta_json())],
        3: [acto("WITHDRAW", '{"reason":"precio"}')],
    }
    ent, sid, _ = preparar(dsn, agentes, guion)
    asyncio.run(negociar(ent, sid))

    assert actos_aceptados(dsn)[2] == (3, COMPRADOR, "WITHDRAW", None, "precio", "t3")
    s = sesion(dsn)
    assert (s["estado"], s["turn"], s["emisor_oferta"]) == ("CLOSING", 3, VENDEDOR)
    assert s["resultado"] == {
        "outcome": "WITHDRAWN",
        "withdrawnBy": COMPRADOR,
        "reason": "precio",
        "lastOffers": [
            {"partyId": COMPRADOR, "offer": oferta()},
            {"partyId": VENDEDOR, "offer": oferta()},
        ],
    }


def test_ac_01_16_withdraw_en_el_turno_1(dsn: str, agentes: ServidorHttp) -> None:
    ent, sid, agente = preparar(dsn, agentes, {1: [acto("WITHDRAW")]})
    asyncio.run(negociar(ent, sid))

    assert len(agente.envios()) == 1
    assert actos_aceptados(dsn) == [(1, COMPRADOR, "WITHDRAW", None, None, "t1")]
    s = sesion(dsn)
    assert (s["estado"], s["oferta_vigente"]) == ("CLOSING", None)
    assert s["resultado"] == {"outcome": "WITHDRAWN", "withdrawnBy": COMPRADOR}
    assert s["envios_close"] == {COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}


def test_d_130_y_d_132_numeros_exactos(dsn: str, agentes: ServidorHttp) -> None:
    """El precio no pasa por coma flotante y 10.0 se reenvía como el entero 10."""
    guion = {
        1: [acto("PROPOSE", oferta_json("1234567890123456.78", "10.0"))],
        2: [acto("WITHDRAW")],
    }
    ent, sid, agente = preparar(dsn, agentes, guion)
    asyncio.run(negociar(ent, sid))

    ultima = cuerpo_de(agente.envios()[1])["lastOffer"]
    assert ultima == oferta("1234567890123456.78")
    assert type(ultima["quantity"]) is int
    assert sesion(dsn)["resultado"]["lastOffers"] == [
        {"partyId": COMPRADOR, "offer": oferta("1234567890123456.78")}
    ]


# --- Fallos: con `maxRetries = 0` el primero aborta (AC-01-15, AC-03-19) ------------------


FALLOS = [
    pytest.param(
        [acto("WITHDRAW", '{"reason":5}')],
        ("WRONG_TYPE", "body.reason"),  # válido como acto en los dos turnos salvo R-15
        True,
        id="acto-no-valido",
    ),
    pytest.param(
        [Tarea("TASK_STATE_FAILED")], ("TASK_FAILED", "task"), True, id="failed"
    ),
    pytest.param(
        [Tarea("TASK_STATE_REJECTED")], ("TASK_REJECTED", "task"), True, id="rejected"
    ),
    pytest.param(
        [Tarea("TASK_STATE_CANCELED")], ("TASK_CANCELED", "task"), True, id="canceled"
    ),
    pytest.param(
        [TRABAJANDO, Tarea("TASK_STATE_INPUT_REQUIRED")],
        ("TASK_INTERRUPTED", "task"),
        True,
        id="input-required",
    ),
    pytest.param([TRABAJANDO], ("TURN_TIMEOUT", "task"), True, id="tiempo-en-sondeo"),
    pytest.param([COLGADO], ("TURN_TIMEOUT", "task"), False, id="tiempo-en-envio"),
    pytest.param([MENSAJE], ("MISSING_ACT", "task"), False, id="message"),
    pytest.param([ERROR_A2A], ("AGENT_ERROR", "task"), False, id="error-a2a"),
    pytest.param([CAIDA], ("AGENT_UNREACHABLE", "task"), False, id="error-transporte"),
    pytest.param(
        [TRABAJANDO, NO_EXISTE], ("MISSING_ACT", "task"), True, id="task-not-found"
    ),
]


@pytest.mark.parametrize("turno", [1, 2])
@pytest.mark.parametrize(("pasos", "fallo", "con_task"), FALLOS)
def test_ac_01_15_el_primer_fallo_aborta(
    dsn: str,
    agentes: ServidorHttp,
    turno: int,
    pasos: list[Any],
    fallo: tuple[str, str],
    con_task: bool,
) -> None:
    guion = (
        {1: pasos} if turno == 1 else {1: [acto("PROPOSE", oferta_json())], 2: pasos}
    )
    ent, sid, agente = preparar(
        dsn, agentes, guion, turnTimeoutSeconds=2, pollIntervalSeconds=1
    )
    asyncio.run(negociar(ent, sid))

    task_id = f"t{turno}" if con_task else None
    code, campo = fallo
    assert registro(dsn, "SELECT turn, attempt, task_id, code, field FROM fallos") == [
        (turno, 1, task_id, code, campo)
    ]
    s = sesion(dsn)
    assert (s["estado"], s["subestado"], s["turn"]) == ("CLOSING", None, turno)
    resultado = {
        "outcome": "ABORTED",
        "abortReason": "RETRIES_EXHAUSTED",
        "lastFailure": {"code": code, "field": campo},
    }
    if turno == 2:
        resultado["lastOffers"] = [{"partyId": COMPRADOR, "offer": oferta()}]
    assert s["resultado"] == resultado
    assert s["envios_close"] == {COMPRADOR: "PENDIENTE", VENDEDOR: "PENDIENTE"}
    cancelada = code in ("TURN_TIMEOUT", "TASK_INTERRUPTED") and con_task
    assert ("CancelTask" in agente.metodos()) == cancelada
    assert len(agente.envios()) == turno  # no hay reintento


def test_ac_01_24_error_de_transporte_en_get_task_sigue_sondeando(
    dsn: str, agentes: ServidorHttp
) -> None:
    guion = {1: [TRABAJANDO, CAIDA, acto("WITHDRAW")]}
    ent, sid, agente = preparar(dsn, agentes, guion, turnTimeoutSeconds=5)
    asyncio.run(negociar(ent, sid))
    assert agente.metodos() == ["SendMessage", "GetTask", "GetTask"]
    assert sesion(dsn)["resultado"] == {
        "outcome": "WITHDRAWN",
        "withdrawnBy": COMPRADOR,
    }


def test_d_63_sin_el_arrendamiento_no_negocia(dsn: str, agentes: ServidorHttp) -> None:
    ent, sid, agente = preparar(dsn, agentes, {1: [acto("WITHDRAW")]})
    with psycopg.connect(dsn) as c:
        c.execute("UPDATE sesiones SET instancia = 'otra'")
    antes = sesion(dsn)
    asyncio.run(negociar(ent, sid))
    assert agente.llamadas == []
    assert sesion(dsn) == antes


@dataclass
class _AgenteQueCedeLaSesion(Agente):
    """Al recibir `GetTask`, otra instancia toma la sesión."""

    async def __call__(self, request: Request) -> Response:
        if b'"GetTask"' in await request.body():
            with psycopg.connect(self.dsn) as c:
                c.execute("UPDATE sesiones SET instancia = 'otra'")
        return await super().__call__(request)


def test_d_63_arrendamiento_perdido_durante_el_sondeo(
    dsn: str, agentes: ServidorHttp
) -> None:
    """La instancia descarta su trabajo: ni acto, ni fallo, ni transición."""
    ent, sid, _ = preparar(dsn, agentes, {1: [TRABAJANDO, acto("WITHDRAW")]})
    agente = _AgenteQueCedeLaSesion(dsn, {1: [TRABAJANDO, acto("WITHDRAW")]})
    agentes.rpc = agente
    asyncio.run(negociar(ent, sid))
    assert agente.metodos() == ["SendMessage", "GetTask"]
    assert actos_aceptados(dsn) == []
    assert registro(dsn, "SELECT count(*) FROM fallos") == [(0,)]
    s = sesion(dsn)
    assert (s["estado"], s["subestado"], s["instancia"]) == (
        "NEGOTIATING",
        "AWAITING_TASK",
        "otra",
    )


# --- Interoperabilidad con un agente hecho con a2a-sdk (D-132) ---------------------------


class _EjecutorSdk(AgentExecutor):
    """Agente mínimo con los tipos del SDK: abre con PROPOSE y responde con WITHDRAW."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        assert context.message is not None and context.task_id and context.context_id
        sobre = MessageToDict(context.message.metadata)[URI_EXTENSION]
        turno = int(sobre["turn"])
        cuerpo: dict[str, Any] = {}
        if turno == 1:
            cuerpo = {
                "offer": {
                    **TERMINOS,
                    "quantity": 10,
                    "unitPrice": 12.5,
                    "deliveryDays": 30,
                    "paymentDays": 60,
                }
            }
        datos = Value()
        ParseDict(cuerpo, datos)
        acto_sdk = {
            "sessionId": sobre["sessionId"],
            "turn": turno,
            "type": "PROPOSE" if turno == 1 else "WITHDRAW",
            "sender": COMPRADOR if turno % 2 else VENDEDOR,
        }
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await event_queue.enqueue_event(  # el manejador v2 exige la Task antes que sus eventos
            Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
            )
        )
        await updater.add_artifact(
            [Part(data=datos, media_type=MEDIA_ACTO)],
            metadata={URI_EXTENSION: acto_sdk},
            extensions=[URI_EXTENSION],
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None


def test_d_132_agente_hecho_con_a2a_sdk_llega_a_closing(
    dsn: str, agentes: ServidorHttp
) -> None:
    app = Starlette()
    with levantar(app) as url:
        card = ParseDict(tarjeta(f"{url}/rpc"), AgentCard())
        manejador = DefaultRequestHandler(_EjecutorSdk(), InMemoryTaskStore(), card)
        app.router.routes.extend(
            [
                *create_agent_card_routes(card),
                *create_jsonrpc_routes(manejador, rpc_url="/rpc"),
            ]
        )
        ent = Entorno(dsn, "instancia-a", frozenset({origen(url)}))
        partes = config(agentes, pollIntervalSeconds=1)
        for p in partes["parties"]:
            p["agentCardUrl"] = f"{url}/.well-known/agent-card.json"
        sid = recibir(ent, mensaje(partes)).sesiones[0]
        asyncio.run(comprobar_sesion(ent, sid))
        asyncio.run(negociar(ent, sid))

    s = sesion(dsn)
    assert s["estado"] == "CLOSING"
    assert s["resultado"] == {
        "outcome": "WITHDRAWN",
        "withdrawnBy": VENDEDOR,
        "lastOffers": [{"partyId": COMPRADOR, "offer": oferta("12.5")}],
    }


@dataclass
class _AgenteLento(Agente):
    """Tarda en responder a `SendMessage`, como un agente real."""

    async def __call__(self, request: Request) -> Response:
        if b'"SendMessage"' in await request.body():
            await asyncio.sleep(0.5)
        return await super().__call__(request)


def test_d_65_cada_transicion_renueva_el_arrendamiento(
    dsn: str, agentes: ServidorHttp
) -> None:
    """`maquina-estados.md` §3: el arrendamiento se renueva en cada transición, no solo al
    tomar la sesión antes de `SendMessage`."""
    ent, sid, _ = preparar(dsn, agentes, {})
    agentes.rpc = _AgenteLento(dsn, {1: [acto("WITHDRAW")]})
    asyncio.run(negociar(ent, sid))
    s = sesion(dsn)
    [(instante,)] = registro(dsn, "SELECT instante FROM actos_aceptados")
    duracion = timedelta(
        seconds=s["config"]["turnTimeoutSeconds"] + s["config"]["pollIntervalSeconds"]
    )
    assert s["arrendamiento_hasta"] - instante >= duracion - timedelta(seconds=0.1)

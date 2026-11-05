"""Capa del orquestador de CU-04: aceptación, AgentCards y salida de `CREATED`.

PostgreSQL y servidor HTTP reales; solo se prueba lo que queda escrito y lo que se responde.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from a2a.types.a2a_pb2 import Message, Part, Task, TaskState
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value

from orquestador import rondas
from orquestador.almacen import leer_task
from orquestador.peticiones import (
    MEDIA_PETICION,
    MEDIA_RESULTADO,
    URI_EXTENSION,
    origen,
)
from orquestador.rondas import Entorno, comprobar_sesion, recibir_peticion
from tests.conftest import ServidorHttp

COMPRADOR = "comprador-1"
VENDEDOR = "vendedor-1"


def entorno(dsn: str, agentes: ServidorHttp, instancia: str = "instancia-a") -> Entorno:
    return Entorno(dsn, instancia, frozenset({origen(agentes.url)}))


def config(
    agentes: ServidorHttp, comprador: str = "con", vendedor: str = "con", **cambios: Any
) -> dict[str, Any]:
    return {
        "fixedTerms": {"productId": "p1", "unit": "kg", "currency": "EUR"},
        "parties": [
            {
                "partyId": COMPRADOR,
                "role": "BUYER",
                "agentCardUrl": f"{agentes.url}/{comprador}.json",
            },
            {
                "partyId": VENDEDOR,
                "role": "SELLER",
                "agentCardUrl": f"{agentes.url}/{vendedor}.json",
            },
        ],
        "openingPartyId": COMPRADOR,
        "validationMode": "STRICT",
        "maxRetries": 0,
        **cambios,
    }


def mensaje(
    *configs: dict[str, Any],
    sender: str = COMPRADOR,
    message_id: str = "m1",
    media: str = MEDIA_PETICION,
) -> Message:
    m = Message(message_id=message_id, extensions=[URI_EXTENSION])
    ParseDict({URI_EXTENSION: {"type": "OPEN_ROUND", "sender": sender}}, m.metadata)
    valor = Value()
    ParseDict(
        {"sessions": [{"itemId": f"i{n}", "config": c} for n, c in enumerate(configs)]},
        valor,
    )
    m.parts.append(Part(data=valor, media_type=media))
    return m


def recibir(ent: Entorno, m: Message, identidad: str = COMPRADOR) -> rondas.Recepcion:
    return asyncio.run(recibir_peticion(ent, m, {URI_EXTENSION}, identidad))


def filas(dsn: str, sql: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(dsn) as c:
        return c.execute(sql).fetchall()


def task_guardada(dsn: str, task_id: str) -> Task:
    task = asyncio.run(leer_task(dsn, task_id, COMPRADOR))
    assert task is not None
    return task


def datos_de(parte: Part) -> dict[str, Any]:
    return MessageToDict(parte.data)


def test_ac_04_01_crea_peticion_y_sesiones(dsn: str, agentes: ServidorHttp) -> None:
    """AC-04-01, D-67, D-83."""
    r = recibir(entorno(dsn, agentes), mensaje(config(agentes), config(agentes)))
    assert r.task.status.state == TaskState.TASK_STATE_WORKING
    assert len(r.sesiones) == 2

    [(request_id, comprador, rondas_guardadas)] = filas(
        dsn, "SELECT request_id, comprador, rondas FROM peticiones"
    )
    UUID(str(request_id))
    assert comprador == COMPRADOR
    assert [x["numero"] for x in rondas_guardadas] == [1]
    assert rondas_guardadas[0]["taskId"] == r.task.id
    assert rondas_guardadas[0]["mantenidas"] == []

    sesiones = filas(
        dsn,
        "SELECT session_id, request_id, ronda, item_id, estado FROM sesiones ORDER BY item_id",
    )
    assert [s[3] for s in sesiones] == ["i0", "i1"]
    assert all(s[1] == request_id and s[2] == 1 and s[4] == "CREATED" for s in sesiones)
    assert sorted(str(s[0]) for s in sesiones) == sorted(r.sesiones)
    assert [(x["itemId"], x["sessionId"]) for x in rondas_guardadas[0]["sesiones"]] == [
        ("i0", str(sesiones[0][0])),
        ("i1", str(sesiones[1][0])),
    ]


def test_ac_04_02_guarda_los_valores_efectivos(dsn: str, agentes: ServidorHttp) -> None:
    recibir(entorno(dsn, agentes), mensaje(config(agentes, maxTurns=4)))
    [(guardada,)] = filas(dsn, "SELECT config FROM sesiones")
    assert guardada["maxTurns"] == 4
    assert guardada["turnTimeoutSeconds"] == 60
    assert guardada["holdTimeoutSeconds"] == 1800


def test_d_65_arrendamiento_de_esta_instancia(dsn: str, agentes: ServidorHttp) -> None:
    """D-63, D-65: dura `turnTimeoutSeconds + pollIntervalSeconds`, con el reloj de la base de datos."""
    recibir(entorno(dsn, agentes), mensaje(config(agentes)))
    [(instancia, segundos)] = filas(
        dsn,
        "SELECT instancia, extract(epoch FROM arrendamiento_hasta - clock_timestamp()) FROM sesiones",
    )
    assert instancia == "instancia-a"
    assert 55 < segundos <= 61


def test_ac_04_03_un_fallo_en_la_transaccion_no_deja_nada(
    dsn: str, agentes: ServidorHttp
) -> None:
    """AC-04-03: el fallo se fuerza con un trigger en la última escritura."""
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(
            """
            CREATE FUNCTION fallar() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'fallo forzado'; END $$;
            CREATE TRIGGER forzar BEFORE INSERT ON registro_peticiones
            FOR EACH ROW EXECUTE FUNCTION fallar();
            """
        )
    with pytest.raises(psycopg.errors.RaiseException):
        recibir(entorno(dsn, agentes), mensaje(config(agentes)))
    for tabla in ("peticiones", "sesiones", "tareas", "registro_peticiones"):
        assert filas(dsn, f"SELECT count(*) FROM {tabla}") == [(0,)], tabla


def test_ac_04_05_agentcards_validas_pasan_a_negotiating(
    dsn: str, agentes: ServidorHttp
) -> None:
    ent = entorno(dsn, agentes)
    r = recibir(ent, mensaje(config(agentes)))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    [(estado, subestado, turn, attempt, message_id, fallida)] = filas(
        dsn,
        "SELECT estado, subestado, turn, attempt, message_id, failed_party_id FROM sesiones",
    )
    assert (estado, subestado, turn, attempt) == ("NEGOTIATING", "READY", 1, 1)
    assert message_id
    assert fallida is None


@pytest.mark.parametrize(
    "vendedor", ["sin", "opcional", "basura", "error", "redirige", "no-resuelve"]
)
def test_ac_04_06_agentcard_no_valida_deja_not_started(
    dsn: str, agentes: ServidorHttp, vendedor: str
) -> None:
    """AC-04-06, AC-04-31, D-99: sin extensión, opcional, no interpretable, error o redirección."""
    ent = entorno(dsn, agentes)
    c = config(agentes, vendedor=vendedor)
    r = recibir(ent, mensaje(c))
    if vendedor == "no-resuelve":
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(
                "UPDATE sesiones SET config = jsonb_set(config, '{parties,1,agentCardUrl}',"
                " '\"http://127.0.0.1:9/x\"')"
            )
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    assert filas(dsn, "SELECT estado, failed_party_id FROM sesiones") == [
        ("NOT_STARTED", VENDEDOR)
    ]
    # AC-04-06: no se envía SESSION_CLOSE; AC-04-31: la redirección no se sigue.
    assert all(v.startswith("GET") for v in agentes.visitas)
    assert agentes.visitas.count("GET /con.json") == 1


def test_ac_04_06_agentcard_lenta_supera_el_tiempo_del_turno(
    dsn: str, agentes: ServidorHttp
) -> None:
    ent = entorno(dsn, agentes)
    c = config(agentes, vendedor="lenta", turnTimeoutSeconds=2, pollIntervalSeconds=1)
    r = recibir(ent, mensaje(c))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    assert filas(dsn, "SELECT estado, failed_party_id FROM sesiones") == [
        ("NOT_STARTED", VENDEDOR)
    ]


def test_ac_04_07_si_fallan_las_dos_es_la_primera_de_parties(
    dsn: str, agentes: ServidorHttp
) -> None:
    ent = entorno(dsn, agentes)
    c = config(agentes, comprador="sin", vendedor="basura")
    c["parties"].reverse()
    r = recibir(ent, mensaje(c))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    assert filas(dsn, "SELECT failed_party_id FROM sesiones") == [(VENDEDOR,)]


def test_ac_04_09_y_25_la_task_se_completa_con_la_ultima_sesion(
    dsn: str, agentes: ServidorHttp
) -> None:
    """AC-04-09, AC-04-25, D-94, D-97, D-104."""
    ent = entorno(dsn, agentes)
    r = recibir(ent, mensaje(config(agentes), config(agentes, vendedor="sin")))
    por_item = dict(filas(dsn, "SELECT item_id, session_id::text FROM sesiones"))

    asyncio.run(comprobar_sesion(ent, por_item["i0"]))
    t = task_guardada(dsn, r.task.id)
    assert t.status.state == TaskState.TASK_STATE_WORKING
    assert not t.artifacts

    asyncio.run(comprobar_sesion(ent, por_item["i1"]))
    t = task_guardada(dsn, r.task.id)
    assert t.status.state == TaskState.TASK_STATE_COMPLETED
    [artefacto] = t.artifacts
    assert list(artefacto.extensions) == [URI_EXTENSION]
    assert MessageToDict(artefacto.metadata)[URI_EXTENSION] == {
        "type": "OPEN_ROUND",
        "sender": "ORCHESTRATOR",
    }
    [parte] = artefacto.parts
    assert parte.media_type == MEDIA_RESULTADO
    [(request_id,)] = filas(dsn, "SELECT request_id::text FROM peticiones")
    assert datos_de(parte) == {
        "requestId": request_id,
        "round": 1,
        "sessions": [
            {"itemId": "i0", "sessionId": por_item["i0"], "started": True},
            {
                "itemId": "i1",
                "sessionId": por_item["i1"],
                "started": False,
                "failedPartyId": VENDEDOR,
            },
        ],
    }


def test_ac_04_09_ronda_con_todas_las_sesiones_en_not_started(
    dsn: str, agentes: ServidorHttp
) -> None:
    """Flujo 10a de CU-04: la Task se completa igualmente."""
    ent = entorno(dsn, agentes)
    r = recibir(ent, mensaje(config(agentes, vendedor="sin")))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    assert task_guardada(dsn, r.task.id).status.state == TaskState.TASK_STATE_COMPLETED


def test_salidas_en_paralelo_completan_la_task(dsn: str, agentes: ServidorHttp) -> None:
    """D-63, D-97: la escritura por versión de la petición no pierde ninguna salida."""
    ent = entorno(dsn, agentes)
    r = recibir(ent, mensaje(*[config(agentes) for _ in range(5)]))

    async def todas() -> None:
        await asyncio.gather(*[comprobar_sesion(ent, s) for s in r.sesiones])

    asyncio.run(todas())
    assert filas(dsn, "SELECT count(*) FROM sesiones WHERE estado = 'NEGOTIATING'") == [
        (5,)
    ]
    t = task_guardada(dsn, r.task.id)
    assert t.status.state == TaskState.TASK_STATE_COMPLETED
    assert len(t.artifacts) == 1


def test_flujo_9a_version_cambiada_descarta_el_trabajo(
    dsn: str, agentes: ServidorHttp
) -> None:
    """D-63: si otra instancia escribió durante la comprobación, no se pisa."""
    ent = entorno(dsn, agentes)
    r = recibir(
        ent,
        mensaje(config(agentes, vendedor="lenta", turnTimeoutSeconds=10)),
    )

    async def carrera() -> None:
        comprobacion = asyncio.create_task(comprobar_sesion(ent, r.sesiones[0]))
        await asyncio.sleep(0.5)
        with psycopg.connect(dsn, autocommit=True) as c:
            c.execute("UPDATE sesiones SET version = version + 100")
        await comprobacion

    asyncio.run(carrera())
    assert filas(dsn, "SELECT estado FROM sesiones") == [("CREATED",)]
    assert task_guardada(dsn, r.task.id).status.state == TaskState.TASK_STATE_WORKING


def test_flujo_6c_identificador_repetido_genera_otro(
    dsn: str, agentes: ServidorHttp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-67: un `sessionId` o `requestId` que ya existe se vuelve a generar."""
    ent = entorno(dsn, agentes)
    recibir(ent, mensaje(config(agentes), message_id="m1"))
    [(existente,)] = filas(dsn, "SELECT session_id FROM sesiones")
    secuencia = iter([uuid4(), uuid4(), existente])  # petición, Task y sesión

    def generar() -> UUID:
        return next(secuencia, None) or uuid4()

    monkeypatch.setattr(rondas, "uuid4", generar)
    recibir(ent, mensaje(config(agentes), message_id="m2"))
    assert filas(dsn, "SELECT count(*) FROM sesiones") == [(2,)]
    assert filas(dsn, "SELECT count(*) FROM peticiones") == [(2,)]


def test_ac_04_11_rechazo_con_todos_los_fallos_y_sin_sesiones(
    dsn: str, agentes: ServidorHttp
) -> None:
    """AC-04-11, AC-04-25, D-89, D-97, D-101, D-104."""
    r = recibir(
        entorno(dsn, agentes),
        mensaje(config(agentes, maxTurns=1, validationMode="RARO")),
    )
    assert r.sesiones == []
    t = task_guardada(dsn, r.task.id)
    assert t.status.state == TaskState.TASK_STATE_REJECTED
    aviso = t.status.message
    assert list(aviso.extensions) == [URI_EXTENSION]
    assert MessageToDict(aviso.metadata)[URI_EXTENSION] == {
        "type": "OPEN_ROUND",
        "sender": "ORCHESTRATOR",
    }
    [parte] = aviso.parts
    assert parte.media_type == MEDIA_RESULTADO
    assert datos_de(parte) == {
        "rejections": [
            {"code": "INVALID_CONFIG", "field": "body.sessions.0.config.maxTurns"},
            {"code": "UNKNOWN_VALUE", "field": "body.sessions.0.config.validationMode"},
        ]
    }
    assert filas(dsn, "SELECT count(*) FROM sesiones") == [(0,)]
    assert filas(dsn, "SELECT count(*) FROM peticiones") == [(0,)]
    assert filas(
        dsn,
        "SELECT tipo, request_id, ronda, sender, identidad, message_id, task_id::text,"
        " resultado, codigos FROM registro_peticiones",
    ) == [
        (
            "OPEN_ROUND",
            None,
            None,
            COMPRADOR,
            COMPRADOR,
            "m1",
            r.task.id,
            "RECHAZADA",
            ["INVALID_CONFIG", "UNKNOWN_VALUE"],
        )
    ]


def test_entrada_aceptada_en_el_registro(dsn: str, agentes: ServidorHttp) -> None:
    """D-89, D-98: una entrada con `requestId`, ronda y `taskId`."""
    r = recibir(entorno(dsn, agentes), mensaje(config(agentes)))
    [(request_id,)] = filas(dsn, "SELECT request_id FROM peticiones")
    assert filas(
        dsn,
        "SELECT tipo, request_id, ronda, sender, identidad, message_id, task_id::text,"
        " resultado, codigos FROM registro_peticiones",
    ) == [
        (
            "OPEN_ROUND",
            request_id,
            1,
            COMPRADOR,
            COMPRADOR,
            "m1",
            r.task.id,
            "ACEPTADA",
            [],
        )
    ]


def test_ac_04_24_y_27_rechazo_sin_type_legible_va_sin_sobre(
    dsn: str, agentes: ServidorHttp
) -> None:
    """AC-04-24, AC-04-27, D-103, D-106: queda en el registro y sin sobre."""
    m = mensaje(config(agentes), media="application/json")
    m.metadata.Clear()
    r = recibir(entorno(dsn, agentes), m)
    t = task_guardada(dsn, r.task.id)
    assert t.status.state == TaskState.TASK_STATE_REJECTED
    aviso = t.status.message
    assert list(aviso.extensions) == [URI_EXTENSION]
    assert not MessageToDict(aviso.metadata)
    assert datos_de(aviso.parts[0]) == {
        "rejections": [{"code": "INVALID_MESSAGE", "field": "message"}]
    }
    assert filas(
        dsn, "SELECT tipo, sender, identidad, codigos FROM registro_peticiones"
    ) == [(None, None, COMPRADOR, ["INVALID_MESSAGE"])]


def test_ac_04_27_rechazo_con_type_legible_lleva_sobre(
    dsn: str, agentes: ServidorHttp
) -> None:
    m = mensaje(config(agentes), media="application/json")
    r = recibir(entorno(dsn, agentes), m)
    aviso = task_guardada(dsn, r.task.id).status.message
    assert MessageToDict(aviso.metadata)[URI_EXTENSION] == {
        "type": "OPEN_ROUND",
        "sender": "ORCHESTRATOR",
    }


def test_ac_04_29_sender_suplantado_no_bloquea_el_message_id(
    dsn: str, agentes: ServidorHttp
) -> None:
    """AC-04-29, D-128: el rechazo por suplantación no cuenta para la unicidad."""
    ent = entorno(dsn, agentes)
    falso = recibir(
        ent, mensaje(config(agentes), message_id="m1"), identidad="atacante"
    )
    assert falso.task.status.state == TaskState.TASK_STATE_REJECTED
    autentico = recibir(ent, mensaje(config(agentes), message_id="m1"))
    assert autentico.task.status.state == TaskState.TASK_STATE_WORKING


def test_ac_04_30_leer_task_solo_de_su_identidad(
    dsn: str, agentes: ServidorHttp
) -> None:
    r = recibir(entorno(dsn, agentes), mensaje(config(agentes)))
    assert asyncio.run(leer_task(dsn, r.task.id, "otro")) is None
    assert asyncio.run(leer_task(dsn, str(uuid4()), COMPRADOR)) is None
    assert asyncio.run(leer_task(dsn, "no-es-uuid", COMPRADOR)) is None


def test_turn_timeout_grande_no_bloquea_la_sesion(
    dsn: str, agentes: ServidorHttp
) -> None:
    """`maquina-estados.md` §5: `turnTimeoutSeconds` no tiene máximo."""
    ent = entorno(dsn, agentes)
    r = recibir(ent, mensaje(config(agentes, turnTimeoutSeconds=10_000_000_000)))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    assert filas(dsn, "SELECT estado FROM sesiones") == [("NEGOTIATING",)]


def test_d_65_la_transicion_a_negotiating_renueva_el_arrendamiento(
    dsn: str, agentes: ServidorHttp
) -> None:
    """`maquina-estados.md` §3: se renueva en cada transición."""
    ent = entorno(dsn, agentes)
    c = config(agentes, vendedor="lenta", turnTimeoutSeconds=10)
    c["parties"][1]["agentCardUrl"] = f"{agentes.url}/lenta.json"
    r = recibir(ent, mensaje(c))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    [(segundos,)] = filas(
        dsn,
        "SELECT extract(epoch FROM arrendamiento_hasta - clock_timestamp()) FROM sesiones",
    )
    # Dura 11 s y la AgentCard tarda 3: sin renovar quedarían unos 8.
    assert segundos > 10


def test_duplicado_aceptado_termina_en_error_sin_escribir(
    dsn: str, agentes: ServidorHttp
) -> None:
    """D-98: hasta feature/rechazos-peticiones, error sin escritura, nunca un bucle."""
    ent = entorno(dsn, agentes)
    recibir(ent, mensaje(config(agentes)))

    async def segundo() -> None:
        await asyncio.wait_for(
            recibir_peticion(ent, mensaje(config(agentes)), {URI_EXTENSION}, COMPRADOR),
            timeout=5,
        )

    with pytest.raises(psycopg.errors.UniqueViolation):
        asyncio.run(segundo())
    assert filas(dsn, "SELECT count(*) FROM sesiones") == [(1,)]
    assert filas(dsn, "SELECT count(*) FROM registro_peticiones") == [(1,)]


def test_ac_04_06_el_unico_tiempo_maximo_es_turn_timeout(
    dsn: str, agentes: ServidorHttp
) -> None:
    """D-99: una AgentCard que tarda 6 s es válida con `turnTimeoutSeconds = 10`."""
    ent = entorno(dsn, agentes)
    c = config(agentes, vendedor="seis-segundos", turnTimeoutSeconds=10)
    r = recibir(ent, mensaje(c))
    asyncio.run(comprobar_sesion(ent, r.sesiones[0]))
    assert filas(dsn, "SELECT estado FROM sesiones") == [("NEGOTIATING",)]

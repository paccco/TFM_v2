"""Capa A2A de CU-04: el orquestador como servidor del coordinador, por HTTP real (D-87, D-127, D-128)."""

import time
from collections.abc import Iterator
from typing import Any

import httpx
import psycopg
import pytest

from orquestador.peticiones import MEDIA_PETICION, URI_EXTENSION, origen
from orquestador.rondas import Entorno
from orquestador.servidor import crear_app, leer_origenes, leer_tokens
from tests.conftest import ServidorHttp, levantar

COMPRADOR = "comprador-1"
TOKEN = "token-de-prueba-comprador"
TOKEN_OTRO = "token-de-prueba-otro"
TOKENS = {TOKEN: COMPRADOR, TOKEN_OTRO: "comprador-2"}
TARJETA = "/.well-known/agent-card.json"
NOT_FOUND_TASK = -32001


@pytest.fixture
def orquestador(dsn: str, agentes: ServidorHttp) -> Iterator[str]:
    with instancia(dsn, agentes, "instancia-a") as url:
        yield url


def instancia(dsn: str, agentes: ServidorHttp, nombre: str) -> Any:
    entorno = Entorno(dsn, nombre, frozenset({origen(agentes.url)}))
    return levantar(crear_app(entorno, TOKENS, "http://orquestador.test/"))


def config(agentes: ServidorHttp, vendedor: str = "con") -> dict[str, Any]:
    return {
        "fixedTerms": {"productId": "p1", "unit": "kg", "currency": "EUR"},
        "parties": [
            {
                "partyId": COMPRADOR,
                "role": "BUYER",
                "agentCardUrl": f"{agentes.url}/con.json",
            },
            {
                "partyId": "v1",
                "role": "SELLER",
                "agentCardUrl": f"{agentes.url}/{vendedor}.json",
            },
        ],
        "openingPartyId": COMPRADOR,
        "validationMode": "STRICT",
        "maxRetries": 0,
    }


def open_round(
    cfg: dict[str, Any],
    sender: str = COMPRADOR,
    message_id: str = "m1",
    inmediato: bool = False,
) -> dict[str, Any]:
    return {
        "message": {
            "messageId": message_id,
            "role": "ROLE_USER",
            "extensions": [URI_EXTENSION],
            "metadata": {URI_EXTENSION: {"type": "OPEN_ROUND", "sender": sender}},
            "parts": [
                {
                    "data": {"sessions": [{"itemId": "i0", "config": cfg}]},
                    "mediaType": MEDIA_PETICION,
                }
            ],
        },
        "configuration": {"returnImmediately": inmediato},
    }


def rpc(
    url: str,
    metodo: str,
    params: dict[str, Any],
    token: str = TOKEN,
    extension: bool = True,
) -> httpx.Response:
    cabeceras = {"A2A-Version": "1.0", "Authorization": f"Bearer {token}"}
    if extension:
        cabeceras["A2A-Extensions"] = URI_EXTENSION
    return httpx.post(
        url,
        headers=cabeceras,
        json={"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params},
        timeout=15,
    )


def enviar(url: str, params: dict[str, Any], **k: Any) -> dict[str, Any]:
    respuesta = rpc(url, "SendMessage", params, **k)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert "result" in cuerpo, cuerpo
    return cuerpo["result"]["task"]


def contar(dsn: str, tabla: str) -> int:
    with psycopg.connect(dsn) as c:
        fila = c.execute(f"SELECT count(*) FROM {tabla}").fetchone()
    assert fila is not None
    return fila[0]


def test_ac_04_28_la_agentcard_es_publica_y_declara_extension_y_bearer(
    orquestador: str,
) -> None:
    """D-87, D-128."""
    respuesta = httpx.get(orquestador + TARJETA)
    assert respuesta.status_code == 200
    tarjeta = respuesta.json()
    assert {"uri": URI_EXTENSION, "required": True}.items() <= tarjeta["capabilities"][
        "extensions"
    ][0].items()
    [esquema] = tarjeta["securitySchemes"].values()
    assert esquema["httpAuthSecurityScheme"]["scheme"].lower() == "bearer"
    assert tarjeta["securityRequirements"]
    assert tarjeta["supportedInterfaces"][0]["url"] == "http://orquestador.test/"


@pytest.mark.parametrize(
    "cabeceras",
    [
        {},
        {"Authorization": "Bearer token-falso"},
        {"Authorization": "Bearer"},
        {"Authorization": f"Basic {TOKEN}"},
        {"Authorization": "Bearer tóken".encode()},
    ],
)
def test_ac_04_28_sin_credencial_valida_401_y_nada_escrito(
    dsn: str, orquestador: str, agentes: ServidorHttp, cabeceras: dict[str, Any]
) -> None:
    respuesta = httpx.post(
        orquestador,
        headers={"A2A-Extensions": URI_EXTENSION, **cabeceras},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "SendMessage",
            "params": open_round(config(agentes)),
        },
    )
    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"].lower().startswith("bearer")
    for tabla in ("peticiones", "sesiones", "tareas", "registro_peticiones"):
        assert contar(dsn, tabla) == 0


def test_camino_valido_sin_return_immediately_espera_al_resultado(
    dsn: str, orquestador: str, agentes: ServidorHttp
) -> None:
    """Paso 7 de CU-04: sin `returnImmediately`, responde al completarse."""
    task = enviar(orquestador, open_round(config(agentes)))
    assert task["status"]["state"] == "TASK_STATE_COMPLETED"
    [parte] = task["artifacts"][0]["parts"]
    assert parte["data"]["sessions"][0]["started"] is True
    with psycopg.connect(dsn) as c:
        assert c.execute("SELECT estado FROM sesiones").fetchall() == [("NEGOTIATING",)]


def test_return_immediately_responde_enseguida_y_completa_despues(
    orquestador: str, agentes: ServidorHttp
) -> None:
    """Paso 7 y AC-04-09: Task en `TASK_STATE_WORKING` y después el resultado por `GetTask`."""
    task = enviar(
        orquestador, open_round(config(agentes, vendedor="lenta"), inmediato=True)
    )
    assert task["status"]["state"] == "TASK_STATE_WORKING"
    for _ in range(100):
        leida = rpc(orquestador, "GetTask", {"id": task["id"]}).json()["result"]
        if leida["status"]["state"] == "TASK_STATE_COMPLETED":
            break
        time.sleep(0.1)
    assert leida["status"]["state"] == "TASK_STATE_COMPLETED"


def test_ac_04_22_get_task_en_otra_instancia_tras_caer_la_primera(
    dsn: str, agentes: ServidorHttp
) -> None:
    """AC-04-22, D-97: la segunda instancia solo comparte la base de datos."""
    with instancia(dsn, agentes, "instancia-a") as a:
        task = enviar(a, open_round(config(agentes)))
    with instancia(dsn, agentes, "instancia-b") as b:
        leida = rpc(b, "GetTask", {"id": task["id"]}).json()["result"]
    assert leida == task


def test_ac_04_24_message_sin_cabecera_es_rechazo_con_task(
    dsn: str, orquestador: str, agentes: ServidorHttp
) -> None:
    """AC-04-24: el `A2A-Extensions` ausente se ve por HTTP; queda en el registro."""
    task = enviar(orquestador, open_round(config(agentes)), extension=False)
    assert task["status"]["state"] == "TASK_STATE_REJECTED"
    assert contar(dsn, "registro_peticiones") == 1


def test_ac_04_24_message_sin_parts_es_rechazo_con_task(orquestador: str) -> None:
    """D-103: lo rechaza el orquestador, no el SDK con un error A2A."""
    params = {
        "message": {
            "messageId": "m1",
            "role": "ROLE_USER",
            "extensions": [URI_EXTENSION],
            "metadata": {URI_EXTENSION: {"type": "OPEN_ROUND", "sender": COMPRADOR}},
        }
    }
    task = enviar(orquestador, params)
    assert task["status"]["state"] == "TASK_STATE_REJECTED"
    [parte] = task["status"]["message"]["parts"]
    assert parte["data"] == {
        "rejections": [{"code": "INVALID_MESSAGE", "field": "message"}]
    }


def test_ac_04_29_identidad_autenticada_distinta_del_sender(
    dsn: str, orquestador: str, agentes: ServidorHttp
) -> None:
    """AC-04-29, D-128: un token válido no sirve para actuar como otro comprador."""
    task = enviar(orquestador, open_round(config(agentes)), token=TOKEN_OTRO)
    assert task["status"]["state"] == "TASK_STATE_REJECTED"
    [parte] = task["status"]["message"]["parts"]
    assert parte["data"] == {
        "rejections": [{"code": "NOT_AUTHORIZED", "field": "envelope.sender"}]
    }
    assert contar(dsn, "sesiones") == 0


def test_ac_04_30_get_task_de_otra_identidad_como_si_no_existiera(
    orquestador: str, agentes: ServidorHttp
) -> None:
    task = enviar(orquestador, open_round(config(agentes)))
    ajena = rpc(orquestador, "GetTask", {"id": task["id"]}, token=TOKEN_OTRO).json()
    inexistente = rpc(
        orquestador, "GetTask", {"id": "00000000-0000-0000-0000-000000000000"}
    ).json()
    assert ajena["error"]["code"] == NOT_FOUND_TASK
    assert ajena["error"] == inexistente["error"]


def test_ac_04_31_origen_no_permitido_sin_ninguna_peticion_de_red(
    dsn: str, orquestador: str, agentes: ServidorHttp
) -> None:
    cfg = config(agentes)
    cfg["parties"][1]["agentCardUrl"] = "http://169.254.169.254/latest/meta-data"
    task = enviar(orquestador, open_round(cfg))
    assert task["status"]["state"] == "TASK_STATE_REJECTED"
    [parte] = task["status"]["message"]["parts"]
    assert parte["data"] == {
        "rejections": [
            {
                "code": "INVALID_CONFIG",
                "field": "body.sessions.0.config.parties.1.agentCardUrl",
            }
        ]
    }
    assert agentes.visitas == []
    assert contar(dsn, "sesiones") == 0


@pytest.mark.parametrize(
    "metodo",
    ["CancelTask", "ListTasks", "GetExtendedAgentCard", "SendStreamingMessage"],
)
def test_d_127_los_demas_metodos_no_se_admiten(
    orquestador: str, agentes: ServidorHttp, metodo: str
) -> None:
    params = {"id": "x"}
    if metodo == "SendStreamingMessage":
        params = open_round(config(agentes))
    assert "error" in rpc(orquestador, metodo, params).json()


def test_leer_tokens() -> None:
    """D-128: `partyId=token` separados por comas; sin configuración, nadie se autentica."""
    assert leer_tokens("c1=abc,c2=d=e") == {"abc": "c1", "d=e": "c2"}
    assert leer_tokens("") == {}
    with pytest.raises(ValueError, match="ORQUESTADOR_TOKENS"):
        leer_tokens("c1=")
    with pytest.raises(ValueError, match="ORQUESTADOR_TOKENS"):
        leer_tokens("c1")


def test_leer_origenes() -> None:
    """D-129: sin configuración no se permite ningún origen; una entrada rara no se acepta."""
    assert leer_origenes("") == frozenset()
    assert leer_origenes("https://a.test, http://b.test:8000") == frozenset(
        {("https", "a.test", 443), ("http", "b.test", 8000)}
    )
    for raro in ("a.test", "http://", "::"):
        with pytest.raises(ValueError, match="ORQUESTADOR_ORIGENES_AGENTES"):
            leer_origenes(raro)

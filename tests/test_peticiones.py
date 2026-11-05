"""Capa 1 de CU-04: forma, sobre, cuerpo y configuración de una petición (D-89 a D-93, D-101 a D-103).

Sin base de datos ni red: validar es una función pura sobre el Message.
"""

from copy import deepcopy
from typing import Any

import pytest
from a2a.types.a2a_pb2 import Message, Part
from google.protobuf.json_format import ParseDict
from google.protobuf.struct_pb2 import Value

from orquestador.peticiones import (
    MEDIA_PETICION,
    URI_EXTENSION,
    Fallo,
    PeticionValidada,
    origen,
    validar_peticion,
)

ORIGENES = frozenset({origen("http://agentes.test:8000")})
COMPRADOR = "comprador-1"


def config(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "fixedTerms": {"productId": "p1", "unit": "kg", "currency": "EUR"},
        "parties": [
            {
                "partyId": COMPRADOR,
                "role": "BUYER",
                "agentCardUrl": "http://agentes.test:8000/comprador.json",
            },
            {
                "partyId": "vendedor-1",
                "role": "SELLER",
                "agentCardUrl": "http://agentes.test:8000/vendedor.json",
            },
        ],
        "openingPartyId": COMPRADOR,
        "validationMode": "STRICT",
        "maxRetries": 0,
    }
    base.update(cambios)
    return base


def cuerpo(*configs: dict[str, Any]) -> dict[str, Any]:
    return {
        "sessions": [
            {"itemId": f"item-{i}", "config": c}
            for i, c in enumerate(configs or [config()])
        ]
    }


def mensaje(
    datos: Any = None,
    sobre: Any = None,
    extensiones: tuple[str, ...] = (URI_EXTENSION,),
    media: str = MEDIA_PETICION,
) -> Message:
    m = Message(message_id="m1", extensions=extensiones)
    ParseDict(
        {
            URI_EXTENSION: {"type": "OPEN_ROUND", "sender": COMPRADOR}
            if sobre is None
            else sobre
        },
        m.metadata,
    )
    valor = Value()
    ParseDict(cuerpo() if datos is None else datos, valor)
    m.parts.append(Part(data=valor, media_type=media))
    return m


def validar(m: Message, identidad: str = COMPRADOR) -> PeticionValidada:
    return validar_peticion(m, {URI_EXTENSION}, identidad, ORIGENES)


def fallos_de(*a: Any, **k: Any) -> list[tuple[str, str]]:
    return [(f.code, f.field) for f in validar(mensaje(*a, **k)).fallos]


def test_peticion_valida_no_tiene_fallos() -> None:
    v = validar(mensaje())
    assert v.fallos == []
    assert v.tipo == "OPEN_ROUND"
    assert v.sender == COMPRADOR
    assert [s.item_id for s in v.sesiones] == ["item-0"]


def test_ac_04_02_valores_efectivos_con_los_por_defecto() -> None:
    """AC-04-02, D-91: un parámetro ausente toma su valor por defecto, como entero."""
    efectiva = validar(mensaje()).sesiones[0].config
    assert efectiva["turnTimeoutSeconds"] == 60
    assert efectiva["pollIntervalSeconds"] == 1
    assert efectiva["maxTurns"] == 10
    assert efectiva["holdTimeoutSeconds"] == 1800
    assert efectiva["maxRetries"] == 0
    assert isinstance(efectiva["maxTurns"], int)


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"maxTurns": 1}, "maxTurns"),
        ({"maxRetries": -1}, "maxRetries"),
        ({"turnTimeoutSeconds": 0}, "turnTimeoutSeconds"),
        ({"pollIntervalSeconds": 0}, "pollIntervalSeconds"),
        ({"holdTimeoutSeconds": 0}, "holdTimeoutSeconds"),
        # AC-04-12: solo aparece con los valores efectivos (el sondeo por defecto vale 1).
        ({"turnTimeoutSeconds": 1}, "pollIntervalSeconds"),
        ({"openingPartyId": "otro"}, "openingPartyId"),
        (
            {"fixedTerms": {"productId": "", "unit": "kg", "currency": "EUR"}},
            "fixedTerms.productId",
        ),
        (
            {"fixedTerms": {"productId": "p", "unit": "", "currency": "EUR"}},
            "fixedTerms.unit",
        ),
        (
            {"fixedTerms": {"productId": "p", "unit": "kg", "currency": "XXZ"}},
            "fixedTerms.currency",
        ),
        # Límites de v0.1.0 (roadmap).
        ({"validationMode": "TOLERANT"}, "validationMode"),
        ({"maxRetries": 1}, "maxRetries"),
    ],
)
def test_ac_04_12_restriccion_incumplida(cambios: dict[str, Any], campo: str) -> None:
    assert fallos_de(cuerpo(config(**cambios))) == [
        ("INVALID_CONFIG", f"body.sessions.0.config.{campo}")
    ]


def test_limite_maxretries_ausente_vale_2_y_se_rechaza() -> None:
    """Límite de v0.1.0, D-91: si falta, su valor efectivo es 2."""
    c = config()
    del c["maxRetries"]
    assert fallos_de(cuerpo(c)) == [
        ("INVALID_CONFIG", "body.sessions.0.config.maxRetries")
    ]


@pytest.mark.parametrize(
    "partes",
    [
        [],
        [
            {
                "partyId": COMPRADOR,
                "role": "BUYER",
                "agentCardUrl": "http://agentes.test:8000/c",
            }
        ],
        [
            {
                "partyId": COMPRADOR,
                "role": "BUYER",
                "agentCardUrl": "http://agentes.test:8000/c",
            },
            {
                "partyId": COMPRADOR,
                "role": "SELLER",
                "agentCardUrl": "http://agentes.test:8000/v",
            },
        ],
        [
            {
                "partyId": COMPRADOR,
                "role": "BUYER",
                "agentCardUrl": "http://agentes.test:8000/c",
            },
            {
                "partyId": "otro",
                "role": "BUYER",
                "agentCardUrl": "http://agentes.test:8000/v",
            },
        ],
    ],
)
def test_partes_exactamente_dos_distintas_y_un_papel_de_cada(
    partes: list[dict[str, str]],
) -> None:
    """D-90: dos partes con `partyId` distintos, un `BUYER` y un `SELLER`."""
    assert (
        "INVALID_CONFIG",
        "body.sessions.0.config.parties",
    ) in fallos_de(cuerpo(config(parties=partes)))


def test_ac_04_11_todos_los_fallos_ordenados_por_ruta() -> None:
    """AC-04-11, D-101: una sola pasada; el índice 10 va después del 2."""
    buenas = [config() for _ in range(11)]
    buenas[10]["maxTurns"] = 1
    buenas[2]["maxTurns"] = 1
    buenas[2]["validationMode"] = "RARO"
    datos = cuerpo(*buenas)
    assert fallos_de(
        datos, sobre={"type": "OPEN_ROUND", "sender": COMPRADOR, "x": 1}
    ) == [
        ("INVALID_CONFIG", "body.sessions.2.config.maxTurns"),
        ("UNKNOWN_VALUE", "body.sessions.2.config.validationMode"),
        ("INVALID_CONFIG", "body.sessions.10.config.maxTurns"),
        ("UNKNOWN_FIELD", "envelope.x"),
    ]


@pytest.mark.parametrize(
    ("cambio", "esperado"),
    [
        ({"maxTurns": "10"}, ("WRONG_TYPE", "maxTurns")),
        ({"maxTurns": 2.5}, ("WRONG_TYPE", "maxTurns")),
        ({"maxTurns": True}, ("WRONG_TYPE", "maxTurns")),
        ({"validationMode": 3}, ("WRONG_TYPE", "validationMode")),
        ({"raro": 1}, ("UNKNOWN_FIELD", "raro")),
        ({"fixedTerms": "p1"}, ("WRONG_TYPE", "fixedTerms")),
        ({"parties": "p"}, ("WRONG_TYPE", "parties")),
    ],
)
def test_fallo_estructural_en_la_configuracion(
    cambio: dict[str, Any], esperado: tuple[str, str]
) -> None:
    """D-101: un fallo estructural no añade otros sobre ese campo."""
    assert fallos_de(cuerpo(config(**cambio))) == [
        (esperado[0], f"body.sessions.0.config.{esperado[1]}")
    ]


def test_campo_obligatorio_ausente() -> None:
    c = config()
    del c["validationMode"]
    assert fallos_de(cuerpo(c)) == [
        ("MISSING_FIELD", "body.sessions.0.config.validationMode")
    ]


def test_cuerpo_sin_sessions_o_con_lista_vacia() -> None:
    assert fallos_de({}) == [("MISSING_FIELD", "body.sessions")]
    assert fallos_de({"sessions": "x"}) == [("WRONG_TYPE", "body.sessions")]
    assert fallos_de({"sessions": []}) == [("INVALID_CONFIG", "body.sessions")]
    assert fallos_de([1]) == [("WRONG_TYPE", "body")]


def test_limite_requestid_siempre_se_rechaza() -> None:
    """Límite de v0.1.0: exista o no la petición."""
    assert fallos_de({**cuerpo(), "requestId": "cualquiera"}) == [
        ("UNKNOWN_REQUEST", "body.requestId")
    ]
    assert fallos_de({**cuerpo(), "requestId": 1}) == [("WRONG_TYPE", "body.requestId")]


def test_ac_04_13_item_repetido_rechaza_cada_aparicion_posterior() -> None:
    datos = cuerpo(config(), config())
    datos["sessions"][1]["itemId"] = "item-0"
    assert fallos_de(datos) == [("INVALID_CONFIG", "body.sessions.1.itemId")]


def test_ac_04_13_buyer_distinto_entre_sesiones_sin_not_authorized() -> None:
    otra = deepcopy(config())
    otra["parties"][0]["partyId"] = "comprador-2"
    otra["openingPartyId"] = "comprador-2"
    assert fallos_de(cuerpo(config(), otra)) == [
        ("INVALID_CONFIG", "body.sessions.1.config.parties.0.partyId")
    ]


@pytest.mark.parametrize(
    "sobre",
    [
        {"type": "OPEN_ROUND", "sender": COMPRADOR, "sessionId": "s"},
        {"type": "OPEN_ROUND", "sender": COMPRADOR, "turn": 1},
        {"type": "OPEN_ROUND", "sender": COMPRADOR, "otro": "x"},
    ],
)
def test_ac_04_17_sobre_con_campo_no_definido(sobre: dict[str, Any]) -> None:
    campo = next(k for k in sobre if k not in ("type", "sender"))
    assert fallos_de(sobre=sobre) == [("UNKNOWN_FIELD", f"envelope.{campo}")]


def test_sobre_con_type_o_sender_no_validos() -> None:
    assert fallos_de(sobre={"sender": COMPRADOR}) == [
        ("MISSING_FIELD", "envelope.type")
    ]
    assert fallos_de(sobre={"type": 1, "sender": COMPRADOR}) == [
        ("WRONG_TYPE", "envelope.type")
    ]
    assert fallos_de(sobre={"type": "PROPOSE", "sender": COMPRADOR}) == [
        ("UNKNOWN_VALUE", "envelope.type")
    ]
    assert fallos_de(sobre={"type": "OPEN_ROUND"}) == [
        ("MISSING_FIELD", "envelope.sender")
    ]
    assert fallos_de(sobre={"type": "OPEN_ROUND", "sender": 1}) == [
        ("WRONG_TYPE", "envelope.sender")
    ]


def test_ac_04_23_buyer_igual_en_todas_pero_distinto_del_sender() -> None:
    assert validar(
        mensaje(sobre={"type": "OPEN_ROUND", "sender": "otro"}), identidad="otro"
    ).fallos == [Fallo("NOT_AUTHORIZED", "envelope.sender")]


def test_ac_04_29_sender_distinto_de_la_identidad_aunque_coincida_con_el_buyer() -> (
    None
):
    """AC-04-29, D-128: suplantar al comprador."""
    assert validar(mensaje(), identidad="atacante").fallos == [
        Fallo("NOT_AUTHORIZED", "envelope.sender")
    ]


def test_ac_04_29_un_solo_fallo_por_ruta() -> None:
    """D-128: `sender` ajeno al `BUYER` y a la identidad da un solo fallo."""
    v = validar(mensaje(sobre={"type": "OPEN_ROUND", "sender": "x"}), identidad="y")
    assert v.fallos == [Fallo("NOT_AUTHORIZED", "envelope.sender")]


@pytest.mark.parametrize(
    "url",
    [
        "http://otro.test:8000/c",
        "http://agentes.test:8001/c",
        "https://agentes.test:8000/c",
        "http://agentes.test/c",
        "http://agentes.test:8000@otro.test/c",
        "file:///etc/passwd",
        "no es una url",
        "",
    ],
)
def test_ac_04_31_origen_no_permitido(url: str) -> None:
    c = config()
    c["parties"][1]["agentCardUrl"] = url
    assert fallos_de(cuerpo(c)) == [
        ("INVALID_CONFIG", "body.sessions.0.config.parties.1.agentCardUrl")
    ]


def test_ac_04_31_origen_permitido_no_distingue_mayusculas_ni_puerto_por_defecto() -> (
    None
):
    assert origen("HTTP://Agentes.Test:80/x") == origen("http://agentes.test/y")


def test_ac_04_24_sin_cabecera_de_extension() -> None:
    v = validar_peticion(mensaje(), set(), COMPRADOR, ORIGENES)
    assert v.fallos == [Fallo("INVALID_MESSAGE", "message")]
    # D-103: la entrada lleva type y sender si se pudieron leer.
    assert (v.tipo, v.sender) == ("OPEN_ROUND", COMPRADOR)


def test_ac_04_24_sin_uri_en_extensions() -> None:
    assert fallos_de(extensiones=()) == [("INVALID_MESSAGE", "message")]


def test_ac_04_24_sin_sobre() -> None:
    m = mensaje()
    m.metadata.Clear()
    v = validar(m)
    assert v.fallos == [Fallo("INVALID_MESSAGE", "message")]
    assert (v.tipo, v.sender) == (None, None)


def test_ac_04_24_sin_part_con_varias_parts_o_de_otro_tipo() -> None:
    sin = mensaje()
    del sin.parts[:]
    varias = mensaje()
    varias.parts.append(varias.parts[0])
    texto = mensaje()
    del texto.parts[:]
    texto.parts.append(Part(text="hola", media_type=MEDIA_PETICION))
    for m in (sin, varias, texto, mensaje(media="application/json")):
        assert validar(m).fallos == [Fallo("INVALID_MESSAGE", "message")]


def test_ac_04_27_tipo_no_legible_queda_sin_tipo() -> None:
    """AC-04-27, D-106: sin `type` de petición válido, el rechazo irá sin sobre."""
    v = validar_peticion(
        mensaje(sobre={"type": "PROPOSE", "sender": COMPRADOR}),
        set(),
        COMPRADOR,
        ORIGENES,
    )
    assert v.tipo is None
    assert v.sender == COMPRADOR

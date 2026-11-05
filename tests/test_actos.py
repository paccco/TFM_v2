"""Capa 1 de CU-01 y CU-03: validación estricta del acto (pasos 6 a 9).

Los actos llegan como JSON leído con los números exactos (D-37, D-130), así que aquí se
construyen con `json.loads(..., parse_float=Decimal)`.
"""

import json
from decimal import Decimal
from typing import Any

import pytest

from orquestador.actos import MEDIA_ACTO, validar_acto
from orquestador.peticiones import URI_EXTENSION, Fallo

SESION = "11111111-1111-1111-1111-111111111111"
COMPRADOR = "comprador-1"
VENDEDOR = "vendedor-1"
TERMINOS = {"productId": "p1", "unit": "kg", "currency": "EUR"}


def leer(texto: str) -> Any:
    return json.loads(texto, parse_float=Decimal)


def oferta(**cambios: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        **TERMINOS,
        "quantity": 10,
        "unitPrice": Decimal("12.50"),
        "deliveryDays": 30,
        "paymentDays": 60,
    }
    base.update(cambios)
    return {k: v for k, v in base.items() if v is not None}


def sobre(
    tipo: Any = "PROPOSE", turn: Any = 1, sender: Any = COMPRADOR
) -> dict[str, Any]:
    return {"sessionId": SESION, "turn": turn, "type": tipo, "sender": sender}


def task(cuerpo: Any, envelope: Any) -> dict[str, Any]:
    return {
        "id": "t1",
        "artifacts": [
            {
                "artifactId": "a1",
                "extensions": [URI_EXTENSION],
                "metadata": {URI_EXTENSION: envelope},
                "parts": [{"data": cuerpo, "mediaType": MEDIA_ACTO}],
            }
        ],
    }


def validar(t: dict[str, Any], turn: int = 1, sender: str = COMPRADOR) -> Any:
    return validar_acto(t, SESION, turn, sender, TERMINOS)


def fallos(t: dict[str, Any], turn: int = 1, sender: str = COMPRADOR) -> list[Fallo]:
    return validar(t, turn, sender).fallos


# --- Actos válidos ---------------------------------------------------------------------


def test_ac_01_03_propose_valido_sin_fallos() -> None:
    acto = validar(task({"offer": oferta()}, sobre()))
    assert acto.fallos == []
    assert acto.tipo == "PROPOSE"
    assert acto.oferta == oferta()


def test_ac_03_04_counteroffer_valido_en_turno_2() -> None:
    t = task({"offer": oferta()}, sobre("COUNTEROFFER", 2, VENDEDOR))
    acto = validar(t, turn=2, sender=VENDEDOR)
    assert (acto.fallos, acto.tipo) == ([], "COUNTEROFFER")


def test_ac_03_06_accept_valido_sin_campos() -> None:
    acto = validar(task({}, sobre("ACCEPT", 2, VENDEDOR)), turn=2, sender=VENDEDOR)
    assert (acto.fallos, acto.tipo, acto.oferta) == ([], "ACCEPT", None)


@pytest.mark.parametrize("cuerpo", [{}, {"reason": "precio"}])
def test_ac_01_16_withdraw_valido_con_o_sin_reason(cuerpo: dict[str, Any]) -> None:
    acto = validar(task(cuerpo, sobre("WITHDRAW")))
    assert (acto.fallos, acto.tipo, acto.reason) == (
        [],
        "WITHDRAW",
        cuerpo.get("reason"),
    )


def test_precio_entero_y_ceros_finales_no_exigen_redondear() -> None:
    assert fallos(task({"offer": oferta(unitPrice=12)}, sobre())) == []
    assert fallos(task({"offer": oferta(unitPrice=leer("12.500"))}, sobre())) == []


def test_un_artifact_ajeno_no_impide_leer_el_acto() -> None:
    t = task({"offer": oferta()}, sobre())
    t["artifacts"].append({"artifactId": "a2", "parts": [{"text": "hola"}]})
    assert fallos(t) == []


# --- Paso 6: Artifact (D-23) -----------------------------------------------------------


def test_sin_artifacts_es_missing_act() -> None:
    assert fallos({"id": "t1"}) == [Fallo("MISSING_ACT", "task")]


def test_part_con_otro_media_type_es_missing_act() -> None:
    t = task({"offer": oferta()}, sobre())
    t["artifacts"][0]["parts"][0]["mediaType"] = "application/json"
    assert fallos(t) == [Fallo("MISSING_ACT", "task")]


def test_dos_artifacts_de_acto_es_multiple_acts() -> None:
    t = task({"offer": oferta()}, sobre())
    t["artifacts"].append(t["artifacts"][0])
    assert fallos(t) == [Fallo("MULTIPLE_ACTS", "task")]


def test_dos_parts_data_es_multiple_acts() -> None:
    t = task({"offer": oferta()}, sobre())
    t["artifacts"][0]["parts"].append({"data": {}, "mediaType": "application/json"})
    assert fallos(t) == [Fallo("MULTIPLE_ACTS", "task")]


@pytest.mark.parametrize(
    "artifacts", [None, "x", [3], [{"parts": "x"}], [{"parts": [3]}]]
)
def test_artifacts_sin_forma_es_missing_act(artifacts: Any) -> None:
    assert fallos({"id": "t1", "artifacts": artifacts}) == [
        Fallo("MISSING_ACT", "task")
    ]


# --- Paso 7: sobre (R-01 a R-05, R-17 en modo estricto) --------------------------------


@pytest.mark.parametrize(
    ("campo", "valor", "esperado"),
    [
        ("sessionId", None, "MISSING_FIELD"),
        ("sessionId", "otra", "STATE_MISMATCH"),
        ("turn", None, "MISSING_FIELD"),
        ("turn", "1", "WRONG_TYPE"),  # R-02
        ("turn", Decimal("1.0"), "WRONG_TYPE"),
        ("turn", True, "WRONG_TYPE"),
        ("turn", 2, "STATE_MISMATCH"),
        ("type", None, "MISSING_FIELD"),  # R-17
        ("type", "propose", "INVALID_FORMAT"),  # R-03
        ("type", " pro-pose ", "INVALID_FORMAT"),
        ("type", "HOLA", "UNKNOWN_VALUE"),  # R-17
        ("type", "TURN_REQUEST", "UNKNOWN_VALUE"),
        ("type", 3, "UNKNOWN_VALUE"),
        ("sender", None, "MISSING_FIELD"),  # R-04
        ("sender", VENDEDOR, "STATE_MISMATCH"),
    ],
)
def test_sobre_no_valido(campo: str, valor: Any, esperado: str) -> None:
    envelope = sobre()
    if valor is None:
        del envelope[campo]
    else:
        envelope[campo] = valor
    assert Fallo(esperado, f"envelope.{campo}") in fallos(
        task({"offer": oferta()}, envelope)
    )


def test_campo_no_definido_en_el_sobre() -> None:
    envelope = {**sobre(), "extra": 1}
    assert fallos(task({"offer": oferta()}, envelope)) == [
        Fallo("UNKNOWN_FIELD", "envelope.extra")
    ]


@pytest.mark.parametrize("envelope", [None, "x"])
def test_sobre_ausente_o_sin_forma(envelope: Any) -> None:
    t = task({"offer": oferta()}, envelope)
    if envelope is None:
        del t["artifacts"][0]["metadata"]
    campos = [f.field for f in fallos(t)]
    assert campos == [f"envelope.{c}" for c in ("sessionId", "turn", "type", "sender")]


def test_ruta_de_un_campo_no_definido_sin_caracteres_que_no_se_pueden_guardar() -> None:
    envelope = {**sobre(), "a\x00\ud800": 1}
    assert fallos(task({"offer": oferta()}, envelope)) == [
        Fallo("UNKNOWN_FIELD", "envelope.a?")
    ]


# --- Pasos 8 y 9: encaje, coherencia y cuerpo (R-05 a R-08, R-13 a R-16) --------------


@pytest.mark.parametrize(
    ("cuerpo", "tipo", "turn", "esperado"),
    [
        (
            {"offer": oferta()},
            "COUNTEROFFER",
            1,
            Fallo("ACT_NOT_ALLOWED", "envelope.type"),
        ),
        ({"offer": oferta()}, "PROPOSE", 2, Fallo("ACT_NOT_ALLOWED", "envelope.type")),
        ({}, "ACCEPT", 1, Fallo("ACT_NOT_ALLOWED", "envelope.type")),  # R-16
        (
            {"reason": "x"},
            "PROPOSE",
            1,
            Fallo("ACT_BODY_MISMATCH", "envelope.type"),
        ),  # R-06
        ({"reason": "x"}, "ACCEPT", 2, Fallo("ACT_BODY_MISMATCH", "envelope.type")),
        ({}, "COUNTEROFFER", 2, Fallo("ACT_BODY_MISMATCH", "body")),  # R-16
        (
            {"offer": oferta()},
            "ACCEPT",
            2,
            Fallo("ACT_BODY_MISMATCH", "body.offer"),
        ),  # R-08, R-14
        (
            {"offer": oferta()},
            "WITHDRAW",
            1,
            Fallo("ACT_BODY_MISMATCH", "body.offer"),
        ),  # R-14
        (
            {"offer": oferta(), "reason": "x"},
            "PROPOSE",
            1,
            Fallo("ACT_BODY_MISMATCH", "body"),
        ),
        ("texto", "PROPOSE", 1, Fallo("ACT_BODY_MISMATCH", "body")),
        ({"reason": 3}, "WITHDRAW", 1, Fallo("WRONG_TYPE", "body.reason")),  # R-15
        (
            {"offer": oferta(), "extra": 1},
            "PROPOSE",
            1,
            Fallo("UNKNOWN_FIELD", "body.extra"),
        ),
        ({"offer": "x"}, "PROPOSE", 1, Fallo("WRONG_TYPE", "body.offer")),
    ],
)
def test_cuerpo_no_valido(cuerpo: Any, tipo: str, turn: int, esperado: Fallo) -> None:
    sender = COMPRADOR if turn % 2 else VENDEDOR
    assert fallos(task(cuerpo, sobre(tipo, turn, sender)), turn, sender) == [esperado]


@pytest.mark.parametrize(
    ("campo", "valor", "esperado"),
    [
        ("productId", None, "MISSING_FIELD"),  # R-09
        ("unit", "g", "STATE_MISMATCH"),
        ("currency", "eur", "INVALID_FORMAT"),
        ("currency", "USD", "STATE_MISMATCH"),
        ("quantity", "omitir", "MISSING_FIELD"),  # R-13
        ("quantity", Decimal("10.0"), "WRONG_TYPE"),  # R-11
        ("quantity", "10", "WRONG_TYPE"),
        ("quantity", True, "WRONG_TYPE"),
        ("quantity", 0, "OUT_OF_RANGE"),  # R-13
        ("quantity", Decimal("10.5"), "PRECISION_EXCEEDED"),
        ("unitPrice", "omitir", "MISSING_FIELD"),
        ("unitPrice", "12,50 €", "INVALID_FORMAT"),  # R-10
        ("unitPrice", "barato", "WRONG_TYPE"),
        ("unitPrice", 0, "OUT_OF_RANGE"),
        ("unitPrice", Decimal("-1.5"), "OUT_OF_RANGE"),
        ("unitPrice", Decimal("12.505"), "PRECISION_EXCEEDED"),
        ("unitPrice", leer("12.50000000000000001"), "PRECISION_EXCEEDED"),  # D-37
        ("unitPrice", leer("1E+5000"), "OUT_OF_RANGE"),
        ("deliveryDays", "30", "WRONG_TYPE"),  # R-12
        ("paymentDays", -1, "OUT_OF_RANGE"),
        ("paymentDays", "omitir", "MISSING_FIELD"),
        ("total", 125, "UNKNOWN_FIELD"),  # R-05
    ],
)
def test_oferta_no_valida(campo: str, valor: Any, esperado: str) -> None:
    o = oferta(**{campo: None if valor == "omitir" else valor})
    assert fallos(task({"offer": o}, sobre())) == [
        Fallo(esperado, f"body.offer.{campo}")
    ]


def test_d_61_fallos_en_orden_sobre_cuerpo_coherencia() -> None:
    """Aunque el encaje se evalúa antes, la coherencia se clasifica la última (D-72)."""
    t = task({"offer": oferta(quantity=0)}, sobre("COUNTEROFFER", sender=VENDEDOR))
    assert fallos(t) == [
        Fallo("STATE_MISMATCH", "envelope.sender"),
        Fallo("OUT_OF_RANGE", "body.offer.quantity"),
        Fallo("ACT_NOT_ALLOWED", "envelope.type"),
    ]

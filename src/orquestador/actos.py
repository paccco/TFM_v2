"""Validación estricta de un acto: pasos 6 a 9 de CU-01 y CU-03 (D-23, D-26, D-34, D-72).

Solo detecta. En v0.1.0 toda sesión es `STRICT` (D-11), así que ningún fallo de R-01 a R-17
se corrige. La Task llega como JSON con los números exactos: los enteros como `int` y el
resto como `Decimal` (D-37, D-130). Es una función pura, sin base de datos ni red.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from orquestador.peticiones import URI_EXTENSION, Fallo

MEDIA_ACTO = "application/vnd.tfm.negociacion.acto+json"  # D-19
ACTOS = ("PROPOSE", "COUNTEROFFER", "ACCEPT", "WITHDRAW")  # D-32
CON_OFERTA = ("PROPOSE", "COUNTEROFFER")
CAMPOS_SOBRE = ("sessionId", "turn", "type", "sender")
CAMPOS_CUERPO = ("offer", "reason")
TERMINOS_FIJOS = ("productId", "unit", "currency")  # D-36
DIAS = ("deliveryDays", "paymentDays")
CAMPOS_OFERTA = (*TERMINOS_FIJOS, "quantity", "unitPrice", *DIAS)
# R-10: precio en forma textual que se podría normalizar.
PRECIO_TEXTUAL = re.compile(r"[\s€$£]*\d+(?:[.,]\d+)?[\s€$£]*")
# Máximo de cifras enteras de `numeric` en PostgreSQL: un precio mayor no se puede guardar.
MAX_CIFRAS_PRECIO = 131072


@dataclass(frozen=True)
class Acto:
    """Resultado de validar. `tipo` solo lleva valor si el acto se acepta (sin fallos)."""

    tipo: str | None
    oferta: dict[str, Any] | None = None
    reason: str | None = None
    fallos: list[Fallo] = field(default_factory=list)


def texto_seguro(texto: str) -> str:
    """Quita lo que PostgreSQL no puede guardar en texto: NUL y sustitutos sueltos."""
    return texto.encode("utf-8", "replace").decode().replace("\x00", "")


def validar_acto(
    task: dict[str, Any],
    session_id: str,
    turn: int,
    sender: str,
    terminos: dict[str, str],
) -> Acto:
    """Fallos en el orden de D-61: Task, sobre, cuerpo y coherencia."""
    parte = _parte_de_acto(task)
    if isinstance(parte, Fallo):
        return Acto(None, fallos=[parte])
    envelope, cuerpo = parte
    fallos, tipo = _validar_sobre(envelope, session_id, turn, sender)
    if tipo is None:  # R-17: sin tipo no hay esquema con el que comparar el cuerpo.
        return Acto(None, fallos=fallos)
    if not isinstance(cuerpo, dict):
        return Acto(None, fallos=[*fallos, Fallo("ACT_BODY_MISMATCH", "body")])

    coherencia = _coherencia(cuerpo, tipo, turn)
    for campo in cuerpo:
        if campo not in CAMPOS_CUERPO:
            fallos.append(Fallo("UNKNOWN_FIELD", f"body.{texto_seguro(campo)}"))  # R-05
    reason = cuerpo.get("reason")
    if "reason" in cuerpo and not isinstance(reason, str):
        fallos.append(Fallo("WRONG_TYPE", "body.reason"))  # R-15
    oferta = cuerpo.get("offer") if tipo in CON_OFERTA else None
    if oferta is not None:
        fallos += _validar_oferta(oferta, terminos)

    fallos += coherencia
    if fallos:
        return Acto(None, fallos=fallos)
    return Acto(tipo, oferta, reason)


def _parte_de_acto(task: dict[str, Any]) -> tuple[Any, Any] | Fallo:
    """Paso 6 (D-23): exactamente un Artifact de acto, con exactamente una Part `data`."""
    artifacts = task.get("artifacts")
    de_acto: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for artefacto in artifacts if isinstance(artifacts, list) else []:
        partes = artefacto.get("parts") if isinstance(artefacto, dict) else None
        datos = [p for p in partes or [] if isinstance(p, dict) and "data" in p]
        if any(p.get("mediaType") == MEDIA_ACTO for p in datos):
            de_acto.append((artefacto, datos))
    if not de_acto:
        return Fallo("MISSING_ACT", "task")
    if len(de_acto) > 1 or len(de_acto[0][1]) > 1:
        return Fallo("MULTIPLE_ACTS", "task")
    artefacto, [parte] = de_acto[0]
    metadatos = artefacto.get("metadata")
    envelope = metadatos.get(URI_EXTENSION) if isinstance(metadatos, dict) else None
    return envelope, parte["data"]


def _validar_sobre(
    envelope: Any, session_id: str, turn: int, sender: str
) -> tuple[list[Fallo], str | None]:
    """Paso 7: R-01 a R-05 y R-17. Devuelve también el tipo, normalizado si se puede."""
    sobre = envelope if isinstance(envelope, dict) else {}
    fallos: list[Fallo] = []

    def comprobar(campo: str, esperado: Any) -> None:
        if campo not in sobre:
            fallos.append(Fallo("MISSING_FIELD", f"envelope.{campo}"))
        elif campo == "turn" and type(sobre[campo]) is not int:
            fallos.append(Fallo("WRONG_TYPE", "envelope.turn"))  # R-02
        elif sobre[campo] != esperado:
            fallos.append(Fallo("STATE_MISMATCH", f"envelope.{campo}"))

    comprobar("sessionId", session_id)  # R-01
    comprobar("turn", turn)
    tipo = None
    valor = sobre.get("type")
    if "type" not in sobre:
        fallos.append(Fallo("MISSING_FIELD", "envelope.type"))  # R-17
    else:
        normalizado = (
            re.sub(r"[\s-]", "", valor).upper() if isinstance(valor, str) else None
        )
        if normalizado not in ACTOS:
            fallos.append(Fallo("UNKNOWN_VALUE", "envelope.type"))  # R-17
        else:
            tipo = normalizado
            if normalizado != valor:
                fallos.append(Fallo("INVALID_FORMAT", "envelope.type"))  # R-03
    comprobar("sender", sender)  # R-04
    for campo in sobre:
        if campo not in CAMPOS_SOBRE:
            fallos.append(Fallo("UNKNOWN_FIELD", f"envelope.{texto_seguro(campo)}"))
    return fallos, tipo


def _coherencia(cuerpo: dict[str, Any], tipo: str, turn: int) -> list[Fallo]:
    """Paso 8 (D-72): encaje del cuerpo tal como llega con el tipo del sobre."""
    con_oferta, con_reason = "offer" in cuerpo, "reason" in cuerpo
    if con_oferta and con_reason:
        return [Fallo("ACT_BODY_MISMATCH", "body")]  # R-16: ningún acto lleva los dos
    if tipo in CON_OFERTA:
        if con_reason:
            return [Fallo("ACT_BODY_MISMATCH", "envelope.type")]  # R-06
        if not con_oferta:
            return [Fallo("ACT_BODY_MISMATCH", "body")]  # R-16: encaje múltiple
        if tipo != ("PROPOSE" if turn == 1 else "COUNTEROFFER"):
            return [Fallo("ACT_NOT_ALLOWED", "envelope.type")]  # R-07
        return []
    if con_oferta:
        return [Fallo("ACT_BODY_MISMATCH", "body.offer")]  # R-08, R-14
    if tipo == "ACCEPT" and con_reason:
        return [Fallo("ACT_BODY_MISMATCH", "envelope.type")]  # R-06
    if tipo == "ACCEPT" and turn == 1:
        return [Fallo("ACT_NOT_ALLOWED", "envelope.type")]  # R-16
    return []


def _validar_oferta(oferta: Any, terminos: dict[str, str]) -> list[Fallo]:
    """Paso 9: tabla «Oferta» de `protocolo.md` (D-39, R-05, R-09 a R-13)."""
    if not isinstance(oferta, dict):
        return [Fallo("WRONG_TYPE", "body.offer")]
    fallos: list[Fallo] = []

    def fallo(code: str, campo: str) -> None:
        fallos.append(Fallo(code, f"body.offer.{texto_seguro(campo)}"))

    for campo in CAMPOS_OFERTA:
        if campo not in oferta:
            fallo("MISSING_FIELD", campo)  # R-09, R-13
            continue
        valor = oferta[campo]
        if campo in TERMINOS_FIJOS:
            if valor == terminos[campo]:
                continue
            en_mayusculas = isinstance(valor, str) and valor.upper() == terminos[campo]
            fallo(
                "INVALID_FORMAT"
                if campo == "currency" and en_mayusculas
                else "STATE_MISMATCH",
                campo,
            )
        elif campo == "unitPrice":
            codigo = _fallo_precio(valor)
            if codigo:
                fallo(codigo, campo)
        elif (
            campo == "quantity"
            and isinstance(valor, Decimal)
            and valor != valor.to_integral_value()
        ):
            fallo("PRECISION_EXCEEDED", campo)  # R-13: cantidad no entera
        elif type(valor) is not int:
            fallo("WRONG_TYPE", campo)  # R-11, R-12
        elif valor < (1 if campo == "quantity" else 0):
            fallo("OUT_OF_RANGE", campo)  # R-13
    for campo in oferta:
        if campo not in CAMPOS_OFERTA:
            fallo("UNKNOWN_FIELD", campo)  # R-05
    return fallos


def _fallo_precio(valor: Any) -> str | None:
    """D-37: decimal exacto, > 0 y con 2 decimales como máximo."""
    if isinstance(valor, str):
        return (
            "INVALID_FORMAT" if PRECIO_TEXTUAL.fullmatch(valor) else "WRONG_TYPE"
        )  # R-10
    if type(valor) not in (int, Decimal):
        return "WRONG_TYPE"
    exacto = Decimal(valor)
    if exacto <= 0 or exacto.adjusted() >= MAX_CIFRAS_PRECIO:
        return "OUT_OF_RANGE"  # R-13
    _, digitos, exponente = exacto.as_tuple()
    cifras = "".join(map(str, digitos))
    ceros_finales = len(cifras) - len(cifras.rstrip("0"))
    if int(exponente) + ceros_finales < -2:
        return "PRECISION_EXCEEDED"  # R-13: exigiría redondear
    return None

"""Validación estricta de un acto: pasos 6 a 9 de CU-01 y CU-03."""

from dataclasses import dataclass, field
from typing import Any

from orquestador.peticiones import Fallo

MEDIA_ACTO = "application/vnd.tfm.negociacion.acto+json"  # D-19


@dataclass(frozen=True)
class Acto:
    tipo: str | None
    oferta: dict[str, Any] | None = None
    reason: str | None = None
    fallos: list[Fallo] = field(default_factory=list)


def validar_acto(
    task: dict[str, Any],
    session_id: str,
    turn: int,
    sender: str,
    terminos: dict[str, str],
) -> Acto:
    raise NotImplementedError

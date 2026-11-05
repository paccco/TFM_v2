"""Validación de las peticiones del comprador (esqueleto en rojo)."""

from dataclasses import dataclass, field
from typing import Any

from a2a.types.a2a_pb2 import Message

URI_EXTENSION = "urn:tfm:negociacion:v1"
MEDIA_PETICION = "application/vnd.tfm.negociacion.peticion+json"

Origen = tuple[str, str, int | None]


@dataclass(frozen=True)
class Fallo:
    code: str
    field: str


@dataclass(frozen=True)
class SesionPedida:
    item_id: str
    config: dict[str, Any]


@dataclass(frozen=True)
class PeticionValidada:
    tipo: str | None
    sender: str | None
    fallos: list[Fallo] = field(default_factory=list)
    sesiones: list[SesionPedida] = field(default_factory=list)


def origen(url: str) -> Origen | None:
    return None


def validar_peticion(
    mensaje: Message,
    extensiones: set[str],
    identidad: str,
    origenes: frozenset[Origen | None],
) -> PeticionValidada:
    raise NotImplementedError

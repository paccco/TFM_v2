"""Esqueleto en rojo."""

from starlette.applications import Starlette

from orquestador.peticiones import Origen
from orquestador.rondas import Entorno


def crear_app(entorno: Entorno, tokens: dict[str, str], url_publica: str) -> Starlette:
    raise NotImplementedError


def leer_tokens(texto: str) -> dict[str, str]:
    raise NotImplementedError


def leer_origenes(texto: str) -> frozenset[Origen]:
    raise NotImplementedError

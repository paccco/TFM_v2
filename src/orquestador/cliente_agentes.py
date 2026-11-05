"""Cliente JSON-RPC propio hacia los agentes de las partes (D-130).

Los números viajan sin pasar por coma flotante: se leen como `Decimal` y se escriben tal cual
(D-37). Métodos y cabeceras de A2A 1.0 (D-17), comprobados contra `a2a-sdk` 1.3.0.
"""

import json
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx

from orquestador.peticiones import URI_EXTENSION

TASK_NOT_FOUND = -32001  # `TaskNotFoundError` de A2A (D-68)
CABECERAS = {
    "Content-Type": "application/json",
    "A2A-Extensions": URI_EXTENSION,
    "A2A-Version": "1.0",  # sin ella, el servidor del SDK supone la 0.3
}


class ErrorTransporte(Exception):
    """Fallo de red, de HTTP o de JSON en la respuesta: `AGENT_UNREACHABLE`."""


class ErrorA2A(Exception):
    """El agente respondió con un error JSON-RPC (D-71)."""

    def __init__(self, code: Any) -> None:
        super().__init__(code)
        self.code = code


def a_json(valor: Any) -> str:
    """JSON con los `Decimal` escritos con todas sus cifras (D-37)."""
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, dict):
        pares = (f"{json.dumps(k)}:{a_json(v)}" for k, v in valor.items())
        return "{" + ",".join(pares) + "}"
    if isinstance(valor, list):
        return "[" + ",".join(a_json(v) for v in valor) + "]"
    return json.dumps(valor)


def _sin_constantes(nombre: str) -> Any:
    raise ValueError(f"{nombre} no es JSON")


def leer_json(texto: str | bytes) -> Any:
    """JSON con los decimales como `Decimal`; `NaN` e `Infinity` no se admiten."""
    return json.loads(texto, parse_float=Decimal, parse_constant=_sin_constantes)


async def llamar(
    cliente: httpx.AsyncClient, url: str, metodo: str, params: dict[str, Any]
) -> Any:
    """Devuelve el `result` de la llamada. El tiempo máximo lo pone quien llama (D-52)."""
    peticion = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": metodo,
        "params": params,
    }
    try:
        respuesta = await cliente.post(url, content=a_json(peticion), headers=CABECERAS)
        respuesta.raise_for_status()
        datos = leer_json(respuesta.content)
    except (httpx.HTTPError, ValueError, RecursionError) as error:
        raise ErrorTransporte from error
    if not isinstance(datos, dict):
        raise ErrorTransporte
    if "error" in datos:
        error = datos["error"]
        raise ErrorA2A(error.get("code") if isinstance(error, dict) else None)
    return datos.get("result")

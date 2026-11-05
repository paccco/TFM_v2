"""Arranque del orquestador: `uv run python -m orquestador`. Configuración en `.env.example`."""

import asyncio
import os
from uuid import uuid4

import uvicorn

from orquestador.almacen import crear_esquema
from orquestador.rondas import Entorno
from orquestador.servidor import crear_app, leer_origenes, leer_tokens


def main() -> None:
    dsn = os.environ["DATABASE_URL"]
    asyncio.run(crear_esquema(dsn))
    entorno = Entorno(
        dsn,
        instancia=str(uuid4()),
        origenes=leer_origenes(os.environ.get("ORQUESTADOR_ORIGENES_AGENTES", "")),
    )
    tokens = leer_tokens(os.environ.get("ORQUESTADOR_TOKENS", ""))
    app = crear_app(entorno, tokens, os.environ["ORQUESTADOR_URL"])
    # El token viaja en claro sin TLS: por defecto solo se escucha en local (D-128).
    uvicorn.run(
        app,
        host=os.environ.get("ORQUESTADOR_HOST", "127.0.0.1"),
        port=int(os.environ.get("ORQUESTADOR_PUERTO", "8000")),
    )


if __name__ == "__main__":
    main()

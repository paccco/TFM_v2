"""Piezas comunes: PostgreSQL real en un esquema propio y un servidor HTTP real de AgentCards."""

import asyncio
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import psycopg
import pytest
import uvicorn
from a2a.types.a2a_pb2 import AgentCapabilities, AgentCard, AgentExtension
from google.protobuf.json_format import MessageToDict
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Route

from orquestador.almacen import crear_esquema
from orquestador.peticiones import URI_EXTENSION

# Credenciales solo de desarrollo, las de docker-compose.yml.
DSN_BASE = os.environ.get("DATABASE_URL", "postgresql://tfm:tfm@127.0.0.1:55432/tfm")
ESQUEMA_PRUEBAS = "pruebas_orquestador"


def tarjeta(uri: str = URI_EXTENSION, requerida: bool = True) -> dict[str, Any]:
    return MessageToDict(
        AgentCard(
            name="agente de prueba",
            capabilities=AgentCapabilities(
                extensions=[AgentExtension(uri=uri, required=requerida)]
            ),
        )
    )


@dataclass
class ServidorHttp:
    """Servidor real: las peticiones recibidas quedan en `visitas`."""

    url: str
    visitas: list[str] = field(default_factory=list)


def _app_de_tarjetas(servidor: ServidorHttp) -> Starlette:
    async def responder(request: Request) -> Response:
        ruta = request.url.path
        servidor.visitas.append(f"{request.method} {ruta}")
        if ruta == "/opcional.json":
            return JSONResponse(tarjeta(requerida=False))
        if ruta == "/sin.json":
            return JSONResponse(tarjeta(uri="urn:otra"))
        if ruta == "/lenta.json":
            await asyncio.sleep(3)
            return JSONResponse(tarjeta())
        if ruta == "/basura.json":
            return PlainTextResponse("esto no es una AgentCard")
        if ruta == "/error.json":
            return PlainTextResponse("fallo", status_code=500)
        if ruta == "/redirige.json":
            return RedirectResponse("/con.json", status_code=302)
        return JSONResponse(tarjeta())

    return Starlette(routes=[Route("/{ruta:path}", responder, methods=["GET", "POST"])])


@contextmanager
def levantar(app: Starlette) -> Iterator[str]:
    """Sirve la aplicación con uvicorn en un hilo y devuelve su URL."""
    uv = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, log_level="warning", lifespan="off"
        )
    )
    hilo = threading.Thread(target=uv.run, daemon=True)
    hilo.start()
    while not uv.started:
        time.sleep(0.01)
    puerto = uv.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{puerto}"
    finally:
        uv.should_exit = True
        hilo.join(timeout=5)


@pytest.fixture(scope="session")
def _servidor_de_tarjetas() -> Iterator[ServidorHttp]:
    servidor = ServidorHttp(url="")
    with levantar(_app_de_tarjetas(servidor)) as url:
        servidor.url = url
        yield servidor


@pytest.fixture
def agentes(_servidor_de_tarjetas: ServidorHttp) -> ServidorHttp:
    _servidor_de_tarjetas.visitas.clear()
    return _servidor_de_tarjetas


@pytest.fixture
def dsn() -> Iterator[str]:
    """Esquema vacío por test: no toca los datos de desarrollo."""
    with psycopg.connect(DSN_BASE, autocommit=True) as c:
        c.execute(f"DROP SCHEMA IF EXISTS {ESQUEMA_PRUEBAS} CASCADE")
        c.execute(f"CREATE SCHEMA {ESQUEMA_PRUEBAS}")
    con_esquema = f"{DSN_BASE}?options=-csearch_path%3D{ESQUEMA_PRUEBAS}"
    asyncio.run(crear_esquema(con_esquema))
    yield con_esquema

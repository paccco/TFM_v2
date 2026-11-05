"""El orquestador como servidor A2A del coordinador (D-87).

Usa las rutas JSON-RPC y de AgentCard del SDK con un `RequestHandler` propio, que escribe las
Tasks en la transacción de las sesiones (D-97, D-127). Delante va la autenticación (D-128).
"""

import asyncio
import hmac
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import RequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.types.a2a_pb2 import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
    GetTaskRequest,
    HTTPAuthSecurityScheme,
    Message,
    SecurityRequirement,
    SecurityScheme,
    SendMessageRequest,
    StringList,
    Task,
)
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    PROTOCOL_VERSION_CURRENT,
    TransportProtocol,
)
from a2a.utils.errors import UnsupportedOperationError
from starlette.applications import Starlette
from starlette.authentication import SimpleUser
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from orquestador.almacen import leer_task
from orquestador.peticiones import (
    MEDIA_PETICION,
    MEDIA_RESULTADO,
    URI_EXTENSION,
    Origen,
    origen,
)
from orquestador.rondas import Entorno, comprobar_sesion, recibir_peticion

logger = logging.getLogger(__name__)

ESQUEMA_BEARER = "bearer"


class Manejador(RequestHandler):
    """D-127: `SendMessage` y `GetTask`; los demás métodos no se admiten."""

    def __init__(self, entorno: Entorno) -> None:
        self._entorno = entorno
        self._en_curso: set[asyncio.Task[None]] = set()

    async def on_message_send(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> Task | Message:
        """Pasos 1 a 7 de CU-04. La comprobación sigue aunque el coordinador se desconecte."""
        identidad = context.user.user_name
        recepcion = await recibir_peticion(
            self._entorno, params.message, context.requested_extensions, identidad
        )
        if not recepcion.sesiones:
            return recepcion.task
        tarea = asyncio.create_task(self._comprobar(recepcion.sesiones))
        self._en_curso.add(tarea)
        tarea.add_done_callback(self._en_curso.discard)
        if params.configuration.return_immediately:
            return recepcion.task
        await asyncio.shield(tarea)
        guardada = await leer_task(self._entorno.dsn, recepcion.task.id, identidad)
        return guardada or recepcion.task

    async def _comprobar(self, sesiones: list[str]) -> None:
        """D-99: sesiones en paralelo. Si algo falla, siguen en `CREATED` para otra instancia."""
        try:
            await asyncio.gather(
                *[comprobar_sesion(self._entorno, s) for s in sesiones]
            )
        except Exception:
            logger.exception("Fallo al comprobar las AgentCards de una ronda")

    async def on_get_task(
        self, params: GetTaskRequest, context: ServerCallContext
    ) -> Task | None:
        """D-97, D-128: la Task guardada, solo para la identidad que la creó."""
        return await leer_task(self._entorno.dsn, params.id, context.user.user_name)

    async def on_message_send_stream(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> AsyncGenerator[Any]:
        raise UnsupportedOperationError
        yield

    async def on_subscribe_to_task(
        self, params: Any, context: ServerCallContext
    ) -> AsyncGenerator[Any]:
        raise UnsupportedOperationError
        yield

    async def on_list_tasks(self, params: Any, context: ServerCallContext) -> Any:
        raise UnsupportedOperationError

    async def on_cancel_task(self, params: Any, context: ServerCallContext) -> Any:
        raise UnsupportedOperationError

    async def on_create_task_push_notification_config(
        self, params: Any, context: ServerCallContext
    ) -> Any:
        raise UnsupportedOperationError

    async def on_get_task_push_notification_config(
        self, params: Any, context: ServerCallContext
    ) -> Any:
        raise UnsupportedOperationError

    async def on_list_task_push_notification_configs(
        self, params: Any, context: ServerCallContext
    ) -> Any:
        raise UnsupportedOperationError

    async def on_delete_task_push_notification_config(
        self, params: Any, context: ServerCallContext
    ) -> None:
        raise UnsupportedOperationError

    async def on_get_extended_agent_card(
        self, params: Any, context: ServerCallContext
    ) -> AgentCard:
        raise UnsupportedOperationError


class Autenticacion(BaseHTTPMiddleware):
    """D-128: todo salvo la AgentCard exige un bearer válido; si no, 401 sin tocar nada."""

    def __init__(self, app: ASGIApp, tokens: dict[str, str]) -> None:
        super().__init__(app)
        self._tokens = {t.encode(): party for t, party in tokens.items()}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == AGENT_CARD_WELL_KNOWN_PATH:
            return await call_next(request)
        identidad = self._identidad(request.headers.get("Authorization", ""))
        if identidad is None:
            return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
        # El SDK lo convierte en `context.user`.
        request.scope["user"] = SimpleUser(identidad)
        return await call_next(request)

    def _identidad(self, cabecera: str) -> str | None:
        esquema, _, token = cabecera.partition(" ")
        if esquema.lower() != ESQUEMA_BEARER or not token:
            return None
        recibido = token.encode()
        identidad = None
        # Se comparan todos y en tiempo constante, para no filtrar nada por el tiempo.
        for valido, party in self._tokens.items():
            if hmac.compare_digest(recibido, valido):
                identidad = party
        return identidad


def crear_tarjeta(url_publica: str) -> AgentCard:
    """AgentCard del orquestador: extensión obligatoria (D-87) y esquema bearer (D-128)."""
    return AgentCard(
        name="Orquestador de negociación",
        description="Media en negociaciones de compraventa entre agentes A2A.",
        version="0.1.0",
        supported_interfaces=[
            AgentInterface(
                url=url_publica,
                protocol_binding=TransportProtocol.JSONRPC,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        capabilities=AgentCapabilities(
            extensions=[AgentExtension(uri=URI_EXTENSION, required=True)]
        ),
        default_input_modes=[MEDIA_PETICION],
        default_output_modes=[MEDIA_RESULTADO],
        skills=[
            AgentSkill(
                id="abrir-ronda",
                name="Abrir una ronda",
                description="Acepta OPEN_ROUND y arranca sus sesiones.",
                tags=["negociacion"],
            )
        ],
        security_schemes={
            ESQUEMA_BEARER: SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(scheme="Bearer")
            )
        },
        security_requirements=[
            SecurityRequirement(schemes={ESQUEMA_BEARER: StringList()})
        ],
    )


def crear_app(entorno: Entorno, tokens: dict[str, str], url_publica: str) -> Starlette:
    """Aplicación ASGI. `tokens` relaciona cada token con su `partyId` (D-128)."""
    return Starlette(
        routes=[
            *create_agent_card_routes(crear_tarjeta(url_publica)),
            *create_jsonrpc_routes(Manejador(entorno), rpc_url="/"),
        ],
        middleware=[Middleware(Autenticacion, tokens=tokens)],
    )


def leer_tokens(texto: str) -> dict[str, str]:
    """`partyId=token` separados por comas (D-128). Vacío: nadie se autentica."""
    tokens: dict[str, str] = {}
    for entrada in filter(None, (e.strip() for e in texto.split(","))):
        party, _, token = entrada.partition("=")
        if not party or not token:
            raise ValueError("ORQUESTADOR_TOKENS: cada entrada es partyId=token")
        tokens[token] = party
    return tokens


def leer_origenes(texto: str) -> frozenset[Origen]:
    """Orígenes separados por comas (D-129). Vacío: ninguno permitido."""
    origenes: set[Origen] = set()
    for entrada in filter(None, (e.strip() for e in texto.split(","))):
        leido = origen(entrada)
        if leido is None or not leido[0] or not leido[1]:
            raise ValueError(
                f"ORQUESTADOR_ORIGENES_AGENTES: origen no válido: {entrada}"
            )
        origenes.add(leido)
    return frozenset(origenes)

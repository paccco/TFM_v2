"""Validación de las peticiones del comprador: forma, sobre, cuerpo y configuración.

Implementa los pasos 1 y 3 a 5 de CU-04 (D-89 a D-93, D-101 a D-103, D-128, D-129).
Es una función pura: no consulta la base de datos ni la red. Lo que necesita de fuera
(identidad autenticada y orígenes permitidos) llega como parámetro.
"""

from dataclasses import dataclass, field
from typing import Any

import httpx
from a2a.types.a2a_pb2 import Message
from google.protobuf.json_format import MessageToDict

URI_EXTENSION = "urn:tfm:negociacion:v1"  # D-27
MEDIA_PETICION = "application/vnd.tfm.negociacion.peticion+json"  # D-92
MEDIA_RESULTADO = "application/vnd.tfm.negociacion.resultado+json"  # D-92

OPEN_ROUND = "OPEN_ROUND"
TIPOS_PETICION = {OPEN_ROUND, "RESOLVE_HOLDS"}

# D-91: por campo, valor por defecto y mínimo (`maquina-estados.md` §5).
PARAMETROS_NUMERICOS = {
    "maxRetries": (2, 0),
    "turnTimeoutSeconds": (60, 1),
    "pollIntervalSeconds": (1, 1),
    "maxTurns": (10, 2),
    "holdTimeoutSeconds": (1800, 1),
}
CAMPOS_CONFIG = {
    "fixedTerms",
    "parties",
    "openingPartyId",
    "validationMode",
    *PARAMETROS_NUMERICOS,
}

# D-36: códigos de divisa vigentes de ISO 4217.
ISO_4217 = frozenset(
    """AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD
    BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF DKK DOP DZD
    EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR
    ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD
    MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR
    PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB
    TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAD XAF
    XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG""".split()  # noqa: SIM905
)

Origen = tuple[str, str, int | None]


@dataclass(frozen=True)
class Fallo:
    """Un fallo de una petición: código del catálogo y ruta del campo (D-50, D-89)."""

    code: str
    field: str


@dataclass(frozen=True)
class SesionPedida:
    """Una entrada de `sessions`, con la configuración en sus valores efectivos (D-91)."""

    item_id: str
    config: dict[str, Any]


@dataclass(frozen=True)
class PeticionValidada:
    """Resultado de validar. `tipo` y `sender` solo llevan valor si se pudieron leer (D-103)."""

    tipo: str | None
    sender: str | None
    fallos: list[Fallo] = field(default_factory=list)
    sesiones: list[SesionPedida] = field(default_factory=list)


def origen(url: str) -> Origen | None:
    """Esquema, host y puerto de una URL, o None si no se puede interpretar (D-129).

    Usa el mismo intérprete que hará la petición, para que la comprobación y el GET no
    puedan discrepar sobre cuál es el host.
    """
    try:
        u = httpx.URL(url)
    except httpx.InvalidURL:
        return None
    # httpx solo omite el puerto por defecto si el esquema llega en minúsculas.
    return (u.scheme, u.host, u.port or {"http": 80, "https": 443}.get(u.scheme))


def validar_peticion(
    mensaje: Message,
    extensiones: set[str],
    identidad: str,
    origenes: frozenset[Origen],
) -> PeticionValidada:
    """Valida un Message dirigido al orquestador y recoge todos sus fallos (D-101)."""
    metadatos = MessageToDict(mensaje.metadata)
    sobre = metadatos.get(URI_EXTENSION)
    tipo: str | None = None
    sender: str | None = None
    if isinstance(sobre, dict):
        if isinstance(sobre.get("type"), str) and sobre["type"] in TIPOS_PETICION:
            tipo = sobre["type"]
        if isinstance(sobre.get("sender"), str):
            sender = sobre["sender"]

    if not _tiene_forma_de_peticion(mensaje, extensiones, sobre):
        return PeticionValidada(tipo, sender, [Fallo("INVALID_MESSAGE", "message")])

    fallos: set[Fallo] = set()
    _validar_sobre(sobre, sender, identidad, fallos)
    sesiones: list[SesionPedida] = []
    if tipo == OPEN_ROUND:
        cuerpo = MessageToDict(mensaje.parts[0].data)
        sesiones = _validar_cuerpo(cuerpo, sender, origenes, fallos)
    elif tipo is not None:
        # shortcut: RESOLVE_HOLDS aún no se admite, feature/resolver-acuerdos lo implementa.
        fallos.add(Fallo("UNKNOWN_VALUE", "envelope.type"))
    return PeticionValidada(tipo, sender, sorted(fallos, key=_clave_de_ruta), sesiones)


def _tiene_forma_de_peticion(
    mensaje: Message, extensiones: set[str], sobre: Any
) -> bool:
    """D-103: cabecera, URI en `extensions`, sobre y una sola Part `data` de petición."""
    return (
        URI_EXTENSION in extensiones
        and URI_EXTENSION in mensaje.extensions
        and isinstance(sobre, dict)
        and len(mensaje.parts) == 1
        and mensaje.parts[0].WhichOneof("content") == "data"
        and mensaje.parts[0].media_type == MEDIA_PETICION
    )


def _clave_de_ruta(fallo: Fallo) -> tuple[tuple[int, int, str], ...]:
    """Orden por ruta (D-101), con los índices como números: 2 va antes que 10."""
    return tuple(
        (0, int(parte), "") if parte.isdigit() else (1, 0, parte)
        for parte in fallo.field.split(".")
    )


def _entero(valor: Any) -> int | None:
    """A2A transporta los números como double: 2.0 es 2, y 2.5 o un booleano no son enteros."""
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return None


def _texto(
    objeto: dict[str, Any], campo: str, ruta: str, fallos: set[Fallo]
) -> str | None:
    """Lee un campo de cadena obligatorio; si no lo es, anota el fallo estructural."""
    if campo not in objeto:
        fallos.add(Fallo("MISSING_FIELD", f"{ruta}.{campo}"))
        return None
    if not isinstance(objeto[campo], str):
        fallos.add(Fallo("WRONG_TYPE", f"{ruta}.{campo}"))
        return None
    return objeto[campo]


def _campos_no_definidos(
    objeto: dict[str, Any], permitidos: set[str], ruta: str, fallos: set[Fallo]
) -> None:
    """D-34, D-89: en una petición, un campo no definido la rechaza."""
    for campo in objeto.keys() - permitidos:
        fallos.add(Fallo("UNKNOWN_FIELD", f"{ruta}.{campo}"))


def _validar_sobre(
    sobre: dict[str, Any], sender: str | None, identidad: str, fallos: set[Fallo]
) -> None:
    """D-93: `type` y `sender`, sin `sessionId` ni `turn`. D-128: `sender` es la identidad."""
    _campos_no_definidos(sobre, {"type", "sender"}, "envelope", fallos)
    tipo = _texto(sobre, "type", "envelope", fallos)
    if tipo is not None and tipo not in TIPOS_PETICION:
        fallos.add(Fallo("UNKNOWN_VALUE", "envelope.type"))
    _texto(sobre, "sender", "envelope", fallos)
    if sender is not None and sender != identidad:
        fallos.add(Fallo("NOT_AUTHORIZED", "envelope.sender"))


def _validar_cuerpo(
    cuerpo: Any,
    sender: str | None,
    origenes: frozenset[Origen],
    fallos: set[Fallo],
) -> list[SesionPedida]:
    """Cuerpo de `OPEN_ROUND` (D-88, D-92) y restricciones entre sesiones (D-102)."""
    if not isinstance(cuerpo, dict):
        fallos.add(Fallo("WRONG_TYPE", "body"))
        return []
    _campos_no_definidos(cuerpo, {"requestId", "sessions"}, "body", fallos)
    if "requestId" in cuerpo:
        # Límite de v0.1.0 (roadmap): feature/varias-sesiones implementa la ronda ≥ 2.
        codigo = (
            "UNKNOWN_REQUEST" if isinstance(cuerpo["requestId"], str) else "WRONG_TYPE"
        )
        fallos.add(Fallo(codigo, "body.requestId"))

    if "sessions" not in cuerpo:
        fallos.add(Fallo("MISSING_FIELD", "body.sessions"))
        return []
    entradas = cuerpo["sessions"]
    if not isinstance(entradas, list):
        fallos.add(Fallo("WRONG_TYPE", "body.sessions"))
        return []
    if not entradas:
        fallos.add(Fallo("INVALID_CONFIG", "body.sessions"))
        return []

    sesiones: list[SesionPedida] = []
    items: set[str] = set()
    compradores: list[tuple[str, str]] = []
    for i, entrada in enumerate(entradas):
        ruta = f"body.sessions.{i}"
        if not isinstance(entrada, dict):
            fallos.add(Fallo("WRONG_TYPE", ruta))
            continue
        _campos_no_definidos(entrada, {"itemId", "config"}, ruta, fallos)
        item_id = _texto(entrada, "itemId", ruta, fallos)
        if item_id in items:
            fallos.add(Fallo("INVALID_CONFIG", f"{ruta}.itemId"))
        elif item_id is not None:
            items.add(item_id)
        if "config" not in entrada:
            fallos.add(Fallo("MISSING_FIELD", f"{ruta}.config"))
            continue
        efectiva = _validar_config(
            entrada["config"], f"{ruta}.config", origenes, compradores, fallos
        )
        if item_id is not None and efectiva is not None:
            sesiones.append(SesionPedida(item_id, efectiva))

    if compradores:
        primero = compradores[0][1]
        distintos = [ruta for ruta, party in compradores if party != primero]
        for ruta in distintos:
            fallos.add(Fallo("INVALID_CONFIG", ruta))
        if not distintos and sender is not None and primero != sender:
            fallos.add(Fallo("NOT_AUTHORIZED", "envelope.sender"))  # D-102
    return sesiones


def _validar_config(
    config: Any,
    ruta: str,
    origenes: frozenset[Origen],
    compradores: list[tuple[str, str]],
    fallos: set[Fallo],
) -> dict[str, Any] | None:
    """Configuración de una sesión (`configuracion-sesion.md`, D-90, D-91).

    Devuelve los valores efectivos y añade a `compradores` la ruta y el `partyId` del `BUYER`.
    """
    if not isinstance(config, dict):
        fallos.add(Fallo("WRONG_TYPE", ruta))
        return None
    _campos_no_definidos(config, CAMPOS_CONFIG, ruta, fallos)
    _validar_terminos(config, ruta, fallos)
    ids = _validar_partes(config, ruta, origenes, compradores, fallos)

    apertura = _texto(config, "openingPartyId", ruta, fallos)
    if apertura is not None and ids is not None and apertura not in ids:
        fallos.add(Fallo("INVALID_CONFIG", f"{ruta}.openingPartyId"))

    modo = _texto(config, "validationMode", ruta, fallos)
    if modo == "TOLERANT":
        # Límite de v0.1.0 (roadmap): feature/autocorreccion lo levanta.
        fallos.add(Fallo("INVALID_CONFIG", f"{ruta}.validationMode"))
    elif modo is not None and modo != "STRICT":
        fallos.add(Fallo("UNKNOWN_VALUE", f"{ruta}.validationMode"))

    efectiva = {
        k: config[k] for k in CAMPOS_CONFIG - PARAMETROS_NUMERICOS.keys() if k in config
    }
    for campo, (defecto, minimo) in PARAMETROS_NUMERICOS.items():
        if campo not in config:
            efectiva[campo] = defecto
            continue
        numero = _entero(config[campo])
        if numero is None:
            fallos.add(Fallo("WRONG_TYPE", f"{ruta}.{campo}"))
        elif numero < minimo:
            fallos.add(Fallo("INVALID_CONFIG", f"{ruta}.{campo}"))
        else:
            efectiva[campo] = numero

    # D-59, D-91: sobre los valores efectivos, solo si los dos son válidos.
    sondeo = efectiva.get("pollIntervalSeconds")
    turno = efectiva.get("turnTimeoutSeconds")
    if sondeo is not None and turno is not None and sondeo >= turno:
        fallos.add(Fallo("INVALID_CONFIG", f"{ruta}.pollIntervalSeconds"))
    if efectiva.get("maxRetries", 0) != 0:
        # Límite de v0.1.0 (roadmap): feature/reintentos-aborto lo levanta.
        fallos.add(Fallo("INVALID_CONFIG", f"{ruta}.maxRetries"))
    return efectiva


def _validar_terminos(config: dict[str, Any], ruta: str, fallos: set[Fallo]) -> None:
    """D-36, D-90: `fixedTerms`, con `productId` y `unit` no vacíos y divisa ISO 4217."""
    if "fixedTerms" not in config:
        fallos.add(Fallo("MISSING_FIELD", f"{ruta}.fixedTerms"))
        return
    terminos = config["fixedTerms"]
    ruta_terminos = f"{ruta}.fixedTerms"
    if not isinstance(terminos, dict):
        fallos.add(Fallo("WRONG_TYPE", ruta_terminos))
        return
    _campos_no_definidos(
        terminos, {"productId", "unit", "currency"}, ruta_terminos, fallos
    )
    for campo in ("productId", "unit"):
        if _texto(terminos, campo, ruta_terminos, fallos) == "":
            fallos.add(Fallo("INVALID_CONFIG", f"{ruta_terminos}.{campo}"))
    divisa = _texto(terminos, "currency", ruta_terminos, fallos)
    if divisa is not None and divisa not in ISO_4217:
        fallos.add(Fallo("INVALID_CONFIG", f"{ruta_terminos}.currency"))


def _validar_partes(
    config: dict[str, Any],
    ruta: str,
    origenes: frozenset[Origen],
    compradores: list[tuple[str, str]],
    fallos: set[Fallo],
) -> list[str] | None:
    """D-30, D-41, D-90, D-129. Devuelve los `partyId`, o None si alguno no se pudo leer."""
    ruta_partes = f"{ruta}.parties"
    if "parties" not in config:
        fallos.add(Fallo("MISSING_FIELD", ruta_partes))
        return None
    partes = config["parties"]
    if not isinstance(partes, list):
        fallos.add(Fallo("WRONG_TYPE", ruta_partes))
        return None

    ids: list[str] | None = []
    papeles: list[str] | None = []
    comprador: tuple[str, str] | None = None
    for j, parte in enumerate(partes):
        ruta_parte = f"{ruta_partes}.{j}"
        if not isinstance(parte, dict):
            fallos.add(Fallo("WRONG_TYPE", ruta_parte))
            ids = papeles = None
            continue
        _campos_no_definidos(
            parte, {"partyId", "role", "agentCardUrl"}, ruta_parte, fallos
        )
        party_id = _texto(parte, "partyId", ruta_parte, fallos)
        papel = _texto(parte, "role", ruta_parte, fallos)
        url = _texto(parte, "agentCardUrl", ruta_parte, fallos)
        if url is not None and origen(url) not in origenes:
            fallos.add(Fallo("INVALID_CONFIG", f"{ruta_parte}.agentCardUrl"))
        if papel is not None and papel not in ("BUYER", "SELLER"):
            fallos.add(Fallo("UNKNOWN_VALUE", f"{ruta_parte}.role"))
            papel = None
        if party_id is None or ids is None:
            ids = None
        else:
            ids.append(party_id)
        if papel is None or papeles is None:
            papeles = None
        else:
            papeles.append(papel)
        if papel == "BUYER" and party_id is not None and comprador is None:
            comprador = (f"{ruta_parte}.partyId", party_id)

    if comprador is not None:
        compradores.append(comprador)
    if (
        len(partes) != 2
        or (ids is not None and len(set(ids)) != 2)
        or (papeles is not None and set(papeles) != {"BUYER", "SELLER"})
    ):
        fallos.add(Fallo("INVALID_CONFIG", ruta_partes))
    return ids

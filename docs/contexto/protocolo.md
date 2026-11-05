# Protocolo de negociación

Decisiones que lo condicionan: D-10, D-11, D-17 a D-74, D-77 a D-94 y D-97 a D-118. D-32 sustituye a D-09, D-58 sustituye a D-24 y D-75 sustituye a D-03.

Vocabulario: una **parte** es cada participante de una sesión, comprador o vendedor (D-75). Su identificador es `partyId` y se fija en la configuración de la sesión (D-30, D-90). El **coordinador** es el componente del agente comprador que agrupa las sesiones de una petición (D-80).

## Actos

Actos de D-32. Todos viajan como cuerpo en la Part `data` con
`mediaType = application/vnd.tfm.negociacion.acto+json`.

### Cuerpo de cada acto
| Acto | Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|---|
| `PROPOSE` | `offer` | Oferta (ver «Oferta») | Sí | |
| `COUNTEROFFER` | `offer` | Oferta | Sí | |
| `ACCEPT` | — | — | — | Sin campos. Acepta la última oferta del rival (D-42) y produce un acuerdo provisional (D-77) |
| `WITHDRAW` | `reason` | cadena | No | Texto libre; solo se valida su tipo (D-43). Si no es cadena, falla con `WRONG_TYPE` y no es corregible (D-74) |

### Quién y cuándo
La configuración de la sesión indica qué parte abre y el papel de cada
una, comprador o vendedor (D-41, D-90).

| Acto | Emisor | Turno |
|---|---|---|
| `PROPOSE` | Parte que abre | Solo turno 1 |
| `COUNTEROFFER` | Parte con turno | ≥ 2 |
| `ACCEPT` | Parte con turno | ≥ 2 |
| `WITHDRAW` | Parte con turno | Cualquiera |

El protocolo no prohíbe repetir ofertas; es estrategia del agente (D-45).

### Último turno (D-57)
El último turno admite los mismos actos que cualquier otro turno ≥ 2. Si
termina en `COUNTEROFFER`, la sesión pasa a cierre con
`outcome = NO_AGREEMENT`, sin turno de respuesta para el rival (D-54).

### Acuerdo provisional (D-77, D-84, D-86)
Un `ACCEPT` aceptado no cierra la sesión: produce un acuerdo provisional
sobre la oferta vigente y la sesión pasa a `HELD`. Las dos partes reciben
`AGREEMENT_HELD`. El acuerdo solo es firme cuando el coordinador lo
confirma con `RESOLVE_HOLDS`. Si lo libera, o si vence el plazo de reserva
(`holdTimeoutSeconds`), la sesión cierra con `outcome = RELEASED`.

### Reglas de coherencia por acto
- El encaje del cuerpo con los esquemas de los actos se evalúa sobre el
  cuerpo tal como llega, antes de descartar campos no definidos (D-34). Si
  el tipo se corrige, el cuerpo se valida con el tipo corregido (D-72).
- `PROPOSE` y `COUNTEROFFER` comparten cuerpo. En modo tolerante, si el
  sobre indica uno de los dos, el tipo se corrige según el turno: turno 1 →
  `PROPOSE`, en otro caso → `COUNTEROFFER` (D-44, D-73). Precisa D-26.
- Un cuerpo vacío encaja con `ACCEPT` y `WITHDRAW`: si el sobre indica
  otro tipo, el encaje es múltiple y no es corregible (D-26).
- Un sobre `ACCEPT` o `WITHDRAW` con un cuerpo que trae oferta no es
  corregible, con una excepción: en modo tolerante, un `ACCEPT` cuya
  oferta es idéntica a la vigente tras normalizarla se mantiene como
  `ACCEPT`, se descarta la oferta y se registra la coerción con
  `ACT_BODY_MISMATCH` (D-73).
- `ACCEPT` en el turno 1 no es corregible: se reintenta (D-23).

## Mensajes de control
Van del orquestador a cada parte en el Message de `SendMessage`, con
`mediaType = application/vnd.tfm.negociacion.control+json` y
`sender = ORCHESTRATOR` en el sobre.

### `TURN_REQUEST`
Se envía completo en cada petición: el agente no necesita guardar
información de la sesión (D-46).

| Campo | Tipo | Obligatorio | Contenido |
|---|---|---|---|
| `role` | enumerado `BUYER` / `SELLER` | Sí | Papel del agente (D-41) |
| `fixedTerms` | objeto `{productId, unit, currency}` | Sí | Términos fijados por la sesión (D-36, D-90) |
| `allowedActs` | lista de actos | Sí | Turno 1: `PROPOSE`, `WITHDRAW`. Resto: `COUNTEROFFER`, `ACCEPT`, `WITHDRAW` (D-47) |
| `turnsLeft` | entero ≥ 1 | Sí | Turnos que quedan, incluido el actual: `maxTurns − turn + 1`. Vale 1 en el último turno (D-57) |
| `lastOffer` | Oferta | Desde el turno 2 | Última oferta del rival, ya validada y, si procede, corregida |
| `attempt` | entero ≥ 1 | Sí | 1 en el primer intento del turno |
| `retryReason` | lista de `{code, field}` | Solo si `attempt` > 1 | Fallos del intento anterior, con códigos de «Códigos de fallo» (D-48, D-50) |

### Envíos de control sin acto
`AGREEMENT_HELD` y `SESSION_CLOSE` no esperan ningún acto. Los dos se
envían igual (D-64, D-85): a las dos partes, con `SendMessage` y
`returnImmediately = true` sin sondeo, un intento por parte, envíos
independientes, `messageId` nuevo y no persistido, y `contextId` solo si
la parte lo tiene. La respuesta se registra y se ignora, y un fallo no
altera el estado de la sesión (D-49). Un error de transporte, la falta
de respuesta en `turnTimeoutSeconds` o un error A2A marcan el envío como
fallido (D-64, D-71). Cada envío se anota en el registro de envíos de
control (D-70, D-85).

### `AGREEMENT_HELD`
Se envía al entrar la sesión en `HELD` (D-85). El `turn` del sobre es el
del `ACCEPT`. Si la sesión sale de `HELD` con envíos de `AGREEMENT_HELD`
pendientes, esos envíos se descartan: el `SESSION_CLOSE` comunica el
resultado final.

| Campo | Tipo | Obligatorio | Contenido |
|---|---|---|---|
| `heldOffer` | Oferta | Sí | Oferta acordada: la vigente en el momento del `ACCEPT` (D-42) |
| `heldUntil` | cadena (instante ISO 8601 en UTC) | Sí | Caducidad de la reserva, calculada con el reloj de la base de datos como entrada en `HELD` + `holdTimeoutSeconds` (D-69, D-86) |

### `SESSION_CLOSE`
Se envía al entrar la sesión en `CLOSING`. Su envío pertenece al CU de
cierre (D-55). El `turn` del sobre es el del turno que provocó el
cierre; si la sesión viene de `HELD`, el del `ACCEPT` (D-64, D-84).

| Campo | Tipo | Obligatorio | Contenido |
|---|---|---|---|
| `outcome` | enumerado `AGREEMENT` / `WITHDRAWN` / `NO_AGREEMENT` / `ABORTED` / `RELEASED` | Sí | Resultado (D-54, D-84) |
| `agreedOffer` | Oferta | Solo si `AGREEMENT` | Oferta acordada en `HELD` y confirmada |
| `withdrawnBy` | cadena | Solo si `WITHDRAWN` | `partyId` de la parte que se retiró |
| `abortReason` | enumerado `RETRIES_EXHAUSTED` | Solo si `ABORTED` | Motivo del aborto (D-53) |
| `lastFailure` | `{code, field}` | Solo si `ABORTED` | Primer fallo, según el orden de validación, del intento que agotó los reintentos (D-61) |
| `releaseReason` | enumerado `BUYER_DECISION` / `HOLD_EXPIRED` | Solo si `RELEASED` | Liberado por `RESOLVE_HOLDS` o por plazo vencido (D-86) |
| `lastOffers` | lista de `{partyId, offer}` | Si `outcome` ≠ `AGREEMENT` y alguna parte llegó a ofertar | Última oferta aceptada de cada parte que ofertó, según el registro de actos aceptados, incluido el `COUNTEROFFER` del último turno. Las partes sin ofertas no aparecen (D-82) |

El `reason` de un `WITHDRAW` queda en el registro de actos aceptados y no
viaja en `SESSION_CLOSE`.

## Peticiones del comprador (D-87 a D-89)
Van del coordinador al orquestador en el Message de `SendMessage`, con
`mediaType = application/vnd.tfm.negociacion.peticion+json` y `sender`
igual al `partyId` del comprador. El orquestador responde con una Task
que completa con un Artifact de resultado, con
`mediaType = application/vnd.tfm.negociacion.resultado+json`.

Las Tasks de las peticiones se guardan en la misma base de datos que el
estado de las sesiones, y `GetTask` del coordinador se responde con la
Task guardada, también tras una caída de la instancia que aceptó la
petición (D-97).

Las peticiones no se autocorrigen en ningún modo: cualquier fallo rechaza
la petición entera. La Task termina en `TASK_STATE_REJECTED` y su mensaje
de estado lleva una Part `data` de resultado con `rejections`, una lista
de `{code, field}` con códigos de «Códigos de fallo» (D-89).
`rejections` recoge todos los fallos de la petición en una sola pasada,
ordenados por ruta. Las comprobaciones que dependen de un campo con fallo
estructural (`MISSING_FIELD`, `WRONG_TYPE`, `UNKNOWN_VALUE`) no se hacen
sobre ese campo (D-101).

### Forma de una petición (D-103)
Un Message dirigido al orquestador tiene forma de petición si lleva la
cabecera `A2A-Extensions` con la URI de la extensión, la URI en
`extensions`, el sobre en `metadata["urn:tfm:negociacion:v1"]` y
exactamente una Part, de tipo `data` y con el `mediaType` de petición. Si
le falta algo de esto, se rechaza con un solo fallo, `INVALID_MESSAGE` en
`message`, sin validar el sobre ni el cuerpo.

### Peticiones duplicadas (D-98, D-109)
Antes de validar un `OPEN_ROUND` o un `RESOLVE_HOLDS`, el orquestador
busca en el registro de peticiones una entrada con el mismo `sender` y
`messageId`. Si existe, devuelve la Task de esa petición en su estado
actual, aceptada o rechazada, y no escribe nada. El par `sender` +
`messageId` es único en el registro: si dos copias llegan a la vez, la
segunda escritura falla y se devuelve la Task de la primera. Si el sobre
no permite leer `sender`, no se comprueba el duplicado y la petición se
rechaza.

### Sobre del resultado (D-104, D-106)
El Artifact de resultado y el mensaje de estado de un rechazo llevan la
URI en `extensions` y un sobre con `type` igual al de la petición,
`sender = ORCHESTRATOR` y sin `sessionId` ni `turn`. Si la petición se
rechaza con `INVALID_MESSAGE` y no se pudo leer un `type` de petición
válido, el mensaje de estado no lleva sobre: solo la Part `data` con
`rejections` y la URI en `extensions`.

### `OPEN_ROUND`
Abre una ronda de sesiones de una petición (D-83, D-88).

| Campo | Tipo | Obligatorio | Contenido |
|---|---|---|---|
| `requestId` | cadena (UUID) | Desde la ronda 2 | Petición a la que pertenece la ronda. Ausente en la primera ronda: el orquestador lo genera |
| `sessions` | lista de `{itemId, config}` | Sí, al menos una | Una entrada por partida. `itemId`: cadena que identifica la partida para el coordinador, distinta dentro de la ronda. `config`: configuración de la sesión (`configuracion-sesion.md`) |

El orquestador valida todas las configuraciones, crea las sesiones en
`CREATED`, asigna la ronda y comprueba las AgentCards (D-25). La Task se
crea en `TASK_STATE_WORKING` en la misma transacción que las sesiones y
se completa cuando todas las sesiones de la ronda han salido de
`CREATED`, para que el resultado indique cuáles no empezaron (D-94,
D-97).

Las AgentCards de cada sesión se obtienen en paralelo, con un intento por
parte y el `turnTimeoutSeconds` efectivo de la sesión como tiempo máximo,
aunque la misma parte aparezca en varias sesiones de la ronda. Una parte
falla si su AgentCard no se puede obtener (error de transporte, tiempo
superado o respuesta no interpretable) o si no declara la extensión con
`required = true`. Si fallan las dos, `failedPartyId` es la primera según
el orden de `parties` (D-99).

A partir de la ronda 2, una ronda nueva solo se acepta cuando la anterior
ha terminado y no reabre partidas mantenidas o confirmadas (D-100,
D-105). Si dos `OPEN_ROUND` de la misma petición compiten, la escritura
condicional por versión del registro de petición decide cuál entra; el
otro se reevalúa, incluidos el número de ronda y `ROUND_CONFLICT` (D-101).

Artifact de resultado:

| Campo | Tipo | Contenido |
|---|---|---|
| `requestId` | cadena (UUID) | Petición |
| `round` | entero ≥ 1 | Número de la ronda |
| `sessions` | lista de `{itemId, sessionId, started, failedPartyId}` | `started` es falso si la sesión quedó en `NOT_STARTED`; en ese caso `failedPartyId` indica la parte cuya AgentCard falló |

### `RESOLVE_HOLDS`
Confirma o libera acuerdos provisionales de una petición (D-84, D-88). Se
aplica en una sola transacción: el paquete se resuelve entero o no se
resuelve (D-77).

| Campo | Tipo | Obligatorio | Contenido |
|---|---|---|---|
| `requestId` | cadena (UUID) | Sí | Petición a la que pertenecen las sesiones |
| `confirm` | lista de `sessionId` | Sí (puede estar vacía) | Sesiones en `HELD` que pasan a `CLOSING` con `AGREEMENT` |
| `release` | lista de `sessionId` | Sí (puede estar vacía) | Sesiones en `HELD` que pasan a `CLOSING` con `RELEASED` y `releaseReason = BUYER_DECISION` |

Cada sesión de las listas debe pertenecer a la petición, estar en `HELD`
y tener `heldUntil` sin vencer según el reloj de la base de datos. Una
sesión con el plazo vencido cuenta como fuera de `HELD` aunque la
caducidad no se haya procesado; el rechazo no la modifica (D-111). Si el
`requestId` tiene cualquier fallo, no se comprueban las sesiones (D-117).

La Task se crea directamente en `TASK_STATE_COMPLETED`, con el Artifact
de resultado, en la misma transacción que las sesiones resueltas, o en
`TASK_STATE_REJECTED` si la petición se rechaza (D-110).

Artifact de resultado: `requestId`, `confirmed` y `released`, con los
`sessionId` resueltos.

### Peticiones no válidas (D-89, D-100, D-102, D-103, D-105, D-111 a D-117)
| Petición | Caso | Código | Campo |
|---|---|---|---|
| Ambas | El Message no tiene forma de petición | `INVALID_MESSAGE` | `message` |
| Ambas | Sobre o cuerpo con un campo ausente, de tipo incorrecto, con valor enumerado desconocido o no definido | `MISSING_FIELD`, `WRONG_TYPE`, `UNKNOWN_VALUE`, `UNKNOWN_FIELD` | Ruta del campo |
| `OPEN_ROUND` | Alguna configuración incumple sus restricciones, incluidas las que se comprueban sobre los valores efectivos (D-91) | `INVALID_CONFIG` | `body.sessions.<i>.config.<campo>` |
| `OPEN_ROUND` | `itemId` repetido en la ronda, o el `partyId` del `BUYER` no es el mismo en todas las sesiones | `INVALID_CONFIG` | Ruta del campo |
| `OPEN_ROUND` | El `partyId` del `BUYER` es el mismo en todas las sesiones, pero distinto del `sender`. En cualquier ronda | `NOT_AUTHORIZED` | `envelope.sender` |
| Ambas | `requestId` desconocido o cuyo comprador no es el `sender`. No se distingue entre los dos casos | `UNKNOWN_REQUEST` | `body.requestId` |
| `OPEN_ROUND` | Con `requestId`, alguna sesión de la petición está en `CREATED` o `NEGOTIATING` | `ROUND_CONFLICT` | `body.requestId` |
| `OPEN_ROUND` | Un `itemId` coincide con el de una sesión de la petición en `HELD`, o en `CLOSING` o `CLOSED` con `outcome = AGREEMENT` | `ROUND_CONFLICT` | `body.sessions.<i>.itemId` |
| `RESOLVE_HOLDS` | Alguna sesión no pertenece a la petición, no está en `HELD` o tiene `heldUntil` vencido | `NOT_HELD` | `body.confirm.<i>` o `body.release.<i>`, sin el estado de la sesión (D-112) |
| `RESOLVE_HOLDS` | Las dos listas vacías | `INVALID_REQUEST` | `body` (D-116) |
| `RESOLVE_HOLDS` | Un `sessionId` en las dos listas | `INVALID_REQUEST` | Cada una de sus apariciones (D-116) |
| `RESOLVE_HOLDS` | Un `sessionId` repetido dentro de una misma lista | `INVALID_REQUEST` | Cada aparición después de la primera (D-114) |

Si el `partyId` del `BUYER` no es el mismo en todas las sesiones, se
rechaza con `INVALID_CONFIG` y no se añade `NOT_AUTHORIZED` (D-102). En
`RESOLVE_HOLDS` no se usa `NOT_AUTHORIZED`: un `sender` que no es el
comprador del `requestId` se rechaza con `UNKNOWN_REQUEST` (D-113). Si un
`sessionId` está en las dos listas y además repetido en alguna, se marcan
todas sus apariciones, con un solo fallo por ruta (D-116).

Que la AgentCard de una parte no declare la extensión, o no se pueda
obtener, no rechaza `OPEN_ROUND`: esa sesión queda en `NOT_STARTED` y el
resultado lo indica (D-89, D-99).

## Esquema de mensaje

### Campos comunes (sobre)
Todo mensaje del protocolo lleva un sobre en
`metadata["urn:tfm:negociacion:v1"]` (D-19, D-27), salvo el rechazo
sin `type` legible de D-106. Los nombres de campo van en inglés y
camelCase (D-29).

| Campo | Tipo | Obligatorio | Restricción | Corrección en modo tolerante (solo actos) |
|---|---|---|---|---|
| `sessionId` | cadena (UUID) | En actos y control | Igual al identificador de la sesión en el estado externalizado (D-67) | Si falta o no coincide, se toma del estado |
| `turn` | entero | En actos y control | ≥ 1. Contador único por sesión: empieza en 1 y sube cada vez que el turno pasa al otro agente. Los reintentos no lo cambian (D-08, D-33) | Una cadena numérica se convierte a entero; si no coincide, se toma del estado |
| `type` | enumerado | Sí | Actos: `PROPOSE`, `COUNTEROFFER`, `ACCEPT`, `WITHDRAW`. Control: `TURN_REQUEST`, `AGREEMENT_HELD`, `SESSION_CLOSE`. Peticiones y su resultado: `OPEN_ROUND`, `RESOLVE_HOLDS` (D-32, D-85, D-88, D-104) | Se normalizan mayúsculas, espacios y guiones; si no coincide con el cuerpo, se aplica D-26 |
| `sender` | cadena | Sí | En un acto: `partyId` de la parte con turno (D-30). En control y en el resultado de una petición: `ORCHESTRATOR` (D-104). En una petición: `partyId` del comprador (D-89) | En un acto, si falta o no es la parte con turno, se toma del estado |

Las peticiones del comprador y su resultado no llevan `sessionId` ni
`turn`, y su sobre nunca se corrige (D-89, D-93, D-104).

### Eco del sobre (D-28)
El orquestador envía `sessionId` y `turn` en cada petición de turno. El
agente los devuelve sin modificar en el sobre de su acto.

### Criterio de corrección del sobre (D-31)
Un campo del sobre de un acto solo se corrige cuando su valor correcto se
puede conocer por el estado externalizado o por normalización
determinista del propio valor. Nunca se deduce del contenido de la
negociación. En modo estricto ningún campo se corrige: el fallo se
registra y se pasa a reintento.

### Campos no definidos (D-34)
Un campo del sobre de un acto que no figure en esta tabla se descarta y
se registra como coerción en modo tolerante. En modo estricto es fallo y
se pasa a reintento. En el cuerpo, los campos no definidos se descartan
después de evaluar el encaje (D-72). En una petición del comprador, un
campo no definido la rechaza con `UNKNOWN_FIELD`, también `sessionId` o
`turn` en el sobre (D-89, D-93).

## Oferta

Los valores fijados por la sesión se definen en `configuracion-sesion.md`
(D-40, D-90).

Una sesión negocia un único producto (D-35). Toda oferta lleva todos sus
términos (D-10). Los nombres siguen D-29.

| Campo | Tipo | Restricción | Origen | Corrección en modo tolerante |
|---|---|---|---|---|
| `productId` | cadena | Igual al de la configuración de la sesión | Sesión (D-36) | Si falta o no coincide, se toma de la sesión |
| `unit` | cadena | Igual a la de la configuración de la sesión | Sesión (D-36) | Si falta o no coincide, se toma de la sesión |
| `currency` | cadena | ISO 4217, igual a la de la configuración de la sesión | Sesión (D-36) | Se normaliza a mayúsculas; si falta o no coincide, se toma de la sesión |
| `quantity` | entero | > 0 | Negociado | Una cadena numérica, o un número con parte decimal nula, se convierte a entero |
| `unitPrice` | número, interpretado como decimal exacto (D-37) | > 0; máximo 2 decimales | Negociado | Se normalizan coma decimal, espacios y símbolo de moneda (`"12,50 €"` → 12.50) |
| `deliveryDays` | entero | ≥ 0; días hasta la entrega | Negociado | Una cadena numérica se convierte a entero |
| `paymentDays` | entero | ≥ 0; días de pago desde la entrega | Negociado | Una cadena numérica se convierte a entero |

La oferta no incluye importe total (D-38). Quien necesite el importe lo
calcula como `unitPrice × quantity` (D-81).

### Criterio de corrección de la oferta (D-39)
Se aplica el mismo criterio que al sobre (D-31): solo se corrige lo que se
conoce por la sesión o por normalización determinista del propio valor.
No son corregibles, y pasan a reintento (D-23):
- un término negociado ausente: nunca se rellena con la oferta anterior;
- un valor fuera de rango (cantidad o precio ≤ 0, días < 0);
- un valor que exigiría redondear (cantidad no entera, precio con más de
  2 decimales).

Un campo no definido en la tabla sigue la regla de D-34.
En modo estricto no se corrige nada: se registra y se reintenta.

## Correspondencia con A2A

Base: especificación A2A 1.0 (D-17). El protocolo de negociación es una
extensión A2A obligatoria (D-18).

### Papeles
| TFM | A2A |
|---|---|
| Orquestador frente a las partes | Cliente A2A de cada agente. Sus mensajes llevan `role = ROLE_USER` |
| Agente de cada parte (D-06) | Servidor A2A. Sus mensajes llevan `role = ROLE_AGENT` |
| Orquestador frente al coordinador (D-87) | Servidor A2A del coordinador. Guarda las Tasks de las peticiones en PostgreSQL (D-97) |
| Coordinador del comprador (D-80, D-87) | Cliente A2A del orquestador. El agente comprador es a la vez servidor A2A del orquestador y cliente suyo |

### Extensión
- Identificada por `urn:tfm:negociacion:v1` (D-27). Un cambio incompatible
  del protocolo incrementa la versión final.
- Cada agente y el orquestador la declaran en su AgentCard con
  `required = true` (D-18, D-87).
- El cliente la activa en cada petición con la cabecera `A2A-Extensions`.
- Todo Message o Artifact del protocolo incluye la URI en su lista
  `extensions`, incluidos el Artifact de resultado y el mensaje de estado
  de un rechazo (D-104).

### Dónde viaja cada cosa (D-19)
| Elemento | Ubicación |
|---|---|
| Sobre (campos comunes, ver «Esquema de mensaje») | `metadata["urn:tfm:negociacion:v1"]` del Message o Artifact |
| Cuerpo | Una única Part con contenido `data` |
| Identificación del cuerpo | `mediaType` de esa Part: `application/vnd.tfm.negociacion.acto+json` (actos), `application/vnd.tfm.negociacion.control+json` (control), `application/vnd.tfm.negociacion.peticion+json` (peticiones del comprador) y `application/vnd.tfm.negociacion.resultado+json` (resultado de una petición) |

No se usan Parts `text`, `raw` ni `url` en el protocolo.

### Familias de mensaje (D-21, D-87)
| Familia | Sentido | Contenedor A2A |
|---|---|---|
| Control (`TURN_REQUEST`, `AGREEMENT_HELD`, `SESSION_CLOSE`) | Orquestador → agente de cada parte | Message de `SendMessage` |
| Acto (`PROPOSE`, `COUNTEROFFER`, `ACCEPT`, `WITHDRAW`) | Agente → orquestador | Artifact de la Task del turno |
| Petición del comprador (`OPEN_ROUND`, `RESOLVE_HOLDS`) | Coordinador → orquestador | Message de `SendMessage`; el resultado, en el Artifact de la Task del orquestador, y el rechazo, en su mensaje de estado |

### Sesión, turno y Task (D-20, D-58)
| TFM | A2A |
|---|---|
| Sesión | Un `contextId` por agente: dos por sesión. En el primer turno de cada agente el orquestador no envía `contextId`; guarda el que devuelve el servidor en el estado externalizado (D-04) y lo envía en los turnos siguientes |
| Turno | Una Task. El orquestador llama a `SendMessage` del agente con turno (D-05) con un mensaje de control; el agente responde con una Task, que el orquestador sondea hasta un estado final. Su Artifact contiene el acto |
| Intento | Un `SendMessage` con un `messageId` generado por el orquestador y guardado antes del envío. Se reutiliza si hay que reenviar el mismo intento tras una caída (D-66) |
| Reintento (D-08) | Nueva `SendMessage` con nuevo `messageId`, en el mismo `contextId` si ya existe, con `referenceTaskIds` apuntando a la Task del intento anterior si la hubo |
| Identificadores que guarda el estado externalizado | Los dos `contextId`, el `taskId` y el `messageId` del intento en curso, y el `taskId` del intento anterior |

### Precondición de sesión (D-25, D-99)
La sesión solo se inicia si la AgentCard de ambos agentes se puede
obtener y declara la extensión con `required = true`. Si no, queda en
`NOT_STARTED`, sin `SESSION_CLOSE` (`maquina-estados.md`, sección 1). El
coordinador lo sabe por el resultado de `OPEN_ROUND`.

### Ejecución del turno (D-52, D-58 a D-60, D-62, D-66, D-68, D-71)
- `SendMessage` se invoca con `returnImmediately = true`. El orquestador
  guarda el `taskId` y, si es nuevo, el `contextId` devueltos antes de
  empezar a esperar.
- Después consulta la Task con `GetTask` cada `pollIntervalSeconds` (D-59)
  hasta que llega a un estado final o se supera `turnTimeoutSeconds`.
- El tiempo del turno cuenta desde justo antes de `SendMessage`.
- Si se supera el tiempo del turno: se registra `TURN_TIMEOUT`, cuenta como
  intento fallido y pasa a reintento. Si ya hay `taskId`, se envía
  `CancelTask` sin esperar a que tenga éxito.
- Un error de transporte en `GetTask` no hace fallar el intento: se sigue
  sondeando hasta el tiempo máximo.
- Las respuestas tardías se descartan por construcción: el orquestador
  solo consulta el `taskId` del intento en curso.

| Resultado del sondeo | Tratamiento |
|---|---|
| `TASK_STATE_SUBMITTED`, `TASK_STATE_WORKING` | Se sigue sondeando |
| `TASK_STATE_COMPLETED` | Se valida la respuesta |
| `TASK_STATE_FAILED` / `TASK_STATE_REJECTED` | `TASK_FAILED` / `TASK_REJECTED` (D-23) |
| `TASK_STATE_CANCELED` | `TASK_CANCELED` (D-60) |
| `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` u otro estado | `CancelTask` sin esperar resultado y `TASK_INTERRUPTED` (D-60) |
| `TaskNotFoundError` | `MISSING_ACT` en `task` (D-68) |

Si `SendMessage` devuelve directamente una Task en estado final, se trata
igual que el resultado del sondeo. Si devuelve un Message, el intento
falla con `MISSING_ACT` en `task`, sin `taskId` (D-62). Si devuelve un
error A2A, el intento falla con `AGENT_ERROR` en `task`, sin `taskId`
(D-71).

### Respuestas no corregibles (D-23, D-60, D-62, D-68, D-71)
Una respuesta no es corregible, y pasa directamente a reintento (D-08) y,
agotados los reintentos, a ABORTAR (D-07), cuando:
- la Task termina en un estado distinto de `TASK_STATE_COMPLETED`, o queda
  en un estado de interrupción o desconocido;
- `SendMessage` responde con un Message en lugar de una Task;
- `SendMessage` responde con un error A2A;
- la Task deja de existir en el agente durante el sondeo; o
- la Task no contiene exactamente un Artifact con exactamente una Part
  `data` cuyo `mediaType` sea el de acto.

### Alcance de la validación (D-22)
La autocorrección actúa sobre el sobre y el cuerpo de los actos una vez
interpretados como objetos: campos ausentes, tipos incorrectos y valores
enumerados mal escritos. El JSON mal formado y el texto libre quedan
fuera. Las peticiones del comprador no se autocorrigen (D-89).

#### Fallo de coherencia entre sobre y cuerpo (D-26, D-72, D-73)
Se produce cuando el tipo de acto del sobre no coincide con el esquema del
cuerpo. El encaje se evalúa sobre el cuerpo tal como llega (D-72). Manda
el cuerpo:
- si el cuerpo encaja con el esquema de un único acto, en modo tolerante se
  corrige el tipo del sobre y se registra la coerción; en modo estricto se
  registra el fallo y se pasa a reintento;
- si no encaja con ninguno o encaja con más de uno, no es corregible: se
  registra el fallo y se pasa a reintento (D-23).

La distinción por turno entre `PROPOSE` y `COUNTEROFFER` (D-44) solo se
aplica cuando el sobre es uno de los dos. Un sobre `ACCEPT` o `WITHDRAW`
con oferta no es corregible, salvo el `ACCEPT` con la oferta vigente
repetida en modo tolerante (D-73).

## Códigos de fallo

Catálogo común para `retryReason`, el registro de fallos, el registro de
coerciones, el registro de envíos de control y los rechazos de peticiones
del comprador (D-50, D-70, D-85, D-89). El campo afectado se indica con
una ruta con puntos y prefijo de zona: `envelope.<campo>`,
`body.<campo>` (p. ej. `body.offer.unitPrice`; en listas, con el índice:
`body.sessions.0.config.maxTurns`), `task` para fallos de la respuesta
A2A o `message` para un Message sin forma de petición (D-103). La ruta
puede ser solo la zona cuando el fallo afecta a la combinación de
varios campos, como `body` en `INVALID_REQUEST` (D-116). El registro de
envíos de control no lleva campo.

| Código | Cuándo | Corregible en modo tolerante |
|---|---|---|
| `TASK_FAILED` | La Task termina en `TASK_STATE_FAILED` | No |
| `TASK_REJECTED` | La Task termina en `TASK_STATE_REJECTED` | No |
| `TASK_CANCELED` | La Task termina en `TASK_STATE_CANCELED` (D-60) | No |
| `TASK_INTERRUPTED` | La Task queda en `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` o en un estado desconocido (D-60) | No |
| `TURN_TIMEOUT` | Se supera el tiempo máximo del turno, o no hay respuesta a un envío de control en `turnTimeoutSeconds` (D-70, D-85) | No |
| `AGENT_UNREACHABLE` | Error de transporte al llamar a `SendMessage`, en un turno o en un envío de control (D-70) | No |
| `AGENT_ERROR` | El agente responde a `SendMessage` con un error A2A, en un turno o en un envío de control (D-71) | No |
| `MISSING_ACT` | Ningún Artifact con Part `data` de acto, respuesta con Message (D-62) o Task desaparecida durante el sondeo (D-68) | No |
| `MULTIPLE_ACTS` | Más de un Artifact de acto o más de una Part `data` | No |
| `MISSING_FIELD` | Falta un campo obligatorio | Solo si su valor se conoce por el estado o la sesión |
| `WRONG_TYPE` | Tipo incorrecto | Solo con conversión determinista; nunca para `reason` (D-74) |
| `INVALID_FORMAT` | Formato normalizable | Sí |
| `UNKNOWN_VALUE` | Valor enumerado no normalizable | No |
| `STATE_MISMATCH` | Valor distinto del estado o de la sesión | Sí |
| `OUT_OF_RANGE` | Valor fuera de rango | No |
| `PRECISION_EXCEEDED` | El valor exigiría redondear | No |
| `UNKNOWN_FIELD` | Campo no definido | Sí, descartándolo (D-34) |
| `ACT_BODY_MISMATCH` | El sobre y el cuerpo no coinciden | Solo si el cuerpo encaja con un único acto (D-26), o si es un `ACCEPT` con la oferta vigente repetida (D-73) |
| `ACT_NOT_ALLOWED` | Acto no permitido en el turno | Solo entre `PROPOSE` y `COUNTEROFFER`, por el turno (D-44) |
| `INVALID_MESSAGE` | Un Message dirigido al orquestador no tiene forma de petición (D-103) | No aplica: rechazo |
| `INVALID_CONFIG` | Una configuración de `OPEN_ROUND` incumple sus restricciones, hay un `itemId` repetido o el `partyId` del `BUYER` no es el mismo en todas las sesiones (D-89, D-91, D-102) | No aplica: rechazo |
| `UNKNOWN_REQUEST` | `requestId` desconocido o cuyo comprador no es el `sender`, sin distinguir los dos casos (D-89, D-102, D-113) | No aplica: rechazo |
| `ROUND_CONFLICT` | `OPEN_ROUND` con la ronda anterior sin terminar, o que reabre una partida en `HELD` o ya confirmada (D-100, D-105) | No aplica: rechazo |
| `NOT_HELD` | Una sesión de `RESOLVE_HOLDS` no pertenece a la petición, no está en `HELD` o tiene `heldUntil` vencido (D-89, D-111) | No aplica: rechazo |
| `NOT_AUTHORIZED` | Solo en `OPEN_ROUND`: el `BUYER` es el mismo en todas las sesiones pero distinto del `sender` (D-89, D-102, D-113) | No aplica: rechazo |
| `INVALID_REQUEST` | `RESOLVE_HOLDS` con las dos listas vacías, con una sesión en las dos o con un `sessionId` repetido en una lista (D-89, D-114, D-116) | No aplica: rechazo |

En modo estricto ningún fallo se corrige. En las peticiones del comprador
cualquier código produce rechazo.

### Registro
- **Fallo:** `code`, `field`, `turn`, `attempt`, `taskId` del intento si lo
  hay e instante.
- **Coerción** (fallo corregido): `code`, `field`, `turn`, `attempt`,
  `taskId`, valor original, valor corregido, decisión aplicada e instante.
- **Envío de control** (D-70, D-85): tipo de mensaje (`AGREEMENT_HELD` o
  `SESSION_CLOSE`), parte, `turn`, instante, resultado (enviado o
  fallido) y, según el caso, `taskId` y estado de la Task, indicación de
  Message o `code` del fallo.
- **Petición del comprador** (D-89, D-98, D-103, D-109, D-118): tipo,
  `requestId`, ronda, `sender`, `messageId`, `taskId` de la Task de la
  petición, resultado (aceptada o rechazada), códigos de rechazo e
  instante. El tipo y el `sender` solo figuran si se pudieron leer, y
  `requestId` falta en un rechazo de ronda 1 o si no es válido. En
  `RESOLVE_HOLDS`, la ronda es la última abierta de la petición, y falta
  si el `requestId` no es válido. Un duplicado no deja entrada. El par
  `sender` + `messageId` es único.

Los cuatro son tablas de solo añadir en PostgreSQL, escritas en la misma
transacción que la transición de estado que las produce (D-63, D-69).
Detalle en `maquina-estados.md`, sección 3.

## Preguntas abiertas
Ninguna propia. Las pendientes están en `maquina-estados.md`, sección 6.

# Máquina de estados

Decisiones que la condicionan: D-04, D-05, D-07, D-08, D-20, D-23, D-25, D-46, D-49, D-51 a D-57, D-58 a D-71, D-77 y D-82 a D-129. D-58 sustituye a D-24.

Este documento define los estados por los que pasa una sesión, los subestados de cada turno, qué se guarda en el estado externalizado en cada transición, cómo se agrupan las sesiones en peticiones, cómo se cierra la sesión y qué restricciones impone todo ello a la configuración. El estado externalizado se guarda en PostgreSQL (D-69).

Principios que lo condicionan:
- El orquestador no guarda estado en memoria (D-04). Toda la información necesaria para continuar una sesión, y las Tasks de las peticiones del comprador (D-97), están en el estado externalizado.
- Otra instancia del orquestador puede retomar una sesión a medias tras una caída. Por eso el estado se guarda en cada punto de espera de E/S, no solo al resolver cada turno.
- Solo se guardan los estados en los que el orquestador espera una operación de E/S o una decisión externa. La validación ocurre en memoria y su resultado se guarda directamente como la transición siguiente.

Vocabulario: «parte» es cada participante de una sesión, comprador o vendedor, identificado por su `partyId` (D-75, D-90).

## 1. Estados de la sesión

| Estado | Significado | Terminal |
|---|---|---|
| `CREATED` | Sesión creada por un `OPEN_ROUND` aceptado, con los valores efectivos de su configuración guardados (D-88, D-91). Aún no se han comprobado las AgentCards | No |
| `NOT_STARTED` | Alguna AgentCard no declara la extensión con `required = true` o no se puede obtener (D-25, D-99). No se envía `SESSION_CLOSE` | Sí |
| `NEGOTIATING` | Hay un turno en curso. Sus subestados se definen en la sección 2 | No |
| `HELD` | Hay un acuerdo provisional (D-77, D-84). No hay turno ni Task en curso: la sesión espera a que el coordinador lo confirme o lo libere, o a que venza el plazo de reserva (D-86) | No |
| `CLOSING` | El resultado ya está decidido y guardado; falta enviar `SESSION_CLOSE` a las partes (D-55, D-64) | No |
| `CLOSED` | `SESSION_CLOSE` enviado o intentado a ambas partes. Resultado definitivo | Sí |

`NOT_STARTED` no es `ABORTED`: todo aborto pasa por agotar reintentos (D-53), y una sesión que no llegó a negociar no tiene turno ni reintentos.

### Transiciones

| Desde | Evento | Hacia | Qué se guarda al transitar |
|---|---|---|---|
| — | `OPEN_ROUND` aceptado (D-88) | `CREATED` | `sessionId` (D-67), `requestId`, ronda, `itemId` y valores efectivos de la configuración (D-91) |
| `CREATED` | Ambas AgentCards se obtienen y declaran la extensión (D-99) | `NEGOTIATING` (`READY`) | `turn = 1`, `attempt = 1`, `messageId` del intento (D-66) |
| `CREATED` | Alguna AgentCard no la declara, no se puede obtener o su URL de servicio no es válida (D-99, D-131) | `NOT_STARTED` | `failedPartyId`: la parte que falló o, si fallan las dos, la primera según el orden de `parties` |
| `NEGOTIATING` | `PROPOSE` o `COUNTEROFFER` aceptado y `turn < maxTurns` | `NEGOTIATING` (`READY`) | `turn + 1`, `attempt = 1`, nuevo `messageId`, nueva oferta vigente con su emisor |
| `NEGOTIATING` | `COUNTEROFFER` aceptado y `turn = maxTurns` | `CLOSING` | `outcome = NO_AGREEMENT` y `lastOffers` (D-54, D-57, D-82) |
| `NEGOTIATING` | `ACCEPT` aceptado | `HELD` | Oferta acordada = oferta vigente (D-42), `heldUntil` = ahora + `holdTimeoutSeconds` (D-86), envío de `AGREEMENT_HELD` pendiente a cada parte (D-85) |
| `NEGOTIATING` | `WITHDRAW` aceptado | `CLOSING` | `outcome = WITHDRAWN`, `withdrawnBy`, `reason` si la hay, y `lastOffers` (D-82) |
| `NEGOTIATING` | Reintentos agotados en el turno | `CLOSING` | `outcome = ABORTED`, `abortReason = RETRIES_EXHAUSTED`, `lastFailure` y `lastOffers` (D-07, D-53, D-61, D-82) |
| `HELD` | `RESOLVE_HOLDS` la confirma (D-88) | `CLOSING` | `outcome = AGREEMENT`, `agreedOffer` = oferta acordada |
| `HELD` | `RESOLVE_HOLDS` la libera (D-88) | `CLOSING` | `outcome = RELEASED`, `releaseReason = BUYER_DECISION`, `lastOffers` (D-82, D-86) |
| `HELD` | Vence `heldUntil` | `CLOSING` | `outcome = RELEASED`, `releaseReason = HOLD_EXPIRED`, `lastOffers` y el arrendamiento de la instancia que procesa la caducidad (D-82, D-86, D-121) |
| `CLOSING` | `SESSION_CLOSE` enviado o intentado a ambas partes | `CLOSED` | Resultado del envío a cada parte (D-49, D-64, D-70) |

`lastOffers` se obtiene del registro de actos aceptados: la última oferta de cada parte que llegó a ofertar, incluido el `COUNTEROFFER` del último turno. Las partes sin ofertas no aparecen (D-82).

La transacción que saca de `CREATED` la última sesión de una ronda completa también la Task del `OPEN_ROUND` con su Artifact de resultado (D-94, D-97).

Una sesión en `HELD` con `heldUntil` vencido ya no admite `RESOLVE_HOLDS`, aunque la caducidad todavía no se haya procesado: cuenta como fuera de `HELD` y la petición se rechaza con `NOT_HELD` (D-111).

### Criterios de diseño
- **El resultado se guarda al entrar en `CLOSING`, no al salir.** La instancia que retome una sesión en cierre no recalcula nada: solo envía lo que falte.
- **`CLOSING` guarda el estado del envío a cada parte por separado.** Al recuperar, se envía `SESSION_CLOSE` solo a quien siga pendiente. Puede duplicarse un envío si la caída ocurre entre enviar y marcar; no rompe nada, porque el agente no guarda estado de sesión (D-46) y el orquestador ignora su respuesta (D-49).
- **La comprobación de AgentCards no tiene estado propio.** Repetirla tras una caída no tiene efectos secundarios, así que `CREATED` basta. Cada sesión se comprueba por separado, con un intento por parte, aunque una parte aparezca en varias sesiones de la ronda (D-99).
- **La Task del `OPEN_ROUND` se completa una sola vez.** Cada transacción de salida de `CREATED` escribe también el registro de petición de forma condicional por versión, así que dos instancias no pueden creer a la vez que la otra sesión sigue en `CREATED` (D-63, D-97).
- **El turno 1 nunca es el último.** `maxTurns ≥ 2` (D-56), así que no existe la transición «`PROPOSE` en el último turno».
- **El `COUNTEROFFER` del último turno no pasa a ser la oferta vigente.** Queda en el registro de actos aceptados, de donde sale para `lastOffers`; la transición a `CLOSING` no cambia la oferta vigente.
- **`HELD` decide el resultado en su transición de salida** (D-84). `CLOSING` sigue significando que el resultado está decidido y `CLOSED` sigue siendo terminal.
- **En `HELD` no hay nada que retomar salvo envíos pendientes o el plazo vencido.** Sin turno ni Task en curso, la sesión solo necesita arrendamiento para enviar `AGREEMENT_HELD` o para procesar la caducidad. Al marcar el último envío de `AGREEMENT_HELD` se libera el arrendamiento (D-108).
- **Los envíos de `AGREEMENT_HELD` pendientes al salir de `HELD` se descartan.** El `SESSION_CLOSE` comunica el resultado final, así que avisar después de un acuerdo provisional que ya no existe solo confundiría a la parte. Por lo mismo, si `heldUntil` ya ha vencido no se envía `AGREEMENT_HELD`: se aplica la caducidad (D-107).
- **El plazo vencido manda sobre `RESOLVE_HOLDS`.** Que una sesión pueda confirmarse o no no depende de cuándo pase la búsqueda: se decide comparando `heldUntil` con el reloj de la base de datos (D-111).
- **Una sesión puede seguir en `HELD` durante varias rondas** si el coordinador no la resuelve antes de abrir la siguiente (D-79). El plazo de reserva no está garantizado en ese caso: si vence, la sesión se libera por plazo (D-86). Una ronda nueva no puede reabrir su partida (D-100).

## 2. Subestados del turno

Dentro de `NEGOTIATING`:

| Subestado | Significado | Qué hay en el estado |
|---|---|---|
| `READY` | Turno e intento preparados; no hay Task en curso | `turn`, `attempt`, `messageId` del intento (D-66) y, si es un reintento, `retryReason` y el `taskId` del intento anterior si lo tuvo |
| `AWAITING_TASK` | Task creada en el agente; se sondea (D-58) | Lo anterior, más el `taskId` en curso, el `contextId` del agente y el instante de inicio del intento |

### Transiciones

| Desde | Evento | Resultado |
|---|---|---|
| `READY` | `SendMessage` (`returnImmediately = true`) devuelve una Task no final | `AWAITING_TASK` |
| `READY` | `SendMessage` devuelve una Task ya final | Se evalúa como si `GetTask` la hubiera devuelto en ese estado (tabla siguiente) |
| `READY` | `SendMessage` devuelve un Message | Intento fallido: `MISSING_ACT` en `task`, sin `taskId` (D-62) |
| `READY` | `SendMessage` devuelve un error A2A | Intento fallido: `AGENT_ERROR` en `task`, sin `taskId` (D-71) |
| `READY` | Error de transporte en `SendMessage` | Intento fallido: `AGENT_UNREACHABLE` |
| `AWAITING_TASK` | `GetTask` devuelve la Task | Evaluación según su estado (tabla siguiente) |
| `AWAITING_TASK` | `GetTask` responde `TaskNotFoundError` | Intento fallido: `MISSING_ACT` en `task` (D-68) |
| `AWAITING_TASK` | Error de transporte en `GetTask` | Sigue sondeando |
| `READY` o `AWAITING_TASK` | Se supera `turnTimeoutSeconds` | `CancelTask` sin esperar resultado, si hay `taskId`; intento fallido: `TURN_TIMEOUT` (D-52) |
| Validación | Acto aceptado | Transición de sesión (sección 1) |
| Validación | Hay algún fallo no corregido | Intento fallido |
| Intento fallido | `attempt − 1 < maxRetries` | `READY` con `attempt + 1`, nuevo `messageId`, `retryReason` = fallos de este intento y `referenceTaskIds` = su `taskId`, si lo tuvo |
| Intento fallido | `attempt − 1 = maxRetries` | `CLOSING` con `ABORTED` (sección 1) |

### Evaluación del estado de la Task

| Estado de la Task | Resultado |
|---|---|
| `TASK_STATE_SUBMITTED`, `TASK_STATE_WORKING` | Sigue en `AWAITING_TASK`; nuevo sondeo tras `pollIntervalSeconds` (D-59) |
| `TASK_STATE_COMPLETED` | Validación: Artifact, sobre, encaje y coherencia, y cuerpo (pasos de validación de los CU de turno, D-72) |
| `TASK_STATE_FAILED` | Intento fallido: `TASK_FAILED` (D-23) |
| `TASK_STATE_REJECTED` | Intento fallido: `TASK_REJECTED` (D-23) |
| `TASK_STATE_CANCELED` | Intento fallido: `TASK_CANCELED` (D-60) |
| `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` o cualquier otro, incluido `TASK_STATE_UNSPECIFIED` | `CancelTask` sin esperar resultado; intento fallido: `TASK_INTERRUPTED` (D-60) |

### Orden de validación y `lastFailure`
Los fallos de un intento se ordenan así: Task, sobre, cuerpo y coherencia. Si el intento que agota los reintentos tiene varios fallos, `lastFailure` es el primero en ese orden (D-61). El encaje del cuerpo se evalúa antes de validar el cuerpo (D-72), pero eso no cambia el orden en que se clasifican los fallos.

### Criterios de diseño
- **El tiempo del turno cuenta desde justo antes de `SendMessage`, no desde que llega la Task.** Así una llamada colgada en el envío también agota el tiempo. En ese caso el fallo es `TURN_TIMEOUT` sin `taskId`, y no se envía `CancelTask` porque no hay nada que cancelar.
- **El instante de inicio se guarda al entrar en `AWAITING_TASK`.** Si el orquestador cae mientras espera, la instancia que lo retoma sigue sondeando la misma Task y calcula el tiempo restante desde ese instante. No reinicia el reloj ni crea otra Task.
- **Una caída en `READY` reenvía el mismo intento con el mismo `messageId` (D-66).** Si la caída fue justo después de enviar y antes de guardar el `taskId`, el agente puede detectar el duplicado por `messageId`. Si no lo detecta, queda en el agente una Task huérfana que nadie leerá; se acepta, porque el agente no guarda estado de sesión (D-46).
- **Un error de transporte en `GetTask` no hace fallar el intento.** La Task sigue viva en el agente; fallar aquí crearía una segunda Task mientras la primera puede estar terminando. Si el error persiste, el tiempo del turno lo corta.
- **Las respuestas tardías se descartan por construcción.** Tras un intento fallido, el orquestador no vuelve a consultar su Task; solo sondea el `taskId` en curso.
- **Un reintento sin `taskId` previo no lleva `referenceTaskIds`.** Pasa tras `AGENT_UNREACHABLE`, tras `AGENT_ERROR`, tras una respuesta con Message o tras un `TURN_TIMEOUT` durante el envío.

## 3. Qué se persiste

### Registro de sesión
Uno por sesión; se reescribe en cada transición.

| Grupo | Campos | Cuándo tiene valor |
|---|---|---|
| Identidad | `sessionId`, `requestId`, ronda, `itemId`, valores efectivos de la configuración (D-91) | Siempre |
| Concurrencia | Versión del registro, instancia que tiene el arrendamiento y su caducidad (D-63) | Siempre; el arrendamiento, mientras una instancia procesa la sesión |
| Estado | Estado de sesión (sección 1), subestado del turno (sección 2) | El subestado, solo en `NEGOTIATING` |
| Turno | `turn`, `attempt`, `messageId` del intento | Desde `NEGOTIATING` |
| A2A | URL de servicio de cada parte (D-131); `contextId` de cada parte | La URL, desde `NEGOTIATING`; el `contextId`, desde el primer turno de cada una |
| Intento en curso | `taskId` en curso, instante de inicio del intento | Solo en `AWAITING_TASK` |
| Reintento | `taskId` del intento anterior, `retryReason` | Solo si `attempt > 1` |
| Negociación | Oferta vigente y su emisor | Desde el primer `PROPOSE` aceptado |
| Acuerdo provisional | Oferta acordada, `heldUntil`, estado del envío de `AGREEMENT_HELD` a cada parte: pendiente, enviado, fallido o descartado (D-84 a D-86) | Desde la entrada en `HELD` |
| Resultado | `outcome` y, según el caso, `agreedOffer`, `withdrawnBy` y `reason`, `abortReason` y `lastFailure`, o `releaseReason`; `lastOffers` si `outcome` ≠ `AGREEMENT` (D-82); `failedPartyId` en `NOT_STARTED` (D-99) | Desde `CLOSING` o `NOT_STARTED` |
| Cierre | Estado del envío de `SESSION_CLOSE` a cada parte: pendiente, enviado o fallido | Solo en `CLOSING` y `CLOSED` |

La configuración se guarda con sus valores efectivos, ya resueltos con los valores por defecto (D-91), para que la sesión no dependa de nada que pueda cambiar durante su ejecución y la traza muestre con qué valores se ejecutó.

### Registro de petición
Uno por petición (D-83); lleva versión, como el registro de sesión (D-63). Se reescribe al abrir cada ronda y en cada transacción que saca una sesión de `CREATED` (D-97, D-101). `RESOLVE_HOLDS` no lo modifica.

| Campo | Contenido |
|---|---|
| `requestId` | UUID generado por el orquestador al aceptar el primer `OPEN_ROUND`. La creación es una escritura condicional que falla si ya existe (como D-67) |
| Comprador | `partyId` del comprador; se mantiene en todas las rondas (D-89) |
| Rondas | Por cada ronda: número, sesiones creadas con su `itemId`, sesiones de rondas anteriores que seguían en `HELD` al abrirla, es decir, las partidas mantenidas (D-79, D-83), y `taskId` de la Task de su `OPEN_ROUND` |

No guarda el presupuesto ni la corrección propuesta al usuario (D-83).

### Tasks de las peticiones del comprador (D-97)
El orquestador, como servidor A2A del coordinador, guarda en la misma base de datos las Tasks de las peticiones, con su estado, su mensaje de estado, su Artifact y la identidad autenticada que la creó (D-128). `GetTask` del coordinador se responde con la Task guardada, solo a esa identidad. Para `OPEN_ROUND`:

| Momento | Estado de la Task | Se escribe en la misma transacción que |
|---|---|---|
| Petición aceptada | `TASK_STATE_WORKING` | Las sesiones, el registro de petición y la entrada del registro de peticiones |
| Petición rechazada | `TASK_STATE_REJECTED`, con `rejections` en el mensaje de estado | La entrada del registro de peticiones |
| Última sesión de la ronda sale de `CREATED` | `TASK_STATE_COMPLETED`, con el Artifact de resultado | La transición de esa sesión y el registro de petición |

Para `RESOLVE_HOLDS`, la Task se crea directamente en estado final, sin pasar por `TASK_STATE_WORKING`, porque no queda trabajo asíncrono (D-110):

| Momento | Estado de la Task | Se escribe en la misma transacción que |
|---|---|---|
| Petición aceptada | `TASK_STATE_COMPLETED`, con el Artifact de resultado | Las sesiones resueltas y la entrada del registro de peticiones |
| Petición rechazada | `TASK_STATE_REJECTED`, con `rejections` en el mensaje de estado | La entrada del registro de peticiones |

El Artifact de resultado y el mensaje de estado de un rechazo llevan el sobre de D-104, o ninguno en el caso de D-106.

### Registros de solo añadir
Las entradas se escriben una vez y nunca se modifican.

| Registro | Una entrada por | Contenido |
|---|---|---|
| Actos aceptados | Turno resuelto | `turn`, emisor, tipo, oferta o `reason`, `taskId`, instante |
| Fallos | Fallo de un intento | `turn`, `attempt`, `taskId` si lo hay, `code`, `field`, instante |
| Coerciones | Corrección aplicada | `turn`, `attempt`, `taskId`, `code`, `field`, valor original, valor corregido, decisión aplicada (el `R-xx` de la regla, D-123), instante |
| Envíos de control | Envío de `AGREEMENT_HELD` o `SESSION_CLOSE` (D-70, D-85) | Tipo de mensaje, parte, `turn`, instante, resultado (enviado o fallido) y, según el caso, `taskId` y estado de la Task, indicación de Message o `code` del fallo (`AGENT_UNREACHABLE`, `TURN_TIMEOUT`, `AGENT_ERROR`) |
| Peticiones del comprador | `OPEN_ROUND` o `RESOLVE_HOLDS` recibida, salvo duplicados (D-89, D-98, D-109) | Tipo y `sender` si se pudieron leer (D-103), identidad autenticada (D-128), `requestId` (salvo rechazo en ronda 1 o `requestId` no válido), ronda, `messageId`, `taskId` de la Task de la petición, resultado (aceptada o rechazada), códigos de rechazo, instante. En `RESOLVE_HOLDS`, la ronda es la última abierta de la petición, y falta si el `requestId` no es válido (D-118). El par `sender` + `messageId` es único entre las entradas cuyo `sender` es su identidad (D-128) |

El registro de actos aceptados da el historial completo de la negociación; el registro de sesión solo guarda la oferta vigente. Los instantes permiten medir la latencia de los agentes. Un envío de control repetido tras una caída deja dos entradas para la misma parte. El registro de peticiones, junto con el registro de petición, explica por qué se abrió cada ronda y por qué cada sesión salió de `HELD`. Un `OPEN_ROUND` o `RESOLVE_HOLDS` duplicado no deja entrada: devuelve la Task de la petición original (D-98, D-109). La caducidad del plazo no deja entrada en ningún registro de solo añadir: queda en el resultado de la sesión y en los envíos de `SESSION_CLOSE` (D-121).

### Escrituras por transición

| Transición | Cambia en el registro de sesión | Se añade a los registros |
|---|---|---|
| `OPEN_ROUND` aceptado → `CREATED` | Registro completo de cada sesión (creación condicional, D-67) con el arrendamiento de esta instancia; registro de petición creado o con la nueva ronda (escritura condicional por versión, D-101); Task en `TASK_STATE_WORKING` (D-97) | Entrada de la petición |
| `OPEN_ROUND` rechazado | Ningún registro de sesión ni de petición; solo la Task en `TASK_STATE_REJECTED` (D-97) | Entrada de la petición con sus códigos |
| `OPEN_ROUND` duplicado | — | — (D-98) |
| `CREATED` → `NEGOTIATING` | Estado, `turn = 1`, `attempt = 1`, `messageId`; registro de petición por versión; si es la última de la ronda, Task en `TASK_STATE_COMPLETED` | — |
| `CREATED` → `NOT_STARTED` | Estado, `failedPartyId`; registro de petición por versión; si es la última de la ronda, Task en `TASK_STATE_COMPLETED` | — |
| `READY` → `AWAITING_TASK` | `taskId`, instante de inicio y `contextId` si es nuevo | — |
| Intento fallido → `READY` | `attempt + 1`, nuevo `messageId`, `retryReason`, `taskId` anterior; borra el intento en curso | Fallos del intento |
| Acto aceptado → turno siguiente | `turn + 1`, `attempt = 1`, nuevo `messageId`, oferta vigente; borra intento y reintento | Acto aceptado y sus coerciones |
| `ACCEPT` aceptado → `HELD` | Estado, oferta acordada, `heldUntil`, envíos de `AGREEMENT_HELD` pendientes; borra intento y reintento | Acto aceptado y sus coerciones |
| `COUNTEROFFER` del último turno, `WITHDRAW` o reintentos agotados → `CLOSING` | Estado, resultado con `lastOffers`, envíos de `SESSION_CLOSE` pendientes | Acto aceptado y sus coerciones, o fallos del último intento |
| Envío de `AGREEMENT_HELD` | Estado del envío a esa parte; si era el último pendiente, libera el arrendamiento (D-108) | Entrada del envío de control |
| `RESOLVE_HOLDS` aceptado → `CLOSING` | En cada sesión resuelta: estado, resultado, envíos de `AGREEMENT_HELD` pendientes a descartado, envíos de `SESSION_CLOSE` pendientes; libera el arrendamiento. Task en `TASK_STATE_COMPLETED` (D-110) | Entrada de la petición |
| `RESOLVE_HOLDS` rechazado | Ningún registro de sesión; solo la Task en `TASK_STATE_REJECTED` (D-110) | Entrada de la petición con sus códigos |
| `RESOLVE_HOLDS` duplicado | — | — (D-109) |
| Plazo vencido → `CLOSING` | Estado, resultado, envíos de `AGREEMENT_HELD` pendientes a descartado, envíos de `SESSION_CLOSE` pendientes y arrendamiento a nombre de esta instancia, en una sola escritura condicional (D-121) | — |
| Envío de `SESSION_CLOSE` | Estado del envío a esa parte; pasa a `CLOSED` cuando no queda ninguno pendiente | Entrada del envío de control (D-70) |

Cada fila se escribe de forma atómica: los registros afectados, las Tasks de las peticiones y las entradas de los registros de solo añadir en la misma transacción (D-63, D-69, D-97). `RESOLVE_HOLDS` escribe todas las sesiones de la petición en una sola transacción (D-77, D-88). La caducidad del plazo escribe cada sesión en su propia transacción (D-121).

### Concurrencia y recuperación (D-63, D-65)
- **Arrendamiento.** Una instancia solo procesa una sesión si tiene su arrendamiento. Lo renueva en cada transición, en cada sondeo y antes de cada `SendMessage` o de cada comprobación de AgentCards. Otra instancia solo toma una sesión con trabajo pendiente si su arrendamiento ha caducado o no existe.
- **Búsqueda de sesiones con trabajo pendiente (D-119, D-120).** Una sola búsqueda periódica en la base de datos, cada 5 s (constante fija en el código), encuentra las sesiones con trabajo pendiente y arrendamiento libre o caducado. Hay trabajo pendiente en `CREATED`, `NEGOTIATING` y `CLOSING`, en `HELD` con envíos de `AGREEMENT_HELD` pendientes y en `HELD` con `heldUntil` vencido según el reloj de la base de datos. La tabla del final de esta sección dice qué hace la instancia con cada una. Cubre la recuperación tras una caída, el cierre de las sesiones que `RESOLVE_HOLDS` deja sin arrendamiento (D-115) y la caducidad del plazo (D-86).
- **Versión.** Toda escritura exige que la versión no haya cambiado desde la lectura. Si cambió, la escritura se rechaza y la instancia descarta su trabajo.
- **Reloj único.** Caducidades, `heldUntil` e instantes se miden con el reloj del servidor de base de datos (D-69).
- **Peticiones duplicadas.** El par `sender` + `messageId` es único en el registro de peticiones, para `OPEN_ROUND` y `RESOLVE_HOLDS`, entre las entradas cuyo `sender` es su identidad autenticada (D-128). Si dos copias llegan a la vez, la segunda transacción falla y se devuelve la Task de la primera (D-98, D-109).
- **`OPEN_ROUND` concurrentes de la misma petición.** La escritura condicional por versión del registro de petición decide cuál entra. El otro relee y vuelve a evaluar la petición, incluidos el número de ronda y `ROUND_CONFLICT` (D-101).
- **`RESOLVE_HOLDS` no necesita el arrendamiento.** La decisión llega de fuera, no de un trabajo en curso de la sesión. Escribe cada sesión de forma condicional por versión; si alguna versión cambió, relee y vuelve a evaluar, y si alguna sesión ya no está en `HELD`, o tiene `heldUntil` vencido según el reloj de la base de datos, rechaza la petición con `NOT_HELD` (D-89, D-111). Libera el arrendamiento de las sesiones resueltas, para que cualquier instancia las tome para el cierre sin esperar a que caduque. Tras confirmar la transacción, la misma instancia intenta tomarlo y lanza el envío de `SESSION_CLOSE`; si no lo consigue, las recoge la búsqueda de sesiones con trabajo pendiente (D-115, D-119). Una instancia que estaba enviando `AGREEMENT_HELD` a una de esas sesiones verá rechazada su escritura y descartará su trabajo; ese envío queda sin entrada en el registro de control, lo que se acepta porque `AGREEMENT_HELD` no altera el estado (D-85).
- **Envíos de `AGREEMENT_HELD`.** Antes de enviar, al renovar el arrendamiento, se comprueba si `heldUntil` ha vencido; si ha vencido, no se envía nada y la misma instancia aplica la caducidad sin soltar el arrendamiento (D-107). La transacción que marca el último envío pendiente libera el arrendamiento, para que la búsqueda no tenga que esperar a que caduque para procesar la caducidad (D-108).
- **Caducidad del plazo (D-86, D-121, D-122).** La búsqueda encuentra las sesiones en `HELD` con `heldUntil` vencido y arrendamiento libre o caducado. La instancia aplica la caducidad con una sola escritura condicional por versión, que comprueba con el reloj de la base de datos que la sesión sigue en `HELD`, que `heldUntil` ha vencido y que el arrendamiento está libre o caducado (o es suyo, si llega desde un envío de `AGREEMENT_HELD`, D-107), y que en la misma transacción pasa la sesión a `CLOSING` y pone el arrendamiento a su nombre. Si alguna condición falla, no escribe nada y descarta su trabajo: si compite con un `RESOLVE_HOLDS` u otra instancia, la versión decide cuál se aplica. Tras confirmar, la misma instancia envía `SESSION_CLOSE` sin soltar el arrendamiento; si cae, otra la retoma en `CLOSING` cuando el arrendamiento caduca.
- **Qué hace la instancia que toma una sesión**, según dónde quedó:

| Estado guardado | Acción al tomarla |
|---|---|
| `CREATED` | Repite la comprobación de AgentCards (D-99). Si es la última sesión de la ronda en salir de `CREATED`, completa la Task del `OPEN_ROUND` (D-97) |
| `READY` | Reenvía el intento con el `messageId` guardado |
| `AWAITING_TASK` | Sigue sondeando el `taskId` guardado con el tiempo restante desde el instante de inicio |
| `HELD` con `heldUntil` vencido, tenga o no envíos de `AGREEMENT_HELD` pendientes | Pasa a `CLOSING` con `RELEASED` y `releaseReason = HOLD_EXPIRED`, en la misma escritura que toma el arrendamiento; los envíos pendientes se descartan sin enviarse. Después envía `SESSION_CLOSE` (CU-07, D-107, D-121, D-122) |
| `HELD` con envíos de `AGREEMENT_HELD` pendientes y `heldUntil` sin vencer | Envía `AGREEMENT_HELD` a las partes que siguen como pendientes (CU-05) |
| `HELD` sin envíos pendientes ni plazo vencido | Nada: no lo selecciona la búsqueda. Espera a `RESOLVE_HOLDS` o a la caducidad |
| `CLOSING` | Envía `SESSION_CLOSE` a las partes que siguen como pendientes (CU-02) |

## 4. Envíos de control sin acto

`AGREEMENT_HELD` (D-85, CU-05) y `SESSION_CLOSE` (D-55, D-64, CU-02) se envían con las mismas reglas:

| Aspecto | Regla |
|---|---|
| Destinatarios | Las dos partes, siempre (D-49) |
| Parte sin `contextId` | Se le envía sin `contextId`. Solo pasa con `SESSION_CLOSE` si el cierre llega en el turno 1: la parte que no abre nunca tuvo turno. En `AGREEMENT_HELD` no pasa, porque el `ACCEPT` solo es válido en un turno ≥ 2 |
| Modo de envío | `SendMessage` con `returnImmediately = true`, sin sondeo. Los dos envíos se lanzan a la vez, tras renovar el arrendamiento |
| `messageId` | Nuevo en cada envío; no se persiste |
| Respuesta | Una Task en cualquier estado o un Message marcan el envío como enviado. Se anota en el registro de envíos de control el `taskId` y el estado de la Task, o que llegó un Message, y no se valida (D-49, D-70). No se envía `CancelTask` |
| Fallo | Error de transporte (`AGENT_UNREACHABLE`), sin respuesta en `turnTimeoutSeconds` (`TURN_TIMEOUT`) o error A2A (`AGENT_ERROR`, D-71): envío marcado como fallido, con el código en el registro de envíos de control (D-70) |
| Intentos | Uno por parte, sin reintento |
| Orden | Envíos independientes; el fallo de uno no impide el otro. Las marcas de los dos envíos se escriben una tras otra dentro de la instancia (D-63) |
| `sessionId` y `sender` | Los del estado, y `ORCHESTRATOR` |
| Recuperación | Solo se envía a las partes que siguen como pendientes |

Diferencias entre los dos mensajes:

| Aspecto | `AGREEMENT_HELD` | `SESSION_CLOSE` |
|---|---|---|
| Cuándo | Al entrar en `HELD`, si `heldUntil` no ha vencido (D-107) | Al entrar en `CLOSING` |
| `turn` en el sobre | El del `ACCEPT` | El del turno que provocó el cierre; si viene de `HELD`, el del `ACCEPT` |
| Si la sesión cambia de estado con envíos pendientes | Se marcan como descartados y no se envían | — (`CLOSING` solo sale a `CLOSED`) |
| Efecto en la sesión | Ninguno; la sesión sigue en `HELD`. Al marcar el último envío se libera el arrendamiento (D-108) | Pasa a `CLOSED` cuando no queda ningún envío pendiente |

## 5. Restricciones sobre la configuración

| Parámetro | Restricción | Motivo |
|---|---|---|
| `maxRetries` | ≥ 0, sin mínimo adicional | Con 0, el primer fallo agota los reintentos; la sección 2 lo cubre sin caso especial |
| `maxTurns` | ≥ 2 (D-56) | La sección 1 se apoya en que el turno 1 nunca es el último |
| `pollIntervalSeconds` | > 0 y < `turnTimeoutSeconds` (D-59) | Que quepa al menos un sondeo antes de agotar el tiempo |
| `turnTimeoutSeconds` | > 0, sin mínimo adicional | Un valor bajo solo provoca `TURN_TIMEOUT`, o `NOT_STARTED` si no da tiempo a obtener una AgentCard (D-99); no rompe la máquina |
| `holdTimeoutSeconds` | > 0 (D-86) | Un valor bajo solo libera antes los acuerdos provisionales |

Las restricciones se comprueban sobre los valores efectivos (D-91). La estructura completa de la configuración está en `configuracion-sesion.md`. El periodo de la búsqueda de sesiones con trabajo pendiente no es un parámetro de la configuración (D-120).

### Duración del arrendamiento (D-65)
El arrendamiento dura `turnTimeoutSeconds + pollIntervalSeconds` y no es configurable. El intervalo más largo sin renovarlo es una llamada a `SendMessage` o la obtención de una AgentCard, acotadas por `turnTimeoutSeconds` en los turnos, en cada envío de control y en la comprobación de AgentCards (D-99); el segundo término es el margen. Con los valores por defecto son 61 s. El retraso máximo en retomar una sesión tras una caída es la duración del arrendamiento más el periodo de la búsqueda: 66 s con los valores por defecto (D-120).

## 6. Preguntas abiertas
- Fuera del orquestador: los agentes de las partes necesitan un almacén persistente de Tasks para que el sondeo sobreviva a sus reinicios y para detectar duplicados por `messageId` (D-66). Se decide al diseñar los agentes.
- Si falla el envío de `AGREEMENT_HELD` a un vendedor, este no sabe que debe reservar y puede vender a otro antes de la confirmación. Opciones a valorar: reintentar el envío, pedir acuse de recibo o permitir al vendedor indicar que ya no está disponible al confirmar. La última cambiaría el significado de un acuerdo (D-85). Se decide al diseñar los agentes.

Casos de uso diseñados: CU-01 a CU-07. Con ellos queda cubierto todo el ciclo de vida de una sesión y de una petición en el orquestador.

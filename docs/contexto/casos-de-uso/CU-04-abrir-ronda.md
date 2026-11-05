# CU-04 · Aceptar `OPEN_ROUND` y arrancar la ronda

| Campo | Contenido |
|---|---|
| Actor principal | Coordinador del comprador (cliente A2A del orquestador, D-80, D-87) |
| Objetivo | Validar la petición, crear las sesiones de la ronda, comprobar sus AgentCards y devolver al coordinador qué sesiones han empezado |
| Precondiciones | El orquestador publica su AgentCard con `urn:tfm:negociacion:v1` y `required = true` (D-87). A partir de la ronda 2, existe el registro de la petición (D-83). El modo de validación no interviene: las peticiones no se autocorrigen (D-89) |
| Disparador | `SendMessage` del coordinador al orquestador con un `OPEN_ROUND` |
| Decisiones y reglas | D-04, D-18, D-19, D-25, D-29, D-30, D-50, D-63, D-65–D-67, D-69, D-79, D-83, D-87–D-94, D-97–D-106. AC-04-01 a AC-04-27 |

## Flujo principal
1. El orquestador recibe el Message con la cabecera `A2A-Extensions`, la URI en `extensions`, el sobre en `metadata["urn:tfm:negociacion:v1"]` y una Part `data` de `mediaType` de petición (D-19, D-92, D-103). Lee `sender` del sobre y el `messageId`.
2. Busca en el registro de peticiones una entrada con el mismo `sender` y `messageId`. No existe (D-98).
3. Valida el sobre y el cuerpo: `type = OPEN_ROUND`, `sender`, sin `sessionId` ni `turn`, campos obligatorios, tipos, enumerados y ausencia de campos no definidos. Recoge todos los fallos (D-89, D-93, D-101).
4. Valida la petición:
   - Ronda 1: sin `requestId`.
   - Ronda ≥ 2: el `requestId` existe y su comprador es el `sender` (`UNKNOWN_REQUEST`, D-102).
   - Ronda ≥ 2: ninguna sesión de la petición está en `CREATED` o `NEGOTIATING`. Ningún `itemId` coincide con el de una sesión de la petición en `HELD`, ni con el de una en `CLOSING` o `CLOSED` con `AGREEMENT` (`ROUND_CONFLICT`, D-100, D-105).
5. Valida las configuraciones:
   - resuelve los valores efectivos con los valores por defecto y comprueba sus restricciones (`INVALID_CONFIG`, D-90, D-91);
   - comprueba que los `itemId` son distintos y que el `partyId` del `BUYER` es el mismo en todas las sesiones (`INVALID_CONFIG`);
   - si el `BUYER` es el mismo en todas, comprueba que coincide con el `sender` (`NOT_AUTHORIZED` en `envelope.sender`, D-102).
6. Sin fallos, en una sola transacción:
   - Ronda 1: crea el registro de petición con un `requestId` nuevo (UUID, creación condicional) y el comprador. Ronda ≥ 2: añade la ronda siguiente al registro de petición con escritura condicional por versión.
   - Anota en la ronda las sesiones creadas con su `itemId` y las sesiones de la petición que siguen en `HELD` (partidas mantenidas, D-79, D-83).
   - Crea cada sesión en `CREATED` con su `sessionId` (UUID, creación condicional, D-67), `requestId`, ronda, `itemId`, los valores efectivos de su configuración y el arrendamiento a nombre de esta instancia (D-63, D-65).
   - Crea la Task de la petición en `TASK_STATE_WORKING` (D-97).
   - Añade la entrada aceptada al registro de peticiones con su `taskId`, `sender` y `messageId`.
7. Responde a `SendMessage` con la Task según A2A: enseguida si el coordinador pidió `returnImmediately = true`, o al completarse si no.
8. Para cada sesión: renueva el arrendamiento y obtiene las AgentCards de las dos partes en paralelo, con un intento por parte y `turnTimeoutSeconds` como tiempo máximo (D-99).
9. Si las dos declaran la extensión con `required = true`: en una transacción, la sesión pasa a `NEGOTIATING` (`READY`) con `turn = 1`, `attempt = 1` y un `messageId` nuevo (D-66), lo que dispara CU-01.
10. La transacción que saca de `CREATED` la última sesión de la ronda completa la Task con el Artifact de resultado: `requestId`, `round` y `sessions` con `{itemId, sessionId, started, failedPartyId}` (D-92, D-94, D-97). El Artifact lleva la URI en `extensions` y un sobre con `type = OPEN_ROUND`, `sender = ORCHESTRATOR` y sin `sessionId` ni `turn` (D-104). Cada transacción de salida de `CREATED` escribe también el registro de petición de forma condicional por versión, para que dos instancias no crean a la vez que la otra sesión sigue en `CREATED`.

## Flujos alternativos
- **1a.** El Message no tiene forma de petición → no se valida el sobre ni el cuerpo; se rechaza como en 3a con un solo fallo, `INVALID_MESSAGE` en `message` (D-103). La entrada del registro lleva el `type` y el `sender` solo si se pudieron leer. Si no se pudo leer un `type` de petición válido, el mensaje de estado del rechazo va sin sobre, solo con `rejections` y la URI en `extensions` (D-106). Los casos son:
  - falta la cabecera o la URI en `extensions`;
  - falta el sobre;
  - no hay exactamente una Part `data` con el `mediaType` de petición.
- **2a.** Ya existe una entrada con el mismo `sender` y `messageId` → se devuelve la Task de esa petición en su estado actual. No se escribe nada (D-98).
- **2b.** El sobre no permite leer `sender` → no se comprueba el duplicado; la validación del paso 3 lo rechaza.
- **3a / 4a / 5a.** Hay al menos un fallo → en una transacción se crea la Task en `TASK_STATE_REJECTED`, cuyo mensaje de estado lleva `rejections` con todos los fallos ordenados por ruta, la URI en `extensions` y un sobre con `type = OPEN_ROUND`, `sender = ORCHESTRATOR` y sin `sessionId` ni `turn` (D-104). Se añade la entrada rechazada, con sus códigos, al registro de peticiones. No se crea ni modifica ningún registro de petición ni sesión (D-89, D-97, D-101). Se responde con esa Task.
- **6a.** La escritura condicional del registro de petición falla porque otro `OPEN_ROUND` de la misma petición se adelantó → se descarta la transacción, se relee y se vuelve al paso 4. Puede acabar en rechazo con `ROUND_CONFLICT` (D-101).
- **6b.** La entrada del registro de peticiones choca con otra de igual `sender` y `messageId`, porque un duplicado llegó a la vez → se descarta la transacción y se continúa como en 2a (D-98).
- **6c.** Un `sessionId` o `requestId` generado ya existe → se genera otro (D-67).
- **8a.** La AgentCard de alguna parte no se puede obtener (error de transporte, tiempo superado o respuesta no interpretable) o no declara la extensión con `required = true` → en una transacción, la sesión pasa a `NOT_STARTED` con `failedPartyId`. Si fallan las dos partes, `failedPartyId` es la primera según el orden de `parties` (D-25, D-99). Se continúa en el paso 10.
- **9a.** Una escritura de sesión se rechaza porque la versión cambió → la instancia descarta su trabajo sobre esa sesión; otra la ha tomado (D-63).
- **10a.** Todas las sesiones de la ronda quedan en `NOT_STARTED` → la Task se completa igualmente, con `started = false` en todas. La ronda queda en el registro de petición.
- **C · Caída del orquestador.**
  - Antes del paso 6: no queda nada escrito. Si el coordinador reenvía la petición con el mismo `messageId`, se procesa como nueva.
  - Después del paso 6: las sesiones que siguen en `CREATED` las toma otra instancia cuando caduca su arrendamiento y repite la comprobación de AgentCards (`maquina-estados.md`, sección 3). La instancia que saca la última sesión de `CREATED` completa la Task.
  - El coordinador puede consultar la Task con `GetTask` en cualquier momento: se responde con la Task guardada (D-97).

## Postcondiciones
- Estado final de las sesiones: cada sesión de la ronda en `NEGOTIATING` (`READY`, turno 1) o en `NOT_STARTED`; ninguna en `CREATED`. Si la petición se rechaza, no hay sesiones.
- Qué queda en el estado externalizado:
  - el registro de petición, con la ronda, sus sesiones y las partidas mantenidas;
  - por sesión, su identidad, los valores efectivos de su configuración y, si no empezó, `failedPartyId`;
  - la Task de la petición en `TASK_STATE_COMPLETED` con el Artifact de resultado, o en `TASK_STATE_REJECTED` con `rejections`.
- Qué queda registrado: una entrada en el registro de peticiones con tipo, `requestId` (salvo rechazo en ronda 1), ronda, `sender`, `messageId`, `taskId`, resultado, códigos de rechazo e instante. Nada en los registros de actos, fallos, coerciones ni envíos de control.

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-04-01 · Un `OPEN_ROUND` válido de ronda 1 crea un registro de petición con un `requestId` UUID nuevo, la ronda 1 y una sesión en `CREATED` por entrada de `sessions`, con su `itemId` y un `sessionId` UUID.
- [ ] AC-04-02 · Cada sesión guarda los valores efectivos de su configuración: un parámetro ausente se guarda con su valor por defecto (D-91).
- [ ] AC-04-03 · La creación de las sesiones, del registro de petición, de la Task en `TASK_STATE_WORKING` y de la entrada del registro de peticiones ocurre en una sola transacción.
- [ ] AC-04-04 · Un `OPEN_ROUND` válido de ronda ≥ 2 asigna el número de ronda siguiente y anota como mantenidas las sesiones de la petición que siguen en `HELD`.
- [ ] AC-04-05 · Si las dos AgentCards declaran la extensión con `required = true`, la sesión pasa a `NEGOTIATING` (`READY`) con `turn = 1`, `attempt = 1` y un `messageId` guardado.
- [ ] AC-04-06 · Si una AgentCard no declara la extensión, no se puede obtener o no responde en `turnTimeoutSeconds`, la sesión pasa a `NOT_STARTED` con el `failedPartyId` de esa parte y no se envía `SESSION_CLOSE`.
- [ ] AC-04-07 · Si fallan las dos AgentCards, `failedPartyId` es la primera parte según el orden de `parties`.
- [ ] AC-04-08 · Las AgentCards de cada sesión se obtienen con un solo intento por parte, aunque la misma parte aparezca en otras sesiones de la ronda.
- [ ] AC-04-09 · La Task pasa a `TASK_STATE_COMPLETED` solo cuando ninguna sesión de la ronda sigue en `CREATED`, y su Artifact lleva `requestId`, `round` y una entrada por sesión con `started` y, si es falso, `failedPartyId`.
- [ ] AC-04-10 · Si las sesiones salen de `CREATED` en instancias distintas a la vez, la Task se completa exactamente una vez.
- [ ] AC-04-11 · Una petición con fallos crea la Task en `TASK_STATE_REJECTED` con todos los fallos en `rejections`, ordenados por ruta, no crea sesiones ni modifica el registro de petición y añade la entrada rechazada con sus códigos.
- [ ] AC-04-12 · Una configuración que incumple una restricción, incluida una entre parámetros que solo aparece con los valores efectivos, rechaza la ronda entera con `INVALID_CONFIG` en la ruta `body.sessions.<i>.config.<campo>`.
- [ ] AC-04-13 · Un `itemId` repetido en la ronda, o un `partyId` del `BUYER` distinto entre sesiones, rechaza con `INVALID_CONFIG`, sin añadir `NOT_AUTHORIZED`.
- [ ] AC-04-14 · Un `requestId` desconocido o de otro comprador rechaza con `UNKNOWN_REQUEST`.
- [ ] AC-04-15 · Un `OPEN_ROUND` con `requestId` cuando alguna sesión de la petición está en `CREATED` o `NEGOTIATING` rechaza con `ROUND_CONFLICT` en `body.requestId`.
- [ ] AC-04-16 · Un `OPEN_ROUND` con un `itemId` igual al de una sesión de la petición en `HELD` rechaza con `ROUND_CONFLICT` en `body.sessions.<i>.itemId`.
- [ ] AC-04-17 · Un sobre con `sessionId` o `turn`, o con un campo no definido, rechaza con `UNKNOWN_FIELD`; nada se corrige en ningún modo.
- [ ] AC-04-18 · Un `OPEN_ROUND` con el mismo `sender` y `messageId` que uno anterior devuelve la Task original en su estado actual y no escribe nada, también si el original fue rechazado.
- [ ] AC-04-19 · Dos copias del mismo `OPEN_ROUND` recibidas a la vez crean una sola ronda y las dos respuestas llevan la misma Task.
- [ ] AC-04-20 · Dos `OPEN_ROUND` distintos de la misma petición recibidos a la vez no crean dos rondas con el mismo número: el segundo se reevalúa y, si la primera ronda sigue en curso, se rechaza con `ROUND_CONFLICT`.
- [ ] AC-04-21 · Si el orquestador cae con sesiones en `CREATED`, la instancia que las toma repite la comprobación de AgentCards y completa la Task cuando sale la última.
- [ ] AC-04-22 · `GetTask` del coordinador devuelve la Task guardada en su estado actual, también tras una caída de la instancia que aceptó la petición.
- [ ] AC-04-23 · Si el `partyId` del `BUYER` es el mismo en todas las sesiones pero distinto del `sender`, la petición se rechaza con `NOT_AUTHORIZED` en `envelope.sender`, en cualquier ronda.
- [ ] AC-04-24 · Un Message sin cabecera `A2A-Extensions`, sin la URI en `extensions`, sin sobre, sin Part `data`, con varias Parts o con otro `mediaType` se rechaza con un solo fallo, `INVALID_MESSAGE` en `message`, y queda en el registro de peticiones.
- [ ] AC-04-25 · El Artifact de resultado y el mensaje de estado de un rechazo llevan la URI en `extensions` y un sobre con `type = OPEN_ROUND`, `sender = ORCHESTRATOR` y sin `sessionId` ni `turn`.
- [ ] AC-04-26 · Un `OPEN_ROUND` con un `itemId` igual al de una sesión de la petición en `CLOSING` o `CLOSED` con `AGREEMENT` rechaza con `ROUND_CONFLICT` en `body.sessions.<i>.itemId`.
- [ ] AC-04-27 · Un rechazo por `INVALID_MESSAGE` en el que no se pudo leer un `type` de petición válido lleva el mensaje de estado sin sobre, solo con `rejections` y la URI en `extensions`. Si el `type` se pudo leer, lleva el sobre de AC-04-25.

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
Ninguna.

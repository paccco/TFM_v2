# CU-06 · Aplicar `RESOLVE_HOLDS`

| Campo | Contenido |
|---|---|
| Actor principal | Coordinador del comprador (cliente A2A del orquestador, D-80, D-87) |
| Objetivo | Confirmar o liberar, en una sola transacción, los acuerdos provisionales de una petición que indica el coordinador, y llevar cada sesión resuelta a `CLOSING` |
| Precondiciones | El orquestador publica su AgentCard con `urn:tfm:negociacion:v1` y `required = true` (D-87). Existe el registro de la petición (D-83). No hace falta el arrendamiento de las sesiones (D-96). El modo de validación no interviene: las peticiones no se autocorrigen (D-89) |
| Disparador | `SendMessage` del coordinador al orquestador con un `RESOLVE_HOLDS` |
| Decisiones y reglas | D-19, D-50, D-63, D-69, D-77, D-82, D-84–D-89, D-92, D-93, D-95–D-98, D-101–D-104, D-106, D-109–D-118. AC-06-01 a AC-06-24 |

## Flujo principal
1. El orquestador recibe el Message con la cabecera `A2A-Extensions`, la URI en `extensions`, el sobre en `metadata["urn:tfm:negociacion:v1"]` y una Part `data` con el `mediaType` de petición (D-19, D-92, D-103). Lee `sender` del sobre y el `messageId`.
2. Busca en el registro de peticiones una entrada con el mismo `sender` y `messageId`. No existe (D-109).
3. Valida el sobre y el cuerpo: `type = RESOLVE_HOLDS`, `sender`, sin `sessionId` ni `turn`, `requestId`, `confirm` y `release` presentes con su tipo y sin campos no definidos. Recoge todos los fallos (D-89, D-93, D-101).
4. Valida la petición:
   - el `requestId` existe y su comprador es el `sender` (`UNKNOWN_REQUEST`, D-113);
   - las dos listas no están vacías a la vez (`INVALID_REQUEST` en `body`, D-116);
   - ningún `sessionId` aparece en las dos listas (`INVALID_REQUEST` en cada aparición, D-116);
   - ningún `sessionId` se repite dentro de una misma lista (`INVALID_REQUEST` en cada aparición tras la primera, D-114). Si una sesión está a la vez repetida y en las dos listas, se marcan todas sus apariciones con un fallo por ruta (D-116).
5. Si `requestId` no tiene ningún fallo (D-117), lee las sesiones de las dos listas y, con el reloj de la base de datos, comprueba que cada una pertenece a la petición, está en `HELD` y tiene `heldUntil` sin vencer (`NOT_HELD` en la ruta de su `sessionId`, sin estado, D-93, D-111, D-112).
6. Sin fallos, en una sola transacción, con escritura condicional por versión de cada sesión (D-96):
   - cada sesión de `confirm` pasa a `CLOSING` con `outcome = AGREEMENT` y `agreedOffer` igual a la oferta acordada;
   - cada sesión de `release` pasa a `CLOSING` con `outcome = RELEASED`, `releaseReason = BUYER_DECISION` y `lastOffers` (D-82, D-86);
   - en todas: los envíos de `AGREEMENT_HELD` pendientes pasan a descartados (D-95), los envíos de `SESSION_CLOSE` a las dos partes quedan pendientes y se libera el arrendamiento, si lo hay (D-96);
   - se crea la Task de la petición en `TASK_STATE_COMPLETED` con el Artifact de resultado: `requestId`, `confirmed` y `released` (D-92, D-110). El Artifact lleva la URI en `extensions` y un sobre con `type = RESOLVE_HOLDS`, `sender = ORCHESTRATOR` y sin `sessionId` ni `turn` (D-104);
   - se añade la entrada aceptada al registro de peticiones con su `taskId`, `sender`, `messageId` y, como ronda, la última ronda abierta de la petición (D-118).
7. Responde a `SendMessage` con la Task, ya en estado final.
8. Para cada sesión resuelta, la misma instancia intenta tomar el arrendamiento y lanza CU-02 (D-115).

## Flujos alternativos
- **1a.** El Message no tiene forma de petición → no se valida el sobre ni el cuerpo; se rechaza como en 3a con un solo fallo, `INVALID_MESSAGE` en `message` (D-103). La entrada del registro lleva el `type` y el `sender` solo si se pudieron leer. Si no se pudo leer un `type` de petición válido, el mensaje de estado del rechazo va sin sobre, solo con `rejections` y la URI en `extensions` (D-106).
- **2a.** Ya existe una entrada con el mismo `sender` y `messageId` → se devuelve la Task de esa petición en su estado actual. No se escribe nada (D-109).
- **2b.** El sobre no permite leer `sender` → no se comprueba el duplicado; la validación del paso 3 lo rechaza.
- **3a / 4a / 5a.** Hay al menos un fallo → en una transacción se crea la Task en `TASK_STATE_REJECTED`, cuyo mensaje de estado lleva `rejections` con todos los fallos ordenados por ruta, la URI en `extensions` y un sobre con `type = RESOLVE_HOLDS`, `sender = ORCHESTRATOR` y sin `sessionId` ni `turn` (D-104, D-110). Se añade la entrada rechazada, con sus códigos, al registro de peticiones. No se modifica ninguna sesión: una sesión con el plazo vencido sigue en `HELD` hasta que la procese CU-07 (D-89, D-111). Se responde con esa Task.
- **6a.** La escritura de alguna sesión se rechaza porque la versión cambió → se descarta la transacción entera, se releen las sesiones y se vuelve al paso 5 (D-96). Pasa si la caducidad del plazo resolvió antes alguna sesión, o si una instancia marcó un envío de `AGREEMENT_HELD`. En el primer caso se acaba en rechazo con `NOT_HELD`. En el segundo, la instancia que enviaba ve rechazada su escritura más tarde y descarta su trabajo (CU-05, 5d).
- **6b.** La entrada del registro de peticiones choca con otra de igual `sender` y `messageId`, porque un duplicado llegó a la vez → se descarta la transacción y se continúa como en 2a (D-109).
- **8a.** Otra instancia toma el arrendamiento antes, o la instancia cae tras el paso 6 → la sesión la recoge la búsqueda de sesiones con trabajo pendiente y sin arrendamiento, y sigue por CU-02 (D-115).
- **C · Caída del orquestador.**
  - Antes del paso 6: no queda nada escrito. Si el coordinador reenvía la petición con el mismo `messageId`, se procesa como nueva.
  - Después del paso 6: el resultado ya está guardado. Un reenvío con el mismo `messageId` devuelve la Task completada (2a), y `GetTask` del coordinador también (D-97).

## Postcondiciones
- Estado final de las sesiones: cada sesión de `confirm` en `CLOSING` con `AGREEMENT`, y cada sesión de `release` en `CLOSING` con `RELEASED` y `BUYER_DECISION`. Las sesiones de la petición que no aparecen en ninguna lista no cambian. Si la petición se rechaza, ninguna sesión cambia.
- Qué queda en el estado externalizado:
  - en cada sesión resuelta: el resultado, los envíos de `AGREEMENT_HELD` pendientes como descartados, los envíos de `SESSION_CLOSE` pendientes y ningún arrendamiento (o el que tome la instancia para CU-02);
  - la Task de la petición en `TASK_STATE_COMPLETED` con el Artifact de resultado, o en `TASK_STATE_REJECTED` con `rejections`;
  - el registro de petición, sin cambios.
- Qué queda registrado: una entrada en el registro de peticiones con tipo, `requestId` y ronda (la última abierta de la petición, D-118) si el `requestId` es válido, `sender`, `messageId`, `taskId`, resultado, códigos de rechazo e instante. Nada en los registros de actos, fallos, coerciones ni envíos de control.

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-06-01 · Un `RESOLVE_HOLDS` válido lleva cada sesión de `confirm` a `CLOSING` con `outcome = AGREEMENT` y `agreedOffer` igual a la oferta acordada.
- [ ] AC-06-02 · Un `RESOLVE_HOLDS` válido lleva cada sesión de `release` a `CLOSING` con `outcome = RELEASED`, `releaseReason = BUYER_DECISION` y `lastOffers`.
- [ ] AC-06-03 · Las sesiones resueltas, la Task en `TASK_STATE_COMPLETED` y la entrada del registro de peticiones se escriben en una sola transacción; si cualquier escritura falla, no se aplica ninguna.
- [ ] AC-06-04 · En cada sesión resuelta, los envíos de `AGREEMENT_HELD` pendientes quedan como descartados, los de `SESSION_CLOSE` a las dos partes quedan pendientes y el arrendamiento se libera.
- [ ] AC-06-05 · Las sesiones de la petición que no aparecen en ninguna lista siguen en `HELD` sin cambios.
- [ ] AC-06-06 · La Task se crea directamente en `TASK_STATE_COMPLETED`, nunca en `TASK_STATE_WORKING`, con un Artifact que lleva `requestId`, `confirmed` y `released`.
- [ ] AC-06-07 · El Artifact de resultado y el mensaje de estado de un rechazo llevan la URI en `extensions` y un sobre con `type = RESOLVE_HOLDS`, `sender = ORCHESTRATOR` y sin `sessionId` ni `turn`.
- [ ] AC-06-08 · Una petición con fallos crea la Task en `TASK_STATE_REJECTED` con todos los fallos en `rejections`, ordenados por ruta, no modifica ninguna sesión y añade la entrada rechazada con sus códigos.
- [ ] AC-06-09 · Si alguna sesión de las listas no está en `HELD`, la petición entera se rechaza con `NOT_HELD` en la ruta de cada `sessionId` afectado, y las demás sesiones no cambian.
- [ ] AC-06-10 · Un `sessionId` de otra petición, o inexistente, se rechaza con `NOT_HELD` en su ruta, con la misma forma que una sesión de la petición que no está en `HELD`.
- [ ] AC-06-11 · Una sesión en `HELD` con `heldUntil` vencido según el reloj de la base de datos rechaza la petición con `NOT_HELD`, y la sesión sigue en `HELD`.
- [ ] AC-06-12 · Los elementos de `rejections` con `NOT_HELD` llevan solo `code` y `field`, sin el estado de la sesión.
- [ ] AC-06-13 · Un `requestId` inexistente, o cuyo comprador no es el `sender`, se rechaza con `UNKNOWN_REQUEST` en `body.requestId`; nunca se usa `NOT_AUTHORIZED`.
- [ ] AC-06-14 · Las dos listas vacías se rechazan con un solo fallo `INVALID_REQUEST` en `body`. Un `sessionId` en las dos listas se rechaza con `INVALID_REQUEST` en cada una de sus apariciones.
- [ ] AC-06-15 · Un `sessionId` repetido dentro de una misma lista se rechaza con `INVALID_REQUEST` en la ruta de cada aparición después de la primera.
- [ ] AC-06-16 · Un sobre con `sessionId` o `turn`, o con un campo no definido, se rechaza con `UNKNOWN_FIELD`; nada se corrige en ningún modo.
- [ ] AC-06-17 · Un `RESOLVE_HOLDS` con el mismo `sender` y `messageId` que uno anterior devuelve la Task original en su estado actual y no escribe nada, también si el original fue rechazado.
- [ ] AC-06-18 · Dos copias del mismo `RESOLVE_HOLDS` recibidas a la vez resuelven las sesiones una sola vez, y las dos respuestas llevan la misma Task.
- [ ] AC-06-19 · Si la caducidad del plazo cierra una sesión mientras se evalúa la petición, la escritura por versión falla, se relee y la petición se rechaza con `NOT_HELD`; la sesión conserva `RELEASED` con `HOLD_EXPIRED`.
- [ ] AC-06-20 · `RESOLVE_HOLDS` se aplica aunque otra instancia tenga el arrendamiento de una sesión mientras envía `AGREEMENT_HELD`; esa instancia ve rechazada su escritura y no vuelve a enviar.
- [ ] AC-06-21 · Tras aceptar la petición, la misma instancia toma el arrendamiento de las sesiones resueltas y lanza CU-02; si cae antes, otra instancia las toma sin esperar a ninguna caducidad de arrendamiento.
- [ ] AC-06-22 · Un `sessionId` repetido en una lista y presente también en la otra genera un fallo `INVALID_REQUEST` por cada aparición, sin rutas duplicadas en `rejections`.
- [ ] AC-06-23 · Si `requestId` falta, tiene tipo incorrecto o da `UNKNOWN_REQUEST`, `rejections` no lleva ningún `NOT_HELD`, pero sí los `INVALID_REQUEST` que correspondan.
- [ ] AC-06-24 · La entrada del registro de peticiones lleva como ronda la última ronda abierta de la petición, también si resuelve sesiones de rondas anteriores; si el `requestId` falla o no se pudo leer, no lleva ronda ni `requestId`.

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
Ninguna.

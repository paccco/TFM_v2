# CU-03 · Procesar un turno de negociación (turno ≥ 2)

| Campo | Contenido |
|---|---|
| Actor principal | Orquestador |
| Objetivo | Obtener de la parte con turno un acto válido para un turno ≥ 2 y registrarlo en el estado externalizado |
| Precondiciones | Sesión en `NEGOTIATING`, subestado `READY` (`maquina-estados.md`), con `2 ≤ turn ≤ maxTurns`, `attempt = 1` y `messageId` del intento guardado (D-66). Oferta vigente guardada, emitida por la otra parte. `contextId` de la parte con turno solo si ya tuvo algún turno: en el turno 2 no lo tiene. Modo de validación fijado (D-11). El orquestador tiene el arrendamiento de la sesión (D-63) |
| Disparador | Paso de la sesión al turno siguiente en `READY` tras un `PROPOSE` o un `COUNTEROFFER` aceptado (CU-01 o este mismo CU) |
| Decisiones y reglas | D-07, D-08, D-11, D-17–D-20, D-22, D-23, D-26–D-28, D-31–D-39, D-41–D-48, D-50–D-54, D-56–D-63, D-65, D-66, D-68, D-71–D-74, D-77, D-82, D-84–D-86. AC-03-01 a AC-03-20 |

## Flujo principal
1. El orquestador lee del estado externalizado la sesión, `turn`, la parte con turno (por paridad: la que abre tiene los turnos impares, D-33), su papel, los términos fijos, `maxTurns`, `attempt = 1`, el `messageId` del intento, el `contextId` de esa parte si lo tiene y la oferta vigente.
2. Construye un `TURN_REQUEST`:
   - Sobre: `sessionId`, `turn`, `type = TURN_REQUEST`, `sender = ORCHESTRATOR`.
   - Cuerpo: `role`, `fixedTerms`, `allowedActs = [COUNTEROFFER, ACCEPT, WITHDRAW]`, `turnsLeft = maxTurns − turn + 1`, `lastOffer` igual a la oferta vigente y `attempt = 1`, sin `retryReason`.
   - Message: `messageId` guardado, `role = ROLE_USER`, `extensions = [urn:tfm:negociacion:v1]` y `contextId` solo si existe.
3. Renueva el arrendamiento, toma el instante de inicio del intento y llama a `SendMessage` de la parte con turno con la cabecera `A2A-Extensions` y `returnImmediately = true` (D-58, D-65).
4. Recibe una Task no final. En una transacción guarda el `taskId`, el instante de inicio y el `contextId` si es nuevo; la sesión pasa a `AWAITING_TASK`.
5. Consulta la Task con `GetTask` cada `pollIntervalSeconds`, renovando el arrendamiento en cada consulta, hasta que llega a `TASK_STATE_COMPLETED` (D-59, D-65).
6. Comprueba que la Task tiene exactamente un Artifact con exactamente una Part `data` de `mediaType` de acto.
7. Valida el sobre del Artifact (tabla de campos comunes, D-31, D-34).
8. Evalúa el encaje del cuerpo, tal como llega, con los esquemas de los actos y su coherencia con el tipo del sobre (D-26, D-44, D-72, D-73).
9. Valida el cuerpo con el tipo resultante: la oferta si es `COUNTEROFFER` (tabla «Oferta», D-39), el tipo de `reason` si es `WITHDRAW` (D-43, D-74) y el cuerpo vacío si es `ACCEPT` (D-42).
10. Si no hay fallos, el acto es `COUNTEROFFER` y `turn < maxTurns`: en una sola transacción añade el acto aceptado y sus coerciones a los registros, guarda la nueva oferta vigente con su emisor y pasa la sesión a `turn + 1` en `READY`, con `attempt = 1` y un `messageId` nuevo.

Los pasos 8 y 9 siguen el orden de D-72. Para elegir `lastFailure`, los fallos se siguen ordenando como Task, sobre, cuerpo y coherencia (D-61).

## Flujos alternativos
- **3a.** Se supera `turnTimeoutSeconds` antes de recibir la Task → se registra `TURN_TIMEOUT` sin `taskId`; no se envía `CancelTask` → **R** (D-52).
- **3b.** Error de transporte en `SendMessage` → se registra `AGENT_UNREACHABLE` → **R**.
- **3c.** `SendMessage` responde con un Message → se registra `MISSING_ACT` en `task`, sin `taskId` → **R** (D-62).
- **3d.** `SendMessage` responde con un error A2A → se registra `AGENT_ERROR` en `task`, sin `taskId` → **R** (D-71).
- **4a.** `SendMessage` devuelve una Task ya en estado final → se guardan sus identificadores y se evalúa como resultado del paso 5.
- **5a.** Se supera `turnTimeoutSeconds` durante el sondeo → se registra `TURN_TIMEOUT` y se envía `CancelTask` sin esperar resultado → **R** (D-52).
- **5b.** Error de transporte en `GetTask` → no hace fallar el intento; se sigue sondeando.
- **5c.** `GetTask` responde `TaskNotFoundError` → se registra `MISSING_ACT` en `task` → **R** (D-68).
- **5d.** La Task termina en `TASK_STATE_FAILED`, `TASK_STATE_REJECTED` o `TASK_STATE_CANCELED` → se registra `TASK_FAILED`, `TASK_REJECTED` o `TASK_CANCELED` → **R** (D-23, D-60).
- **5e.** La Task queda en `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` o en un estado desconocido → se envía `CancelTask` sin esperar resultado y se registra `TASK_INTERRUPTED` → **R** (D-60).
- **6a.** No hay exactamente un Artifact con una Part `data` de acto → se registra `MISSING_ACT` o `MULTIPLE_ACTS` → **R** (D-23).
- **7a / 8a / 9a.** Modo tolerante y todos los fallos son corregibles → se aplican las correcciones, se registra cada coerción y se continúa en el paso 10 o en 10a–10c. Esto incluye:
  - un `PROPOSE` con oferta, que se corrige a `COUNTEROFFER` (`ACT_NOT_ALLOWED`, D-44);
  - un sobre `ACCEPT` con cuerpo de `WITHDRAW`, que se corrige a `WITHDRAW` (D-26, D-72);
  - un `ACCEPT` con una oferta idéntica a la vigente tras normalizarla, que queda como `ACCEPT` con la oferta descartada (`ACT_BODY_MISMATCH`, D-73).
- **7b / 8b / 9b.** Modo estricto y hay al menos un fallo → se registran los fallos sin corregir → **R**.
- **7c / 8c / 9c.** Hay al menos un fallo no corregible → se registran → **R**. Esto incluye:
  - un `ACCEPT` con una oferta distinta de la vigente, o cuya normalización falla;
  - un `WITHDRAW` con oferta;
  - un cuerpo vacío con sobre `PROPOSE` o `COUNTEROFFER`;
  - un término ausente, fuera de rango o que exige redondear;
  - un `reason` que no es cadena (D-74).
- **10a.** El acto aceptado es `COUNTEROFFER` y `turn = maxTurns` → en una transacción se añaden el acto y sus coerciones, y la sesión pasa a `CLOSING` con `NO_AGREEMENT` y `lastOffers`, que incluye este `COUNTEROFFER`; la oferta vigente no cambia (D-54, D-57, D-82, CU-02).
- **10b.** El acto aceptado es `ACCEPT` → en una transacción se añaden el acto y sus coerciones, y la sesión pasa a `HELD` con la oferta vigente como oferta acordada, `heldUntil` = instante de la transición + `holdTimeoutSeconds` y el envío de `AGREEMENT_HELD` pendiente a cada parte (D-42, D-77, D-84 a D-86). El acuerdo no es firme hasta `RESOLVE_HOLDS`.
- **10c.** El acto aceptado es `WITHDRAW` → en una transacción se añaden el acto y sus coerciones, y la sesión pasa a `CLOSING` con `WITHDRAWN`, con `withdrawnBy` igual a la parte con turno, su `reason` si la hay y `lastOffers` (D-82, CU-02).
- **R · Reintento.** Los fallos del intento se añaden al registro en la misma transacción que la transición.
  - **Si `attempt − 1 < maxRetries`** (D-08, D-51): `attempt + 1`, `messageId` nuevo y vuelta al paso 2 con el mismo `turn`, con `retryReason` con los fallos del intento, el `contextId` guardado si existe y `referenceTaskIds = [taskId anterior]` si el intento tuvo `taskId`.
  - **Si `attempt − 1 = maxRetries`:** la sesión se aborta (D-07) y pasa a `CLOSING` con `ABORTED`, `abortReason = RETRIES_EXHAUSTED`, `lastFailure` igual al primer fallo del intento según el orden Task, sobre, cuerpo, coherencia, y `lastOffers` (D-53, D-61, D-82, CU-02).
- **C · Caída del orquestador.** Otra instancia retoma la sesión cuando caduca el arrendamiento (D-63, D-65). En `READY`, reenvía el intento con el mismo `messageId` (D-66). En `AWAITING_TASK`, sigue sondeando el `taskId` guardado con el tiempo restante desde el instante de inicio guardado.

Un `COUNTEROFFER` idéntico a la oferta vigente se acepta como cualquier otro (D-45). En el último turno lleva a `NO_AGREEMENT` (10a).

## Postcondiciones
- Estado final de la sesión: uno de estos cuatro:
  - `turn + 1` en `READY` con el `COUNTEROFFER` aceptado;
  - `HELD` con el acuerdo provisional del `ACCEPT`;
  - `CLOSING` con `NO_AGREEMENT` o `WITHDRAWN`;
  - `CLOSING` con `ABORTED`.
- Qué queda en el estado externalizado:
  - el `contextId` de la parte con turno, si algún intento lo obtuvo;
  - la nueva oferta vigente y su emisor, si se pasa al turno siguiente;
  - la oferta acordada, `heldUntil` y los envíos de `AGREEMENT_HELD` pendientes, si pasa a `HELD`;
  - o el resultado de la sesión con `lastOffers`, si pasa a cierre.
- Qué queda registrado:
  - el acto aceptado, si lo hay, incluido el `COUNTEROFFER` del último turno;
  - por cada fallo: `code`, `field`, `turn`, `attempt`, `taskId` si lo hay e instante;
  - por cada coerción, además, el valor original, el valor corregido y la decisión aplicada (`maquina-estados.md`, sección 3).

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-03-01 · El `TURN_REQUEST` de un turno ≥ 2 lleva `allowedActs = [COUNTEROFFER, ACCEPT, WITHDRAW]`, `turnsLeft = maxTurns − turn + 1`, `lastOffer` igual a la oferta vigente, `attempt = 1`, el `messageId` guardado y la URI en `extensions` y en la cabecera, no lleva `retryReason` y se envía con `returnImmediately = true`.
- [ ] AC-03-02 · El turno se envía a la parte que corresponde por paridad: la que abre en los turnos impares y la otra en los pares.
- [ ] AC-03-03 · En el turno 2, el `TURN_REQUEST` va sin `contextId`; el `contextId` devuelto se guarda antes de empezar el sondeo y se envía en los reintentos y en los turnos siguientes de esa parte.
- [ ] AC-03-04 · Un `COUNTEROFFER` válido con `turn < maxTurns` se acepta, su oferta queda como oferta vigente con su emisor y la sesión pasa a `turn + 1` en `READY`.
- [ ] AC-03-05 · Un `COUNTEROFFER` válido con `turn = maxTurns` se registra como acto aceptado, la oferta vigente no cambia y la sesión pasa a `CLOSING` con `NO_AGREEMENT` y `lastOffers` que incluye ese `COUNTEROFFER`.
- [ ] AC-03-06 · Un `ACCEPT` válido lleva la sesión a `HELD`, no a `CLOSING`, con la oferta vigente como oferta acordada, `heldUntil` igual al instante de la transición más `holdTimeoutSeconds` y el envío de `AGREEMENT_HELD` pendiente a las dos partes.
- [ ] AC-03-07 · Un `WITHDRAW` válido lleva la sesión a `CLOSING` con `WITHDRAWN`, `withdrawnBy` igual a la parte con turno, su `reason` si la hay y `lastOffers`.
- [ ] AC-03-08 · Tolerante: un `PROPOSE` con oferta en un turno ≥ 2 se corrige a `COUNTEROFFER` y se registra la coerción con `ACT_NOT_ALLOWED`.
- [ ] AC-03-09 · Tolerante: un `ACCEPT` con una oferta idéntica a la vigente tras normalizarla, incluido un precio en forma textual normalizable, queda como `ACCEPT` con la oferta descartada y la coerción registrada con `ACT_BODY_MISMATCH`.
- [ ] AC-03-10 · Tolerante: un sobre `ACCEPT` con cuerpo `{reason}` se corrige a `WITHDRAW`; nunca se acepta como `ACCEPT` descartando `reason`.
- [ ] AC-03-11 · En ambos modos: un `ACCEPT` con una oferta distinta de la vigente, o cuya normalización falla, y un `WITHDRAW` con oferta provocan reintento con `ACT_BODY_MISMATCH`.
- [ ] AC-03-12 · En ambos modos: un cuerpo vacío con sobre `COUNTEROFFER` provoca reintento.
- [ ] AC-03-13 · En ambos modos: un `reason` que no es cadena provoca reintento con `WRONG_TYPE` en `body.reason`.
- [ ] AC-03-14 · Estricto: los casos de AC-03-08 a AC-03-10 provocan reintento sin aplicar correcciones.
- [ ] AC-03-15 · Las correcciones de sobre y oferta de los criterios AC-01-04 a AC-01-06 y AC-01-08 a AC-01-12 se cumplen igual en un turno ≥ 2, en los dos modos.
- [ ] AC-03-16 · Un `COUNTEROFFER` idéntico a la oferta vigente se acepta como cualquier otro.
- [ ] AC-03-17 · Una respuesta de error A2A a `SendMessage` registra `AGENT_ERROR` en `task` y el reintento no lleva `referenceTaskIds`.
- [ ] AC-03-18 · En el turno 2, un reintento tras un intento que no obtuvo `contextId` va sin `contextId`; si algún intento anterior lo obtuvo, lo reutiliza.
- [ ] AC-03-19 · Los criterios AC-01-14 a AC-01-26 (reintento, aborto, tiempo máximo, estados de la Task, sondeo y caída) se cumplen igual en un turno ≥ 2.
- [ ] AC-03-20 · Si el intento que agota los reintentos tiene varios fallos, `lastFailure` es el primero según el orden Task, sobre, cuerpo, coherencia, aunque el cuerpo se haya evaluado antes que la coherencia (D-61, D-72).

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
Ninguna.

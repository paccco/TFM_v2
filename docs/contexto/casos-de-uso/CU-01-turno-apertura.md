# CU-01 · Procesar el turno de apertura

| Campo | Contenido |
|---|---|
| Actor principal | Orquestador |
| Objetivo | Obtener de la parte que abre un acto válido para el turno 1 y registrarlo en el estado externalizado |
| Precondiciones | Sesión en `NEGOTIATING`, subestado `READY` (`maquina-estados.md`), con configuración válida (D-40, D-41, D-90). Ambas AgentCards declaran `urn:tfm:negociacion:v1` con `required = true` (D-25). `turn = 1`, `attempt = 1` y `messageId` del intento guardado (D-66). Modo de validación fijado (D-11). Sin `contextId` guardado para la parte que abre. El orquestador tiene el arrendamiento de la sesión (D-63) |
| Disparador | Paso de la sesión de `CREATED` a `NEGOTIATING` |
| Decisiones y reglas | D-07, D-08, D-11, D-17–D-20, D-22, D-23, D-25–D-28, D-31–D-39, D-41–D-48, D-50–D-53, D-57–D-63, D-65, D-66, D-68, D-71–D-74, D-82, D-90. AC-01-01 a AC-01-30 |

## Flujo principal
1. El orquestador lee del estado externalizado la sesión, la parte que abre, su papel, los términos fijos, `maxTurns`, `turn = 1`, `attempt = 1` y el `messageId` del intento.
2. Construye un `TURN_REQUEST`:
   - Sobre: `sessionId`, `turn = 1`, `type = TURN_REQUEST`, `sender = ORCHESTRATOR`.
   - Cuerpo: `role`, `fixedTerms`, `allowedActs = [PROPOSE, WITHDRAW]`, `turnsLeft = maxTurns`, `attempt = 1`, sin `lastOffer` ni `retryReason`.
   - Message: `messageId` guardado, `role = ROLE_USER`, `extensions = [urn:tfm:negociacion:v1]`, sin `contextId`.
3. Renueva el arrendamiento, toma el instante de inicio del intento y llama a `SendMessage` de la parte que abre con la cabecera `A2A-Extensions` y `returnImmediately = true` (D-58, D-65).
4. Recibe una Task no final. Guarda en el estado, en la misma transacción, el `contextId` devuelto, el `taskId` y el instante de inicio; la sesión pasa a `AWAITING_TASK`.
5. Consulta la Task con `GetTask` cada `pollIntervalSeconds`, renovando el arrendamiento en cada consulta, hasta que llega a `TASK_STATE_COMPLETED` (D-59, D-65).
6. Comprueba que la Task tiene exactamente un Artifact con exactamente una Part `data` de `mediaType` de acto.
7. Valida el sobre del Artifact (tabla de campos comunes, D-34).
8. Evalúa el encaje del cuerpo, tal como llega, con los esquemas de los actos y su coherencia con el tipo del sobre (D-26, D-44, D-72, D-73).
9. Valida el cuerpo con el tipo resultante: la oferta si es `PROPOSE` (tabla «Oferta», D-39) o el tipo de `reason` si es `WITHDRAW` (D-43, D-74).
10. Sin fallos: en una sola transacción, añade el acto aceptado y sus coerciones a los registros, guarda la oferta como oferta vigente con su emisor y pasa la sesión al turno 2 en `READY`, con `attempt = 1` y un `messageId` nuevo.

Los pasos 8 y 9 siguen el orden de D-72. Para elegir `lastFailure`, los fallos se siguen ordenando como Task, sobre, cuerpo y coherencia (D-61).

## Flujos alternativos
- **3a.** Se supera `turnTimeoutSeconds` antes de recibir la Task → se registra `TURN_TIMEOUT` sin `taskId`; no se envía `CancelTask` → **R** (D-52).
- **3b.** Error de transporte en `SendMessage` → se registra `AGENT_UNREACHABLE` → **R**.
- **3c.** `SendMessage` responde con un Message → se registra `MISSING_ACT` en `task`, sin `taskId` → **R** (D-62).
- **3d.** `SendMessage` responde con un error A2A → se registra `AGENT_ERROR` en `task`, sin `taskId` → **R** (D-71).
- **4a.** `SendMessage` devuelve una Task ya en estado final → se guardan sus identificadores y se evalúa como resultado del paso 5.
- **5a.** Se supera `turnTimeoutSeconds` durante el sondeo → se registra `TURN_TIMEOUT`, se envía `CancelTask` sin esperar resultado → **R** (D-52).
- **5b.** Error de transporte en `GetTask` → no hace fallar el intento; se sigue sondeando.
- **5c.** `GetTask` responde `TaskNotFoundError` → se registra `MISSING_ACT` en `task` → **R** (D-68).
- **5d.** La Task termina en `TASK_STATE_FAILED`, `TASK_STATE_REJECTED` o `TASK_STATE_CANCELED` → se registra `TASK_FAILED`, `TASK_REJECTED` o `TASK_CANCELED` → **R** (D-23, D-60).
- **5e.** La Task queda en `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` o en un estado desconocido → se envía `CancelTask` sin esperar resultado y se registra `TASK_INTERRUPTED` → **R** (D-60).
- **6a.** No hay exactamente un Artifact con una Part `data` de acto → se registra `MISSING_ACT` o `MULTIPLE_ACTS` → **R** (D-23).
- **7a / 8a / 9a.** Modo tolerante y todos los fallos son corregibles → se aplican las correcciones, se registra cada coerción y se continúa en el paso 10. Esto incluye:
  - un `COUNTEROFFER` con oferta, que se corrige a `PROPOSE` (D-44);
  - un sobre `PROPOSE` con cuerpo de `WITHDRAW`, que se corrige a `WITHDRAW` (D-26, D-72).
- **7b / 8b / 9b.** Modo estricto y hay al menos un fallo → se registran los fallos sin corregir → **R**.
- **7c / 8c / 9c.** Hay al menos un fallo no corregible → se registran → **R**. Esto incluye:
  - un término ausente, fuera de rango o que exige redondear;
  - `ACCEPT` en el turno 1;
  - un cuerpo vacío con un sobre que no es `ACCEPT` ni `WITHDRAW`;
  - un sobre `WITHDRAW` o `ACCEPT` con oferta (D-73);
  - un `reason` que no es cadena (D-74).
- **10a.** El acto aceptado es `WITHDRAW` → se registra con su `reason`, si la hay, y la sesión pasa a `CLOSING` con resultado `WITHDRAWN`, sin `lastOffers` porque ninguna parte llegó a ofertar (D-82, CU-02).
- **R · Reintento.** Los fallos del intento se añaden al registro en la misma transacción que la transición.
  - **Si `attempt − 1 < maxRetries`** (D-08, D-51): `attempt + 1`, `messageId` nuevo y vuelta al paso 2 con el mismo `turn`, `retryReason` con los fallos del intento, el `contextId` guardado si existe y `referenceTaskIds = [taskId anterior]` si el intento tuvo `taskId`.
  - **Si `attempt − 1 = maxRetries`:** la sesión se aborta (D-07) y pasa a `CLOSING` con resultado `ABORTED`, `abortReason = RETRIES_EXHAUSTED` y `lastFailure` igual al primer fallo del intento según el orden Task, sobre, cuerpo, coherencia, sin `lastOffers` porque ninguna parte llegó a ofertar (D-53, D-61, D-82, CU-02).
- **C · Caída del orquestador.** Otra instancia retoma la sesión cuando caduca el arrendamiento (D-63, D-65). En `READY`, reenvía el intento con el mismo `messageId` (D-66). En `AWAITING_TASK`, sigue sondeando el `taskId` guardado con el tiempo restante desde el instante de inicio guardado.

## Postcondiciones
- Estado final de la sesión: turno 2 en `READY` con el `PROPOSE` aceptado, `CLOSING` por `WITHDRAW`, o `CLOSING` por aborto.
- Qué queda en el estado externalizado: `contextId` de la parte que abre (si algún intento lo obtuvo), oferta vigente y su emisor si el acto es `PROPOSE`, o el resultado de la sesión si pasa a cierre.
- Qué queda registrado: el acto aceptado, si lo hay; por cada fallo, `code`, `field`, `turn`, `attempt`, `taskId` si lo hay e instante; por cada coerción, además, el valor original, el valor corregido y la decisión aplicada (`maquina-estados.md`, sección 3).

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-01-01 · El `TURN_REQUEST` del turno 1 no lleva `contextId`, `lastOffer` ni `retryReason`; lleva `allowedActs = [PROPOSE, WITHDRAW]`, `attempt = 1`, `turnsLeft = maxTurns`, el `messageId` guardado y la URI en `extensions` y en la cabecera, y se envía con `returnImmediately = true`.
- [ ] AC-01-02 · El `contextId` y el `taskId` devueltos se guardan en el estado antes de empezar el sondeo, y el `contextId` se reutiliza en los reintentos.
- [ ] AC-01-03 · Un `PROPOSE` válido se acepta sin coerciones, su oferta queda como oferta vigente y la sesión pasa al turno 2 en `READY`.
- [ ] AC-01-04 · Tolerante: `turn = "1"` se corrige a 1 y se registra la coerción.
- [ ] AC-01-05 · Tolerante: un `sessionId` o un `sender` incorrectos se sustituyen por los del estado, con coerción registrada.
- [ ] AC-01-06 · Tolerante: `type = "propose"` se normaliza a `PROPOSE`.
- [ ] AC-01-07 · Tolerante: `COUNTEROFFER` con oferta en el turno 1 se corrige a `PROPOSE` (D-44).
- [ ] AC-01-08 · Tolerante: `unitPrice = "12,50 €"` se corrige a 12.50, interpretado como decimal exacto.
- [ ] AC-01-09 · Tolerante: `productId`, `unit` o `currency` ausentes o distintos se toman de la sesión.
- [ ] AC-01-10 · Tolerante: un campo no definido en el sobre o en la oferta se descarta con coerción registrada.
- [ ] AC-01-11 · Estricto: cualquiera de los casos AC-01-04 a AC-01-10 provoca reintento sin aplicar correcciones.
- [ ] AC-01-12 · En ambos modos: una oferta sin `quantity`, con `unitPrice = 12.505` o con `quantity = 0` provoca reintento.
- [ ] AC-01-13 · En ambos modos: `ACCEPT` en el turno 1 provoca reintento.
- [ ] AC-01-14 · Un reintento mantiene `turn = 1`, incrementa `attempt`, usa un `messageId` nuevo, incluye `retryReason` y lleva `referenceTaskIds` con el `taskId` anterior solo si ese intento lo tuvo.
- [ ] AC-01-15 · Al alcanzar `maxRetries`, la sesión pasa a `CLOSING` con `ABORTED`, `abortReason = RETRIES_EXHAUSTED` y `lastFailure` igual al primer fallo del último intento según el orden de validación.
- [ ] AC-01-16 · Un `WITHDRAW` válido en el turno 1 lleva la sesión a `CLOSING` con `WITHDRAWN`.
- [ ] AC-01-17 · Superar el tiempo del turno durante el sondeo registra `TURN_TIMEOUT`, envía `CancelTask` y pasa a reintento; superarlo antes de recibir la Task registra `TURN_TIMEOUT` sin enviar `CancelTask`.
- [ ] AC-01-18 · Tras un intento fallido, su Task no se vuelve a consultar, y que termine más tarde no altera el estado.
- [ ] AC-01-19 · Todo fallo registrado y toda entrada de `retryReason` usan un código del catálogo y una ruta `envelope.*`, `body.*` o `task`.
- [ ] AC-01-20 · Una Task en `TASK_STATE_CANCELED` registra `TASK_CANCELED` y pasa a reintento.
- [ ] AC-01-21 · Una Task en `TASK_STATE_INPUT_REQUIRED`, `TASK_STATE_AUTH_REQUIRED` o en un estado desconocido envía `CancelTask`, registra `TASK_INTERRUPTED` y pasa a reintento.
- [ ] AC-01-22 · Una respuesta con Message en lugar de Task registra `MISSING_ACT` en `task` y el reintento no lleva `referenceTaskIds`.
- [ ] AC-01-23 · Un `TaskNotFoundError` durante el sondeo registra `MISSING_ACT` en `task` y pasa a reintento.
- [ ] AC-01-24 · Un error de transporte en `GetTask` no hace fallar el intento: el sondeo continúa hasta el tiempo máximo.
- [ ] AC-01-25 · Si el orquestador cae en `AWAITING_TASK`, la instancia que retoma la sesión sondea el mismo `taskId` y respeta el tiempo restante desde el instante de inicio guardado.
- [ ] AC-01-26 · Si el orquestador cae en `READY`, la instancia que retoma la sesión reenvía el intento con el mismo `messageId`.
- [ ] AC-01-27 · Una respuesta de error A2A a `SendMessage` registra `AGENT_ERROR` en `task` y el reintento no lleva `referenceTaskIds`.
- [ ] AC-01-28 · Tolerante: un sobre `PROPOSE` con cuerpo `{reason}` se corrige a `WITHDRAW` con coerción registrada; en estricto provoca reintento.
- [ ] AC-01-29 · En ambos modos: un sobre `WITHDRAW` con oferta provoca reintento con `ACT_BODY_MISMATCH`.
- [ ] AC-01-30 · En ambos modos: un `WITHDRAW` con `reason` que no es cadena provoca reintento con `WRONG_TYPE` en `body.reason`.

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
Ninguna.

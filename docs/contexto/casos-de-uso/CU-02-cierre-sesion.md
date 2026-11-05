# CU-02 · Cerrar la sesión

| Campo | Contenido |
|---|---|
| Actor principal | Orquestador |
| Objetivo | Comunicar a ambas partes, con `SESSION_CLOSE`, el resultado ya decidido de la sesión y dejarla en `CLOSED` |
| Precondiciones | Sesión en `CLOSING`, con `outcome` y sus campos asociados guardados, incluido `lastOffers` si `outcome` ≠ `AGREEMENT`, y el envío a cada parte como pendiente (`maquina-estados.md`, secciones 1 y 3). `turn` del turno que provocó el cierre o, si la sesión viene de `HELD`, el del `ACCEPT`. `contextId` de cada parte solo si llegó a tener turno. El orquestador tiene el arrendamiento de la sesión (D-63). El modo de validación no interviene: la respuesta no se valida (D-49) |
| Disparador | Paso de la sesión a `CLOSING`: desde `NEGOTIATING` (CU-01 o CU-03), o desde `HELD` por `RESOLVE_HOLDS` (CU-06) o por plazo vencido (CU-07) (D-84, D-86) |
| Decisiones y reglas | D-17–D-19, D-21, D-27, D-29, D-30, D-32, D-42, D-46, D-49, D-53–D-55, D-57, D-61, D-63–D-65, D-69–D-71, D-82, D-84–D-86, D-90, D-115, D-119, D-122. AC-02-01 a AC-02-17 |

`NOT_STARTED` queda fuera de este CU: no envía `SESSION_CLOSE` (D-25).

## Flujo principal
1. El orquestador lee del estado externalizado `sessionId`, `turn`, el resultado y sus campos, los `partyId` de las dos partes, el `contextId` de cada una si lo tiene y el estado de los dos envíos (ambos pendientes).
2. Para cada parte pendiente construye un `SESSION_CLOSE`:
   - Sobre: `sessionId`, `turn`, `type = SESSION_CLOSE`, `sender = ORCHESTRATOR`.
   - Cuerpo: `outcome` y solo los campos que le corresponden: `agreedOffer` si `AGREEMENT`; `withdrawnBy` si `WITHDRAWN`; `abortReason` y `lastFailure` si `ABORTED`; `releaseReason` si `RELEASED`; y `lastOffers` si `outcome` ≠ `AGREEMENT` y alguna parte llegó a ofertar (D-82). El `reason` del `WITHDRAW` no viaja.
   - Message: `messageId` nuevo y no persistido, `role = ROLE_USER`, `extensions = [urn:tfm:negociacion:v1]` y `contextId` solo si la parte lo tiene.
3. Renueva el arrendamiento y lanza los dos `SendMessage` a la vez, con la cabecera `A2A-Extensions` y `returnImmediately = true`, tomando el instante de cada envío (D-64, D-65).
4. Para cada envío que recibe una Task, en cualquier estado, o un Message dentro de `turnTimeoutSeconds`, en una transacción marca a esa parte como enviada y añade al registro de envíos de control una entrada de tipo `SESSION_CLOSE` con el `taskId` y el estado de la Task, o la indicación de que llegó un Message (D-70, D-85). No sondea, no envía `CancelTask` y no valida la respuesta (D-49). Las escrituras de los dos envíos se hacen una tras otra dentro de la instancia (D-63).
5. La transacción que marca el último envío pendiente pasa la sesión a `CLOSED`.

## Flujos alternativos
- **4a.** Error de transporte en un `SendMessage` → en una transacción, se marca el envío a esa parte como fallido y se añade la entrada con `AGENT_UNREACHABLE` (D-64, D-70).
- **4b.** Sin respuesta en `turnTimeoutSeconds` → se marca como fallido con `TURN_TIMEOUT`. No se envía `CancelTask`: no hay `taskId`.
- **4c.** La parte responde con un error A2A → se marca como fallido con `AGENT_ERROR`, sin reintento (D-71).
- **4d.** La escritura se rechaza porque la versión cambió → la instancia descarta su trabajo; otra instancia ha retomado la sesión (D-63).
- **5a.** Uno o los dos envíos han fallado → la sesión pasa igualmente a `CLOSED` cuando no queda ninguno pendiente, con el mismo resultado (D-49).
- En todos los casos 4x, el fallo de un envío no afecta al otro, que sigue en curso (D-64).
- **C · Caída del orquestador.** La búsqueda de sesiones con trabajo pendiente encuentra la sesión en `CLOSING` cuando su arrendamiento ha caducado o, si viene de `RESOLVE_HOLDS` y ninguna instancia llegó a tomarlo, en cuanto la encuentra sin arrendamiento (D-63, D-65, D-115, D-119). Si viene de la caducidad del plazo, la instancia que la procesó conservaba el arrendamiento, así que se espera a que caduque (D-122). La instancia que la toma envía `SESSION_CLOSE` solo a las partes que siguen pendientes, con un `messageId` nuevo. Si la caída ocurrió entre un envío y su marca, ese envío se repite y el registro de envíos de control tendrá dos entradas para esa parte. Se acepta, porque el agente no guarda estado de sesión (D-46).

## Postcondiciones
- Estado final de la sesión: `CLOSED`. Si la instancia cae antes, la sesión sigue en `CLOSING` hasta que otra la tome.
- Qué queda en el estado externalizado: el resultado, sin cambios respecto a la entrada en `CLOSING`, y el envío a cada parte marcado como enviado o fallido, sin ninguno pendiente.
- Qué queda registrado: una entrada de tipo `SESSION_CLOSE` por envío en el registro de envíos de control, con parte, `turn`, instante, resultado y, según el caso, `taskId` y estado de la Task, indicación de Message o código del fallo (D-70, D-85). No se añade nada a los registros de fallos ni de coerciones, y no hay reintentos.

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-02-01 · Se envía `SESSION_CLOSE` a las dos partes de forma concurrente, cada uno con `returnImmediately = true`, la cabecera `A2A-Extensions`, la URI en `extensions`, `role = ROLE_USER` y un `messageId` nuevo.
- [ ] AC-02-02 · El sobre lleva el `sessionId` del estado, el `turn` del turno que provocó el cierre, `type = SESSION_CLOSE` y `sender = ORCHESTRATOR`.
- [ ] AC-02-03 · El cuerpo lleva `outcome` y solo sus campos: `AGREEMENT` con `agreedOffer` igual a la oferta acordada en `HELD` y sin `lastOffers`; `WITHDRAWN` con `withdrawnBy` y sin `reason`; `NO_AGREEMENT` sin más campos que `lastOffers`; `ABORTED` con `abortReason = RETRIES_EXHAUSTED` y `lastFailure`; `RELEASED` con `releaseReason`. En todos salvo `AGREEMENT`, lleva `lastOffers` si alguna parte llegó a ofertar.
- [ ] AC-02-04 · Cada Message lleva el `contextId` de su parte solo si lo tiene; si la sesión cierra en el turno 1, el de la parte que no abre va sin `contextId`.
- [ ] AC-02-05 · Una respuesta con Task, en cualquier estado, o con Message marca el envío como enviado y registra el `taskId` y el estado, o la indicación de Message; no se sondea, no se envía `CancelTask` y no se valida.
- [ ] AC-02-06 · Un error de transporte marca el envío como fallido con `AGENT_UNREACHABLE`.
- [ ] AC-02-07 · Sin respuesta en `turnTimeoutSeconds`, el envío se marca como fallido con `TURN_TIMEOUT` y no se envía `CancelTask`.
- [ ] AC-02-08 · Una respuesta de error A2A marca el envío como fallido con `AGENT_ERROR`.
- [ ] AC-02-09 · Hay un solo intento por parte, y el fallo de un envío no impide ni retrasa el otro.
- [ ] AC-02-10 · La sesión pasa a `CLOSED` cuando no queda ningún envío pendiente, también si los dos han fallado, y el resultado no cambia.
- [ ] AC-02-11 · Cada marca de envío y su entrada en el registro de envíos de control se escriben en la misma transacción, y la entrada lleva tipo `SESSION_CLOSE`, parte, `turn`, instante y resultado.
- [ ] AC-02-12 · Si el orquestador cae en `CLOSING`, la instancia que toma la sesión solo envía a las partes pendientes; las marcadas como enviadas o fallidas no se reenvían.
- [ ] AC-02-13 · Si una escritura se rechaza porque la versión cambió, la instancia descarta su trabajo y no vuelve a escribir.
- [ ] AC-02-14 · El arrendamiento se renueva antes de lanzar los envíos.
- [ ] AC-02-15 · Una sesión que viene de `HELD` lleva en el sobre el `turn` del `ACCEPT`, con `AGREEMENT` si se confirmó, `RELEASED` con `releaseReason = BUYER_DECISION` si se liberó con `RESOLVE_HOLDS`, o `RELEASED` con `releaseReason = HOLD_EXPIRED` si venció el plazo.
- [ ] AC-02-16 · `lastOffers` contiene la última oferta aceptada de cada parte que ofertó, incluido el `COUNTEROFFER` del último turno aunque no sea la oferta vigente, y no incluye a las partes que no llegaron a ofertar.
- [ ] AC-02-17 · Si ninguna parte llegó a ofertar (por ejemplo, un `WITHDRAW` en el turno 1), el cuerpo no lleva `lastOffers`.

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
Ninguna.

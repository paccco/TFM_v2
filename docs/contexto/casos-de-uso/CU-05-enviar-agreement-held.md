# CU-05 · Enviar `AGREEMENT_HELD`

| Campo | Contenido |
|---|---|
| Actor principal | Orquestador |
| Objetivo | Comunicar a las dos partes, con `AGREEMENT_HELD`, el acuerdo provisional y su plazo de reserva, sin cambiar el estado de la sesión |
| Precondiciones | Sesión en `HELD` con la oferta acordada, `heldUntil` y al menos un envío de `AGREEMENT_HELD` pendiente (`maquina-estados.md`, secciones 1 y 3). `turn` del `ACCEPT`. `contextId` de las dos partes: el `ACCEPT` solo se acepta en un turno ≥ 2, así que las dos han tenido turno. El orquestador tiene el arrendamiento de la sesión (D-63). El modo de validación no interviene: la respuesta no se valida (D-49) |
| Disparador | Entrada de la sesión en `HELD` por un `ACCEPT` aceptado (CU-03, 10b), o toma de una sesión en `HELD` con envíos pendientes tras una caída |
| Decisiones y reglas | D-17–D-19, D-21, D-27, D-29, D-42, D-46, D-49, D-63–D-65, D-69–D-71, D-77, D-84–D-86, D-90, D-107, D-108. AC-05-01 a AC-05-16 |

## Flujo principal
1. El orquestador lee del estado externalizado `sessionId`, `turn`, la oferta acordada, `heldUntil`, los `partyId` de las dos partes, el `contextId` de cada una y el estado de los dos envíos (ambos pendientes).
2. Renueva el arrendamiento y, en la misma operación, comprueba con el reloj de la base de datos que `heldUntil` no ha vencido (D-69, D-107).
3. Para cada parte pendiente construye un `AGREEMENT_HELD`:
   - Sobre: `sessionId`, `turn`, `type = AGREEMENT_HELD`, `sender = ORCHESTRATOR`.
   - Cuerpo: `heldOffer` igual a la oferta acordada y `heldUntil` como instante ISO 8601 en UTC (D-42, D-86).
   - Message: `messageId` nuevo y no persistido, `role = ROLE_USER`, `extensions = [urn:tfm:negociacion:v1]` y el `contextId` de la parte.
4. Lanza los dos `SendMessage` a la vez, con la cabecera `A2A-Extensions` y `returnImmediately = true`, tomando el instante de cada envío (D-64, D-85).
5. Para cada envío que recibe una Task, en cualquier estado, o un Message dentro de `turnTimeoutSeconds`, en una transacción marca a esa parte como enviada y añade al registro de envíos de control una entrada de tipo `AGREEMENT_HELD` con el `taskId` y el estado de la Task, o la indicación de que llegó un Message (D-70, D-85). No sondea, no envía `CancelTask` y no valida la respuesta (D-49). Las escrituras de los dos envíos se hacen una tras otra dentro de la instancia (D-63).
6. La transacción que marca el último envío pendiente libera el arrendamiento (D-108). La sesión sigue en `HELD`, a la espera de `RESOLVE_HOLDS` (CU-06) o de la caducidad del plazo (CU-07).

## Flujos alternativos
- **2a.** `heldUntil` ya ha vencido → no se construye ni se envía ningún `AGREEMENT_HELD` y no se escribe nada en este CU. La instancia, que conserva el arrendamiento, continúa directamente con CU-07, que pasa la sesión a `CLOSING` con `RELEASED` y `releaseReason = HOLD_EXPIRED` y marca los envíos pendientes como descartados (D-86, D-107).
- **5a.** Error de transporte en un `SendMessage` → en una transacción, se marca el envío a esa parte como fallido y se añade la entrada con `AGENT_UNREACHABLE` (D-70).
- **5b.** Sin respuesta en `turnTimeoutSeconds` → se marca como fallido con `TURN_TIMEOUT`. No se envía `CancelTask`: no hay `taskId`.
- **5c.** La parte responde con un error A2A → se marca como fallido con `AGENT_ERROR`, sin reintento (D-71).
- **5d.** La escritura se rechaza porque la versión cambió → la instancia descarta su trabajo y no vuelve a escribir (D-63). Pasa si un `RESOLVE_HOLDS` resolvió la sesión mientras se enviaba, porque no necesita el arrendamiento; los envíos que seguían pendientes ya están descartados y el que estaba en curso queda sin entrada en el registro de envíos de control (`maquina-estados.md`, sección 3).
- **6a.** Uno o los dos envíos han fallado → el arrendamiento se libera igualmente cuando no queda ninguno pendiente. La sesión sigue en `HELD` con la misma oferta acordada y el mismo `heldUntil` (D-49, D-85).
- En todos los casos 5x, el fallo de un envío no afecta al otro, que sigue en curso (D-64).
- **C · Caída del orquestador.** Otra instancia toma la sesión cuando caduca el arrendamiento (D-63, D-65). Vuelve al paso 1: comprueba `heldUntil` (2a) y envía `AGREEMENT_HELD` solo a las partes que siguen pendientes, con un `messageId` nuevo. Si la caída ocurrió entre un envío y su marca, ese envío se repite y el registro de envíos de control tendrá dos entradas para esa parte. Se acepta, porque `AGREEMENT_HELD` no altera el estado (D-85) y el agente no guarda estado de sesión (D-46). Si la caída ocurrió después de marcar el último envío, el arrendamiento ya está liberado y no hay nada que retomar.

## Postcondiciones
- Estado final de la sesión: `HELD`. Si se dio 2a, la sesión sigue por CU-07. Si se dio 5d, el que dejó quien se adelantó.
- Qué queda en el estado externalizado: la oferta acordada y `heldUntil`, sin cambios; el envío a cada parte marcado como enviado o fallido, sin ninguno pendiente; la sesión sin arrendamiento.
- Qué queda registrado: una entrada de tipo `AGREEMENT_HELD` por envío en el registro de envíos de control, con parte, `turn` del `ACCEPT`, instante, resultado y, según el caso, `taskId` y estado de la Task, indicación de Message o código del fallo (D-70, D-85). No se añade nada a los registros de fallos, coerciones ni peticiones, y no hay reintentos.

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-05-01 · Se envía `AGREEMENT_HELD` a las dos partes de forma concurrente, cada uno con `returnImmediately = true`, la cabecera `A2A-Extensions`, la URI en `extensions`, `role = ROLE_USER` y un `messageId` nuevo.
- [ ] AC-05-02 · El sobre lleva el `sessionId` del estado, el `turn` del `ACCEPT`, `type = AGREEMENT_HELD` y `sender = ORCHESTRATOR`.
- [ ] AC-05-03 · El cuerpo lleva solo `heldOffer`, igual a la oferta acordada guardada, y `heldUntil`, igual al guardado y expresado como instante ISO 8601 en UTC.
- [ ] AC-05-04 · Cada Message lleva el `contextId` de su parte.
- [ ] AC-05-05 · Una respuesta con Task, en cualquier estado, o con Message marca el envío como enviado y registra el `taskId` y el estado, o la indicación de Message; no se sondea, no se envía `CancelTask` y no se valida.
- [ ] AC-05-06 · Un error de transporte marca el envío como fallido con `AGENT_UNREACHABLE`.
- [ ] AC-05-07 · Sin respuesta en `turnTimeoutSeconds`, el envío se marca como fallido con `TURN_TIMEOUT` y no se envía `CancelTask`.
- [ ] AC-05-08 · Una respuesta de error A2A marca el envío como fallido con `AGENT_ERROR`.
- [ ] AC-05-09 · Hay un solo intento por parte, y el fallo de un envío no impide ni retrasa el otro.
- [ ] AC-05-10 · Cada marca de envío y su entrada en el registro de envíos de control se escriben en la misma transacción, y la entrada lleva tipo `AGREEMENT_HELD`, parte, `turn` del `ACCEPT`, instante y resultado.
- [ ] AC-05-11 · Tras los envíos, la sesión sigue en `HELD` con la oferta acordada y `heldUntil` sin cambios, también si los dos han fallado, y no se escribe nada en los registros de fallos ni de coerciones.
- [ ] AC-05-12 · La transacción que marca el último envío pendiente libera el arrendamiento, también si los dos envíos han fallado.
- [ ] AC-05-13 · El arrendamiento se renueva antes de lanzar los envíos.
- [ ] AC-05-14 · Si `heldUntil` ha vencido según el reloj de la base de datos al renovar el arrendamiento, no se envía ningún `AGREEMENT_HELD` y la instancia continúa con CU-07 sin soltar el arrendamiento.
- [ ] AC-05-15 · Si el orquestador cae en `HELD` con envíos pendientes, la instancia que toma la sesión comprueba `heldUntil` y solo envía a las partes pendientes; las marcadas como enviadas o fallidas no se reenvían.
- [ ] AC-05-16 · Si un `RESOLVE_HOLDS` resuelve la sesión mientras se envía, la escritura de la marca se rechaza por versión, la instancia descarta su trabajo y no vuelve a escribir ni a enviar.

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
- Si falla el envío de `AGREEMENT_HELD` a un vendedor, este no sabe que debe reservar. Sigue abierta en `maquina-estados.md`, sección 6, y se decide al diseñar los agentes; no cambia este CU mientras no se decida.

# CU-07 · Procesar la caducidad del plazo de reserva

| Campo | Contenido |
|---|---|
| Actor principal | Orquestador |
| Objetivo | Liberar por plazo vencido una sesión en `HELD` y llevarla a `CLOSING` con `RELEASED` y `releaseReason = HOLD_EXPIRED` |
| Precondiciones | Sesión en `HELD` con `heldUntil` vencido según el reloj de la base de datos (D-69, D-86). Arrendamiento libre o caducado o, si se llega desde CU-05 2a, de esta instancia (D-107). El modo de validación no interviene: no hay acto que validar |
| Disparador | La búsqueda periódica de sesiones con trabajo pendiente encuentra la sesión (D-119, D-120), o CU-05 2a continúa con este CU sin soltar el arrendamiento (D-107) |
| Decisiones y reglas | D-63, D-65, D-69, D-77, D-82, D-84–D-86, D-95, D-96, D-107, D-108, D-111, D-115, D-119–D-122. AC-07-01 a AC-07-14 |

## Flujo principal
1. La búsqueda periódica, que se ejecuta cada 5 s, consulta las sesiones con trabajo pendiente y arrendamiento libre o caducado. Entre ellas están las sesiones en `HELD` con `heldUntil` vencido según el reloj de la base de datos (D-119, D-120).
2. Para cada sesión en `HELD` con el plazo vencido, la instancia lee el registro de sesión con su versión y obtiene `lastOffers` del registro de actos aceptados: la última oferta de cada parte que llegó a ofertar (D-82).
3. En una transacción, con escritura condicional que comprueba que la sesión sigue en `HELD`, que `heldUntil` ha vencido, que el arrendamiento está libre o caducado y que la versión no ha cambiado (D-121):
   - la sesión pasa a `CLOSING` con `outcome = RELEASED`, `releaseReason = HOLD_EXPIRED` y `lastOffers` (D-86);
   - los envíos de `AGREEMENT_HELD` pendientes pasan a descartados y no se envían (D-95);
   - los envíos de `SESSION_CLOSE` a las dos partes quedan pendientes;
   - el arrendamiento queda a nombre de esta instancia, con su caducidad renovada (D-65).

   No se añade nada a los registros de solo añadir. Cada sesión se procesa en su propia transacción.
4. Tras confirmar la transacción, la misma instancia continúa con CU-02 sin soltar el arrendamiento (D-122).

## Flujos alternativos
- **1a.** Se llega desde CU-05 2a → no hay búsqueda. La instancia ya tiene el arrendamiento y la sesión leída; continúa en el paso 2, y en el paso 3 la condición es que el arrendamiento sea de esta instancia (D-107, D-121).
- **1b.** La sesión tiene el arrendamiento vigente de otra instancia, que estaba enviando `AGREEMENT_HELD` antes del vencimiento → la búsqueda no la selecciona. Esa instancia libera el arrendamiento al marcar el último envío (D-108), o este caduca, y una pasada posterior procesa la sesión. El retraso no altera el resultado: mientras tanto, un `RESOLVE_HOLDS` sobre esa sesión se rechaza con `NOT_HELD` (D-111).
- **3a.** La escritura se rechaza porque alguna condición falla → no se escribe nada y la instancia descarta su trabajo (D-63, D-121). Pasa si un `RESOLVE_HOLDS` resolvió la sesión antes de vencer el plazo, que conserva el resultado de CU-06, o si otra instancia de la búsqueda se adelantó. Si la sesión sigue cumpliendo las condiciones, la siguiente pasada la vuelve a evaluar.
- **3b.** Falla la transición de una sesión → las demás sesiones de la misma pasada siguen su curso, cada una en su transacción (D-121).
- **C · Caída del orquestador.**
  - Antes de confirmar la transacción del paso 3: no queda nada escrito y la sesión sigue en `HELD`. Si se llegó por la búsqueda, el arrendamiento no llegó a tomarse y una pasada posterior la procesa. Si se llegó desde CU-05 2a, la procesa una pasada posterior a la caducidad del arrendamiento.
  - Después de confirmar: la sesión queda en `CLOSING` con el resultado guardado y el arrendamiento de la instancia caída. Cuando caduca, la búsqueda la encuentra y otra instancia envía `SESSION_CLOSE` solo a las partes que siguen pendientes (CU-02, D-63, D-65, D-122).

## Postcondiciones
- Estado final de la sesión: `CLOSING` con `outcome = RELEASED` y `releaseReason = HOLD_EXPIRED`, y continúa por CU-02. Si se dio 3a, el que dejó quien se adelantó.
- Qué queda en el estado externalizado: el resultado con `lastOffers`; los envíos de `AGREEMENT_HELD` que estaban pendientes, como descartados; los envíos de `SESSION_CLOSE` a las dos partes, como pendientes; el arrendamiento a nombre de la instancia que procesó la caducidad.
- Qué queda registrado: nada en los registros de actos, fallos, coerciones, envíos de control ni peticiones. Las entradas de los envíos de `SESSION_CLOSE` las añade CU-02.

## Criterios de aceptación
<!-- Cada uno se convierte en al menos un test -->
- [ ] AC-07-01 · La búsqueda periódica selecciona las sesiones en `HELD` con `heldUntil` vencido según el reloj de la base de datos y arrendamiento libre o caducado, en la misma consulta que el resto de sesiones con trabajo pendiente.
- [ ] AC-07-02 · La búsqueda se ejecuta cada 5 s, con un valor fijo que no depende de la configuración de ninguna sesión.
- [ ] AC-07-03 · Una sesión en `HELD` con el plazo vencido pasa a `CLOSING` con `outcome = RELEASED`, `releaseReason = HOLD_EXPIRED` y `lastOffers` con la última oferta de cada parte que llegó a ofertar.
- [ ] AC-07-04 · Los envíos de `AGREEMENT_HELD` pendientes quedan como descartados y no se envían; los de `SESSION_CLOSE` a las dos partes quedan pendientes.
- [ ] AC-07-05 · El estado, el resultado, las marcas de envío y el arrendamiento se escriben en una sola transacción condicional; si falla cualquier condición, no se escribe nada.
- [ ] AC-07-06 · La caducidad no añade ninguna entrada a los registros de actos, fallos, coerciones, envíos de control ni peticiones.
- [ ] AC-07-07 · Si un `RESOLVE_HOLDS` resolvió la sesión antes de vencer el plazo, la escritura de la caducidad se rechaza por versión y la sesión conserva el resultado de `RESOLVE_HOLDS`.
- [ ] AC-07-08 · Si dos instancias de la búsqueda procesan la misma sesión a la vez, solo una hace la transición y la otra no escribe nada.
- [ ] AC-07-09 · Una sesión con el plazo vencido y el arrendamiento vigente de otra instancia no se toma; se procesa en una pasada posterior a que el arrendamiento se libere o caduque.
- [ ] AC-07-10 · Desde CU-05 2a, la caducidad se aplica con el arrendamiento que ya tiene la instancia, sin enviar ningún `AGREEMENT_HELD`.
- [ ] AC-07-11 · Tras confirmar la transacción, la misma instancia lanza CU-02 sin soltar el arrendamiento.
- [ ] AC-07-12 · Si la instancia cae tras confirmar la transacción, otra instancia toma la sesión en `CLOSING` cuando caduca el arrendamiento y envía `SESSION_CLOSE` solo a las partes pendientes.
- [ ] AC-07-13 · Si la instancia cae antes de confirmar la transacción, la sesión sigue en `HELD` sin cambios y una pasada posterior la procesa.
- [ ] AC-07-14 · Cada sesión se procesa en su propia transacción; el fallo de una no impide la transición de las demás sesiones de la misma pasada.

## Preguntas abiertas
<!-- Lo que gemini-analista no puede deducir de docs/contexto/ va aquí, nunca se inventa -->
Ninguna.

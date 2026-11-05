# Catálogo de reglas de autocorrección

Fuente única de las reglas de autocorrección (D-123). `protocolo.md` y las tarjetas las citan por su `R-xx`. Los códigos de fallo siguen en `protocolo.md`, «Códigos de fallo» (D-50).

Decisiones que lo condicionan: D-02, D-08, D-11, D-22, D-23, D-26, D-28, D-31, D-34, D-36, D-37, D-39, D-43, D-44, D-50, D-53, D-61, D-72, D-73, D-74, D-89 y D-123.

## Alcance

- Solo fallos de **estructura**; los de contenido quedan fuera (D-02).
- Se aplica a los actos, sobre el sobre y el cuerpo ya interpretados como objetos: campos ausentes, tipos incorrectos y valores enumerados mal escritos. El JSON mal formado y el texto libre quedan fuera (D-22).
- Un campo solo se corrige si su valor correcto se conoce por el estado externalizado o la sesión, o por normalización determinista del propio valor. Nunca se deduce del contenido de la negociación (D-31, D-39).
- Las peticiones del comprador no se autocorrigen (D-89).
- Una respuesta sin objeto que interpretar no entra aquí: va a reintento (`protocolo.md`, «Respuestas no corregibles», D-23).

## Lo común a todas las reglas

| Campo | Contenido |
|---|---|
| Modo `STRICT` | No se corrige nada: se registra el fallo y se pasa a reintento (D-11, D-31, D-39) |
| Modo `TOLERANT` | Si todos los fallos del intento son corregibles, se aplican las correcciones y el acto continúa. Si alguno no lo es, se registran los fallos y se pasa a reintento, sin aceptar el acto |
| Si no se puede corregir | Reintento del turno (D-08, D-23). Solo al agotar los reintentos la sesión se aborta, con `abortReason = RETRIES_EXHAUSTED` (D-07, D-53). No existe el aborto directo |
| Orden | El encaje del cuerpo se evalúa sobre el cuerpo tal como llega, antes de descartar campos no definidos. Si el tipo se corrige, el cuerpo se valida con el tipo corregido (D-72). Para `lastFailure` se mantiene el orden Task, sobre, cuerpo y coherencia (D-61) |

## Formato de cada regla

| Campo | Contenido |
|---|---|
| ID | `R-xx` |
| Fallo y detección | Qué incumple el mensaje, con una condición determinista |
| Corrección en `TOLERANT` | Qué se hace, o «No corregible» |
| Código | Código del catálogo de `protocolo.md` |
| Decisiones | D-xx que la sustentan |
| Criterios | `AC-cc-nn` que la cubren. Toda regla tiene al menos uno |

## Reglas corregibles

| ID | Fallo y detección | Corrección en `TOLERANT` | Código | Decisiones | Criterios |
|---|---|---|---|---|---|
| R-01 | `sessionId` del sobre ausente o distinto del estado | Se toma del estado | `MISSING_FIELD`, `STATE_MISMATCH` | D-28, D-31 | AC-01-05 |
| R-02 | `turn` del sobre como cadena numérica, ausente o distinto del estado | La cadena numérica se convierte a entero; si falta o no coincide, se toma del estado | `WRONG_TYPE`, `MISSING_FIELD`, `STATE_MISMATCH` | D-28, D-31 | AC-01-04, AC-01-31 |
| R-03 | `type` del sobre con otras mayúsculas, espacios o guiones | Se normaliza | `INVALID_FORMAT` | D-31 | AC-01-06 |
| R-04 | `sender` del sobre ausente o distinto de la parte con turno | Se toma del estado | `MISSING_FIELD`, `STATE_MISMATCH` | D-31 | AC-01-05 |
| R-05 | Campo no definido en el sobre o en el cuerpo | Se descarta. En el cuerpo, después de evaluar el encaje | `UNKNOWN_FIELD` | D-34, D-72 | AC-01-10 |
| R-06 | El tipo del sobre no coincide con el cuerpo, y el cuerpo encaja con el esquema de un único acto | Se corrige el tipo según el cuerpo. Un sobre `PROPOSE` o `ACCEPT` con cuerpo `{reason}` pasa a `WITHDRAW` | `ACT_BODY_MISMATCH` | D-26, D-72 | AC-01-28, AC-03-10 |
| R-07 | Sobre `PROPOSE` o `COUNTEROFFER` con oferta, y tipo que no corresponde al turno | Se corrige según el turno: turno 1, `PROPOSE`; en otro caso, `COUNTEROFFER` | `ACT_NOT_ALLOWED` | D-26, D-44, D-73 | AC-01-07, AC-03-08 |
| R-08 | Sobre `ACCEPT` con una oferta idéntica a la vigente tras normalizarla | Sigue como `ACCEPT` y se descarta la oferta | `ACT_BODY_MISMATCH` | D-42, D-73 | AC-03-09 |
| R-09 | `productId`, `unit` o `currency` de la oferta ausentes o distintos de la sesión; `currency` en minúsculas | Se toman de la sesión; `currency` se normaliza a mayúsculas | `MISSING_FIELD`, `STATE_MISMATCH`, `INVALID_FORMAT` | D-36, D-39 | AC-01-09, AC-01-32 |
| R-10 | `unitPrice` en forma textual con coma decimal, espacios o símbolo de moneda | Se normaliza a número, interpretado como decimal exacto (`"12,50 €"` → 12.50) | `INVALID_FORMAT` | D-37 | AC-01-08 |
| R-11 | `quantity` como cadena numérica o como número con parte decimal nula | Se convierte a entero | `WRONG_TYPE` | D-39 | AC-01-33 |
| R-12 | `deliveryDays` o `paymentDays` como cadena numérica | Se convierte a entero | `WRONG_TYPE` | D-39 | AC-01-34 |

## Reglas no corregibles

Van a reintento en los dos modos.

| ID | Fallo y detección | Corrección en `TOLERANT` | Código | Decisiones | Criterios |
|---|---|---|---|---|---|
| R-13 | Término negociado ausente, valor fuera de rango (cantidad o precio ≤ 0, días < 0) o valor que exigiría redondear (cantidad no entera, precio con más de 2 decimales) | No corregible. Un término ausente nunca se rellena con la oferta anterior | `MISSING_FIELD`, `OUT_OF_RANGE`, `PRECISION_EXCEEDED` | D-23, D-39 | AC-01-12 |
| R-14 | Sobre `ACCEPT` con una oferta distinta de la vigente, o cuya normalización falla; sobre `WITHDRAW` con oferta | No corregible | `ACT_BODY_MISMATCH` | D-26, D-73 | AC-01-29, AC-03-11 |
| R-15 | `reason` que no es cadena | No corregible | `WRONG_TYPE` | D-43, D-74 | AC-01-30, AC-03-13 |
| R-16 | Encaje nulo o múltiple (un cuerpo vacío encaja con `ACCEPT` y `WITHDRAW`, así que con otro sobre es múltiple); `ACCEPT` en el turno 1 | No corregible | `ACT_BODY_MISMATCH`, `ACT_NOT_ALLOWED` | D-23, D-26 | AC-01-13, AC-03-12 |
| R-17 | `type` del sobre ausente o que no se puede normalizar a un acto | No corregible: su valor no se conoce por el estado | `MISSING_FIELD`, `UNKNOWN_VALUE` | D-23, D-31 | AC-01-35 |

## Registro

Cada corrección aplicada añade una entrada al registro de coerciones (`maquina-estados.md`, sección 3), en la misma transacción que el acto: `code`, `field`, `turn`, `attempt`, `taskId`, valor original, valor corregido, decisión aplicada e instante. La **decisión aplicada** es el `R-xx` de la regla (D-123). `code` se mantiene como vocabulario común con los fallos (D-50).

## Preguntas abiertas

Ninguna.

# Configuración de la sesión

Define con qué valores se ejecuta cada sesión (D-40). El coordinador del comprador la envía, una por partida, en `OPEN_ROUND` (D-88).

Decisiones que lo condicionan: D-08, D-11, D-30, D-36, D-40, D-41, D-51, D-52, D-54, D-56, D-59, D-65, D-67, D-83, D-86, D-88 a D-91, D-99 y D-102.

## Campos

Los nombres de campo van en inglés y camelCase (D-29).

| Campo | Tipo | Obligatorio | Por defecto | Restricción | Decisión |
|---|---|---|---|---|---|
| `fixedTerms` | objeto `{productId, unit, currency}` | Sí | — | `productId` y `unit` no vacíos; `currency` código ISO 4217 | D-36, D-90 |
| `parties` | lista de `{partyId, role, agentCardUrl}` | Sí | — | Exactamente 2; `partyId` distintos; un `role = BUYER` y un `role = SELLER` | D-30, D-41, D-90 |
| `openingPartyId` | cadena | Sí | — | Uno de los `partyId` de `parties` | D-41, D-90 |
| `validationMode` | enumerado `STRICT` / `TOLERANT` | Sí | — | | D-11, D-90 |
| `maxRetries` | entero | No | 2 | ≥ 0. Cuenta reintentos, no intentos | D-08, D-51 |
| `turnTimeoutSeconds` | entero | No | 60 | > 0. También acota la obtención de cada AgentCard (D-99) | D-52 |
| `pollIntervalSeconds` | entero | No | 1 | > 0 y < `turnTimeoutSeconds` | D-59 |
| `maxTurns` | entero | No | 10 | ≥ 2 | D-54, D-56 |
| `holdTimeoutSeconds` | entero | No | 1800 | > 0 | D-86 |

### Campos de cada parte
| Campo | Tipo | Contenido |
|---|---|---|
| `partyId` | cadena | Identificador de la parte en la sesión. Es el valor de `sender` en sus actos (D-30) |
| `role` | enumerado `BUYER` / `SELLER` | Papel de la parte (D-41) |
| `agentCardUrl` | cadena (URL) | Dónde obtener la AgentCard del agente de esa parte, para comprobar la extensión (D-25, D-99) y llamarlo. El orden de `parties` decide `failedPartyId` si fallan las dos AgentCards (D-99) |

## Restricciones en `OPEN_ROUND`
- En todas las sesiones de una ronda, el `partyId` del `BUYER` es el mismo. Si no, se rechaza con `INVALID_CONFIG` (D-102).
- Ese `partyId` coincide con el `sender` de `OPEN_ROUND`. Si es el mismo en todas las sesiones pero distinto del `sender`, se rechaza con `NOT_AUTHORIZED` en `envelope.sender`, en cualquier ronda (D-102).
- Los `itemId` de la ronda son distintos. Si no, se rechaza con `INVALID_CONFIG` (D-92).
- Las rondas siguientes de una petición mantienen el mismo comprador: un `requestId` cuyo comprador no es el `sender` se rechaza con `UNKNOWN_REQUEST` (D-102).
- Si alguna configuración de la ronda incumple una restricción, se rechaza la ronda entera y no se crea ninguna sesión (D-89).

## Valores por defecto y valores efectivos (D-91)
- Los valores por defecto son globales y fijos en el código.
- Las restricciones entre parámetros se comprueban sobre los valores efectivos, ya resueltos con los por defecto. Por ejemplo, `turnTimeoutSeconds = 1` sin `pollIntervalSeconds` incumple «`pollIntervalSeconds` < `turnTimeoutSeconds`».
- El registro de sesión guarda los valores efectivos, no la configuración tal como llegó (`maquina-estados.md`, sección 3).

## Valores que no son parámetros
- `sessionId`: lo genera el orquestador como UUID al crear la sesión (D-67).
- `requestId` y número de ronda: los asigna el orquestador (D-83, D-88).
- Duración del arrendamiento: se deriva como `turnTimeoutSeconds + pollIntervalSeconds` (D-65).

Las restricciones numéricas anteriores son las que exige la máquina de estados (`maquina-estados.md`, sección 5), más la de `holdTimeoutSeconds` (D-86).

## Preguntas abiertas
Ninguna.

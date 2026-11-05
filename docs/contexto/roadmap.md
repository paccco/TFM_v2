# Roadmap

Cada hito agrupa funcionalidades. Cuando se completa una funcionalidad marcada como importante, el Orquestador propone una `release/` (`proceso.md` §10). Cada rama necesita además su propuesta y su «aprobado» (`proceso.md` §5).

Aquí, `AC-cc-nn` es el criterio de aceptación `nn` de la tarjeta `CU-cc`. Cada criterio da al menos un test (`proceso.md` §7). «(parte)» indica un criterio que se reparte entre las dos ramas que lo citan.

| Versión | Hito | Funcionalidades | ¿Importante? | Estado |
|---|---|---|---|---|
| — | Preparación | `feature/docs-alineacion`, `feature/setup` | No | pendiente |
| v0.1.0 | H1 · Negociación de punta a punta | `feature/abrir-ronda`, `feature/turnos`, `feature/cierre-sesion`, `feature/agreement-held`, `feature/resolver-acuerdos`, `feature/e2e-estrategias-fijas` | Sí, la última | pendiente |
| v0.2.0 | H2 · Resto de casos y caminos | `feature/fin-sin-acuerdo`, `feature/rechazos-peticiones`, `feature/reintentos-aborto`, `feature/autocorreccion`, `feature/recuperacion`, `feature/caducidad-plazo`, `feature/varias-sesiones` | Sí, la última | pendiente |
| v0.3.0 | H3 · Agentes LangGraph con SLM | Por concretar al aprobar sus CU | Sí, la última | pendiente |

Estados: pendiente · en curso · publicado.

## Requisito previo

Commit inicial en `main` con la documentación y este roadmap, y después `git flow init` (`proceso.md` §6), confirmados por el desarrollador.

## Preparación

### `feature/docs-alineacion`
- **Qué hace:** sin código. Alinea `proceso.md`, `CLAUDE.md`, `docs/latex/CLAUDE.md`, `maquina-estados.md` §6, `implementar-rama`, `cerrar-release` y el `revisor` con las decisiones. Cierra `autocorreccion.md` como fuente única de las reglas, con prefijo `R-xx`.
- **CU y AC:** ninguno implementado. Las tarjetas pasan a citar `R-xx` y se añaden los criterios de las reglas que no tienen ninguno.
- **Depende de:** requisito previo.
- **Pruebas:** no aplica código. Se comprueba que cada `R-xx` está cubierta por algún `AC-cc-nn` y que `AC` solo significa criterio de aceptación.
- **LaTeX:** ningún capítulo; solo la regla de `docs/latex/CLAUDE.md:24`.

### `feature/setup`
- **CU y AC:** ninguno; es infraestructura.
- **Depende de:** `feature/docs-alineacion`.
- **Resuelve** (`maquina-estados.md` §6, D-13, D-17, D-69, D-97):
  - `a2a-sdk` implementa A2A 1.0 y resuelve con Python 3.14. Si no, 3.13 con aprobación del desarrollador.
  - LangGraph resuelve con la misma versión de Python (lo exige D-13). Solo se comprueba: se añade como dependencia en H3.
  - Versión de PostgreSQL y controlador de Python: se propone con pruebas y decide el desarrollador.
  - Si `a2a-sdk` ofrece un almacén de Tasks en base de datos. Solo sirve si escribe en la misma transacción que las sesiones (D-97).
  - El resultado se registra en `decisiones.md` y `maquina-estados.md` §6, con diff aprobado (`proceso.md` §1). El resto de preguntas de §6 no se tocan.
- **Deja:** `pyproject.toml`, `uv.lock`, `ruff`, `pytest` y la estructura de `src/` que acuerde el desarrollador.
- **Pruebas:** humo: instalación limpia con `uv sync`; conexión a PostgreSQL; transacción entre dos tablas con escritura condicional por versión y lectura del reloj del servidor (D-63, D-69); los documentos LaTeX compilan.
- **LaTeX:** `manual/` Instalación; `tecnica/` Arquitectura (stack).

## H1 · Negociación de punta a punta (v0.1.0)

Comprador con coordinador mínimo y vendedor, con estrategias fijas y sin LLM. Desde aquí el estado vive en PostgreSQL, con arrendamiento y versión (D-04, D-63, D-69).

**Límites de v0.1.0**, que cubre H2:
- Una sesión con `validationMode = TOLERANT` se rechaza con `INVALID_CONFIG` en `body.sessions.<i>.config.validationMode`. `feature/autocorreccion` levanta este límite.
- Una sesión con `maxRetries` efectivo distinto de 0 se rechaza con `INVALID_CONFIG` en `body.sessions.<i>.config.maxRetries`, también si falta el campo, porque su valor por defecto es 2 (D-91). `feature/reintentos-aborto` levanta este límite.
- Un acto no válido, un fallo de Task o un tiempo agotado llevan la sesión a `CLOSING` con `outcome = ABORTED`, `abortReason = RETRIES_EXHAUSTED` y `lastFailure`. Es el estado que ya define la máquina: con `maxRetries = 0`, el primer fallo agota los reintentos (D-07, D-53, `maquina-estados.md` §5). No hay estados ni resultados provisionales.
- Una petición no válida no termina ninguna sesión: la Task queda en `TASK_STATE_REJECTED` con `rejections` y las sesiones no cambian (D-89, D-97, D-110). `feature/rechazos-peticiones` completa los casos restantes.
- Un `OPEN_ROUND` con `requestId` se rechaza con `UNKNOWN_REQUEST` en `body.requestId`, exista o no la petición, y no escribe más que el rechazo. `feature/varias-sesiones` levanta este límite.

### `feature/abrir-ronda`
- **CU y AC:** CU-04. AC-04-01, AC-04-02, AC-04-03, AC-04-05, AC-04-06, AC-04-07, AC-04-09, AC-04-11, AC-04-12, AC-04-13, AC-04-17, AC-04-22, AC-04-23, AC-04-24, AC-04-25, AC-04-27, AC-04-28 a AC-04-31.
- **Depende de:** `feature/setup`.
- **Pruebas:** PostgreSQL real y un servidor A2A de prueba para las AgentCards. La atomicidad se comprueba forzando un fallo dentro de la transacción. AC-04-22, con una segunda instancia que solo comparte la base de datos. Rechazo de `TOLERANT` y de `maxRetries` distinto de 0. Autenticación bearer y orígenes permitidos (D-128, D-129).
- **LaTeX:** `tecnica/` Arquitectura y Protocolo (peticiones del comprador y autenticación); `manual/` Configuración (tokens, orígenes, TLS y límites de v0.1.0).

### `feature/turnos`
- **CU y AC:** CU-01 y CU-03, camino válido hasta `HELD`. AC-01-01, AC-01-02 (parte), AC-01-03, AC-01-15 (parte: `maxRetries = 0`), AC-03-01, AC-03-02, AC-03-03 (parte), AC-03-04, AC-03-06, AC-03-16.
- **Depende de:** `feature/abrir-ronda`.
- **Pruebas:** agente A2A de prueba con respuestas guionizadas, que comprueba cada `TURN_REQUEST` recibido, la paridad y el sondeo. Se comprueban las escrituras de cada transición en PostgreSQL. Aborto con `maxRetries = 0` ante un acto no válido, un fallo de Task y un tiempo agotado, en turno 1 y en turno ≥ 2.
- **LaTeX:** `tecnica/` Protocolo (actos y turno), Máquina de estados y Flujo de una sesión.

### `feature/cierre-sesion`
- **CU y AC:** CU-02. AC-02-01 a AC-02-11, AC-02-13 a AC-02-17.
- **Depende de:** `feature/turnos`, por la parte cliente A2A y los registros.
- **Pruebas:** sesiones sembradas en `CLOSING` con cada `outcome`, también los que aún no se alcanzan en H1. Agentes de prueba que responden con Task, Message, error A2A, error de transporte o silencio.
- **LaTeX:** `tecnica/` Máquina de estados (cierre); `manual/` Leer el resultado.

### `feature/agreement-held`
- **CU y AC:** CU-05. AC-05-01 a AC-05-13.
- **Depende de:** `feature/cierre-sesion`, porque reutiliza el envío de control (`maquina-estados.md` §4).
- **Pruebas:** las mismas variantes de respuesta que `SESSION_CLOSE`, más la permanencia en `HELD` y la liberación del arrendamiento.
- **LaTeX:** `tecnica/` Máquina de estados (acuerdo provisional).

### `feature/resolver-acuerdos`
- **CU y AC:** CU-06, peticiones válidas y rechazo base. AC-06-01, AC-06-02, AC-06-03, AC-06-04, AC-06-06, AC-06-07, AC-06-08, AC-06-09, AC-06-21 (parte: misma instancia).
- **Depende de:** `feature/agreement-held`.
- **Pruebas:** sesiones sembradas en `HELD`; fallo forzado dentro de la transacción; arranque del cierre tras confirmarla; rechazo con `NOT_HELD` sin cambios en las sesiones.
- **LaTeX:** `tecnica/` Protocolo (`RESOLVE_HOLDS`) y Máquina de estados.

### `feature/e2e-estrategias-fijas` (importante)
- **CU y AC:** ningún criterio nuevo; recorre AC-04-09, AC-01-03, AC-03-04, AC-03-06, AC-05-11, AC-06-01 y AC-02-10 de una vez. Añade el comprador (coordinador mínimo y negociador, D-80, D-87) y el vendedor, sin LangGraph. El coordinador envía `validationMode = STRICT` y `maxRetries = 0`.
- **Depende de:** `feature/resolver-acuerdos`.
- **Pruebas:** extremo a extremo con procesos A2A reales. Turno 1, `PROPOSE` del comprador; turno 2, `COUNTEROFFER` del vendedor; turno 3, `ACCEPT` del comprador; `AGREEMENT_HELD`; `RESOLVE_HOLDS`; `SESSION_CLOSE`; sesión en `CLOSED` con `AGREEMENT`, y registros coherentes.
- **LaTeX:** `manual/` Lanzar una negociación; `tecnica/` Flujo de una sesión y Pruebas.

## H2 · Resto de casos y caminos (v0.2.0)

Cada rama de este hito añade su escenario extremo a extremo con agentes simulados.

### `feature/fin-sin-acuerdo`
- **CU y AC:** CU-01 y CU-03. AC-01-16, AC-03-05, AC-03-07.
- **Depende de:** H1.
- **Pruebas:** `WITHDRAW` en el turno 1 y en un turno ≥ 2; `COUNTEROFFER` en el último turno. Se comprueba el `SESSION_CLOSE` resultante.
- **LaTeX:** `tecnica/` Máquina de estados; `manual/` Leer el resultado.

### `feature/rechazos-peticiones`
- **CU y AC:** CU-04 y CU-06. AC-04-14, AC-04-18, AC-04-19; AC-06-10 a AC-06-18, AC-06-22, AC-06-23.
- **Depende de:** H1.
- **Pruebas:** una petición por código de rechazo; duplicados en serie y a la vez, con dos conexiones; plazo vencido con un `heldUntil` sembrado.
- **LaTeX:** `tecnica/` Protocolo (peticiones no válidas); `manual/` Errores visibles.

### `feature/reintentos-aborto`
- **CU y AC:** CU-01 y CU-03. AC-01-02 (parte), AC-01-12 a AC-01-14, AC-01-15 (parte: `maxRetries` > 0), AC-01-17 a AC-01-24, AC-01-27, AC-01-29, AC-01-30; AC-03-03 (parte), AC-03-11, AC-03-12, AC-03-13, AC-03-17, AC-03-18, AC-03-19 (parte: AC-01-14 a AC-01-24), AC-03-20.
- **Levanta:** el límite de `maxRetries` de v0.1.0.
- **Depende de:** `feature/fin-sin-acuerdo`.
- **Pruebas:** agente de prueba que provoca cada fallo y cada estado de Task; agotar `maxRetries`, incluido 0; tiempo agotado durante el envío y durante el sondeo; respuesta tardía descartada.
- **LaTeX:** `tecnica/` Máquina de estados (intentos y aborto) y Protocolo (códigos de fallo); `manual/` Errores visibles.

### `feature/autocorreccion`
- **CU y AC:** CU-01 y CU-03. AC-01-04 a AC-01-11, AC-01-28; AC-03-08, AC-03-09, AC-03-10, AC-03-14, AC-03-15. Más los criterios nuevos de CU-01 que añade `feature/docs-alineacion`, de AC-01-31 en adelante.
- **Levanta:** el límite de `TOLERANT` de v0.1.0.
- **Depende de:** `feature/reintentos-aborto`.
- **Pruebas:** parametrizadas en `TOLERANT` y `STRICT`; cada coerción queda en su registro, con el valor original y el corregido.
- **LaTeX:** `tecnica/` Autocorrección; `manual/` Configuración (`validationMode`).

### `feature/recuperacion`
- **CU y AC:** CU-01 a CU-06. AC-01-25, AC-01-26, AC-02-12, AC-03-19 (parte: AC-01-25 y AC-01-26), AC-04-21, AC-05-15, AC-05-16, AC-06-20, AC-06-21 (parte: otra instancia).
- **Depende de:** `feature/reintentos-aborto`.
- **Pruebas:** dos instancias sobre la misma base de datos; la primera se detiene en cada punto de espera y la segunda la retoma mediante la búsqueda de D-119 y D-120. También arrendamiento vigente frente a caducado.
- **LaTeX:** `tecnica/` Arquitectura (concurrencia y recuperación).

### `feature/caducidad-plazo`
- **CU y AC:** CU-07, más los cruces con CU-05 y CU-06. AC-07-01 a AC-07-14, AC-05-14, AC-06-19.
- **Depende de:** `feature/recuperacion`, porque D-119 exige una única búsqueda.
- **Pruebas:** `holdTimeoutSeconds` corto con el reloj de la base de datos; carreras con `RESOLVE_HOLDS` y entre dos instancias.
- **LaTeX:** `tecnica/` Máquina de estados (caducidad); `manual/` Leer el resultado (`HOLD_EXPIRED`).

### `feature/varias-sesiones` (importante)
- **CU y AC:** CU-04 y CU-06. AC-04-04, AC-04-08, AC-04-10, AC-04-15, AC-04-16, AC-04-20, AC-04-26, AC-06-05, AC-06-24.
- **Levanta:** el límite de `requestId` de v0.1.0.
- **Depende de:** `feature/rechazos-peticiones`, `feature/caducidad-plazo`.
- **Pruebas:** petición con dos partidas en paralelo; segunda ronda con una partida mantenida (D-79); competencia entre instancias y entre rondas; extremo a extremo con el coordinador mínimo.
- **LaTeX:** `tecnica/` Flujo de una sesión (peticiones compuestas); `manual/` Lanzar una negociación.

## H3 · Agentes LangGraph con SLM (v0.3.0)

Aún no tiene CU ni AC, así que sus ramas no se pueden proponer (`proceso.md` §5). Falta diseñar, y lo decide el desarrollador:
- los agentes vendedor y comprador, con su negociador y su coordinador (D-06, D-76 a D-81);
- las preguntas de `maquina-estados.md` §6 que se dejan para ese momento: almacén de Tasks de los agentes y fallo de `AGREEMENT_HELD` a un vendedor;
- el SLM y su despliegue.

- **Ramas previstas:** una `feature/docs-` para las tarjetas y, después, las `feature/` que salgan de ellas.
- **Depende de:** H2.
- **Pruebas:** los AC de las tarjetas nuevas.
- **LaTeX:** `tecnica/` Arquitectura (agentes) y Pruebas; `manual/` Lanzar una negociación.

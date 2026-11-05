# Registro de decisiones

Decisiones cerradas. El agente no las reabre salvo que el desarrollador lo pida. Para cambiar una, se añade una nueva que la sustituya y se marca la antigua como «Sustituida por D-xx».

Formato de cada entrada: ID, fecha, decisión, motivo, alternativas descartadas.

## Alcance

### D-01 · Reescritura en Python
- **Fecha:** 2026-11
- **Decisión:** el orquestador se implementa en Python en lugar de .NET.
- **Motivo:** que el desarrollador entienda todo el código.

### D-02 · Autocorrección solo estructural
- **Fecha:** 2026-11
- **Decisión:** la autocorrección aplica reglas deterministas sobre la estructura del mensaje. Los fallos de contenido quedan fuera del alcance.
- **Concretada por D-22.**

### D-03 · Dominio
- **Fecha:** 2026-11
- **Decisión:** negociación genérica de compraventa entre negocios.
- **Sustituida por D-75.**

## Arquitectura

### D-04 · Orquestador sin estado en proceso
- **Fecha:** 2026-11
- **Decisión:** el orquestador no guarda estado en memoria; el estado de sesión está externalizado.
- **Precisada por D-97.**

### D-05 · Modelo pull
- **Fecha:** 2026-11
- **Decisión:** el orquestador consulta al agente que tiene el turno.

### D-06 · Un agente privado por empresa
- **Fecha:** 2026-11
- **Decisión:** cada empresa tiene su agente LangGraph privado expuesto tras A2A. Escenario: SLMs desplegados en la nube.

### D-07 · Fallback único ABORTAR
- **Fecha:** 2026-11
- **Decisión:** cuando no se puede recuperar, la sesión se aborta.
- **Descartado:** PAUSAR.

### D-08 · Reintentos por turno
- **Fecha:** 2026-11
- **Decisión:** los reintentos se cuentan por turno.

## Protocolo

### D-09 · Actos del protocolo
- **Fecha:** 2026-11
- **Decisión:** actos PROPONER, CONTRAOFERTA, ACEPTAR y RETIRARSE, con ofertas alternas tipo Rubinstein.
- **Descartado:** RECHAZAR.
- **Sustituida por D-32.**

### D-10 · Ofertas completas
- **Fecha:** 2026-11
- **Decisión:** cada oferta incluye todos sus términos, no solo los que cambian.

### D-11 · Modo de validación por sesión
- **Fecha:** 2026-11
- **Decisión:** configurable por sesión: estricto, o tolerante con registro de coerciones.
- **Precisada por D-90.**

## Stack

### D-12 · Gestor de entorno y dependencias
- **Fecha:** 2026-11
- **Decisión:** `uv`. Dependencias con `uv add`; `uv.lock` versionado.

### D-13 · Versión de Python
- **Fecha:** 2026-11
- **Decisión:** Python 3.14, provisional hasta que `feature/setup` confirme que LangGraph y el SDK de A2A resuelven con ella. Si no, 3.13, con aprobación del desarrollador.
- **Descartado:** 3.15, por recién publicada (riesgo de dependencias sin soporte).
- **Precisada por D-124.**

### D-14 · Tests
- **Fecha:** 2026-11
- **Decisión:** `pytest`.

### D-15 · Lint y formato
- **Fecha:** 2026-11
- **Decisión:** `ruff`, para ambas cosas.

### D-16 · Tipos
- **Fecha:** 2026-11
- **Decisión:** anotaciones de tipo en todo el código, sin comprobador de tipos por ahora. Se revisará si hace falta.

## Correspondencia con A2A

### D-17 · A2A 1.0 como base
- **Fecha:** 2026-11
- **Decisión:** el protocolo se apoya en la especificación A2A 1.0. El orquestador es cliente A2A y cada agente de empresa es servidor A2A.
- **Motivo:** es la versión estable vigente, y cambia la estructura de Part, Message y los enumerados respecto a la 0.3.
- **Descartado:** A2A 0.3.

### D-18 · Protocolo como extensión A2A obligatoria
- **Fecha:** 2026-11
- **Decisión:** el protocolo de negociación se define como extensión A2A con URI propia, declarada `required = true` en la AgentCard, activada con la cabecera `A2A-Extensions` y listada en `extensions` de cada Message y Artifact del protocolo.
- **Motivo:** es el mecanismo oficial de A2A para añadir semántica propia sin alterar sus estructuras.

### D-19 · Sobre en metadata, cuerpo en Part data
- **Fecha:** 2026-11
- **Decisión:** los campos comunes van en `metadata[<URI-extensión>]` del Message o Artifact. El cuerpo va en una única Part `data`, identificada por `mediaType` propio.
- **Motivo:** ceñirse al uso de extensiones que recomienda A2A, que es poner los atributos propios en metadata.
- **Descartado:** todo dentro de la Part `data`; transportar el acto como Part `text`.
- **Precisada por D-104.**

### D-20 · Una Task por turno
- **Fecha:** 2026-11
- **Decisión:** cada turno es una Task y el acto es un Artifact de esa Task. Hay un `contextId` por agente y sesión, generado por el servidor y guardado en el estado externalizado.
- **Motivo:** cada turno termina en estado terminal, lo que encaja con D-04 y D-08, y la Task se puede consultar después.
- **Descartado:** una Task larga por sesión con `INPUT_REQUIRED`; respuesta con Message sin Task.
- **Precisada por D-62.**

### D-21 · Familias de mensaje: actos y control
- **Fecha:** 2026-11
- **Decisión:** el protocolo distingue actos (del agente al orquestador) y mensajes de control (del orquestador al agente: petición de turno y cierre de sesión).
- **Motivo:** el orquestador necesita pedir el turno y comunicar el resultado sin inventar actos de negociación.
- **Ampliada por D-87.**

### D-22 · La autocorrección solo actúa sobre objetos ya interpretados
- **Fecha:** 2026-11
- **Decisión:** la autocorrección actúa sobre sobre y cuerpo ya interpretados. El JSON mal formado y el texto libre quedan fuera. Concreta D-02.
- **Descartado:** aceptar Parts `text` y repararlas.

### D-23 · Respuestas no corregibles van a reintento
- **Fecha:** 2026-11
- **Decisión:** si la Task termina en FAILED o REJECTED, o no trae exactamente un Artifact con una única Part `data` de acto, no se intenta corregir: se reintenta (D-08) y, agotados los reintentos, se aborta (D-07).
- **Motivo:** sin un objeto interpretado no hay estructura sobre la que aplicar reglas (D-22).
- **Ampliada por D-60 y D-71. Precisada por D-62 y D-68.**

### D-24 · Turno en modo bloqueante
- **Fecha:** 2026-11
- **Decisión:** `SendMessage` con `returnImmediately = false`.
- **Motivo:** más simple; D-20 permite pasar a sondeo más adelante sin rediseñar.
- **Descartado:** `returnImmediately = true` con sondeo.
- **Sustituida por D-58.**

### D-25 · Extensión obligatoria para iniciar sesión
- **Fecha:** 2026-11
- **Decisión:** si la AgentCard de algún agente no declara la extensión con `required = true`, la sesión no se inicia.
- **Precisada por D-99.**

### D-26 · Fallo de coherencia entre sobre y cuerpo: manda el cuerpo
- **Fecha:** 2026-11
- **Decisión:** la contradicción entre el tipo de acto del sobre y el esquema del cuerpo se registra como fallo de coherencia (estructural, D-02). En modo tolerante se corrige el sobre según el cuerpo si este encaja con un único acto; en modo estricto, o si el encaje es nulo o múltiple, se reintenta.
- **Motivo:** el cuerpo tiene más campos que el tipo de acto del sobre y permite deducir el acto sin inventar datos.
- **Descartado:** que mande el sobre; llamarlo «alucinación», porque sugiere un fallo de contenido, fuera de alcance por D-02.
- **Precisada por D-44, D-72 y D-73.**

### D-27 · URI de la extensión
- **Fecha:** 2026-11
- **Decisión:** la extensión se identifica como `urn:tfm:negociacion:v1`. Un cambio incompatible del protocolo incrementa la versión final.
- **Motivo:** no depende de ningún recurso alojado ni se confunde con la dirección de las AgentCards.
- **Descartado:** URL del repositorio, porque no hay nada publicado todavía.

## Esquema de mensaje

### D-28 · El agente repite sesión y turno
- **Fecha:** 2026-11
- **Decisión:** el orquestador envía `sessionId` y `turn` en la petición de turno, y el agente los devuelve en el sobre de su acto.
- **Motivo:** permite detectar respuestas fuera de sitio (por ejemplo, la respuesta tardía a un intento anterior) y corregirlas de forma determinista con el estado.
- **Descartado:** sobre mínimo del agente con solo el tipo.

### D-29 · Nombres de campo en inglés y camelCase
- **Fecha:** 2026-11
- **Decisión:** los nombres de campo del protocolo van en inglés y camelCase.
- **Motivo:** coherencia con la convención JSON de A2A 1.0.

### D-30 · Identificador de empresa en la configuración de la sesión
- **Fecha:** 2026-11
- **Decisión:** el identificador de cada empresa se asigna en la configuración de la sesión.
- **Motivo:** el `name` de una AgentCard no está pensado como clave estable.
- **Descartado:** tomarlo de la AgentCard.
- **Precisada por D-90.**

### D-31 · El sobre solo se corrige con datos del estado o normalización
- **Fecha:** 2026-11
- **Decisión:** un campo del sobre solo se corrige si su valor correcto se conoce por el estado externalizado o por normalización determinista del propio valor; nunca se deduce del contenido. En modo estricto no se corrige: se registra y se reintenta.
- **Motivo:** mantiene la corrección dentro de lo estructural (D-02) y determinista.

### D-32 · Actos del protocolo (en inglés)
- **Fecha:** 2026-11
- **Decisión:** actos `PROPOSE`, `COUNTEROFFER`, `ACCEPT` y `WITHDRAW`, con ofertas alternas tipo Rubinstein. Los mensajes de control son `TURN_REQUEST` y `SESSION_CLOSE`, y el emisor del orquestador es `ORCHESTRATOR`. Sustituye a D-09: los actos son los mismos en significado y solo cambian de nombre.
- **Motivo:** coherencia con los nombres de campo en inglés (D-29).
- **Descartado:** REJECT (como en D-09); mantener los valores en español.
- **Ampliada por D-85.**

### D-33 · Contador de turnos único por sesión
- **Fecha:** 2026-11
- **Decisión:** `turn` es un contador único por sesión que empieza en 1 y sube cada vez que el turno pasa al otro agente. Los reintentos no lo incrementan.
- **Motivo:** con ofertas alternas, la paridad del turno identifica qué agente lo tiene.
- **Descartado:** un contador por agente.

### D-34 · Campos no definidos
- **Fecha:** 2026-11
- **Decisión:** en modo tolerante se descartan y se registra la coerción; en modo estricto son fallo y se reintenta.
- **Motivo:** un campo inesperado suele indicar que el SLM ha mezclado estructuras.
- **Precisada por D-72.**

## Oferta

### D-35 · Un producto por sesión
- **Fecha:** 2026-11
- **Decisión:** cada sesión negocia un único producto.
- **Motivo:** el modelo de Rubinstein negocia un conjunto fijo de términos; varias líneas complican la validación sin aportar al objetivo del TFM.
- **Descartado:** ofertas con varias líneas de pedido.

### D-36 · Términos fijados por la sesión y negociados
- **Fecha:** 2026-11
- **Decisión:** la configuración de la sesión fija `productId`, `unit` y `currency`, y la oferta los repite. Se negocian `quantity`, `unitPrice`, `deliveryDays` y `paymentDays`. Todos son obligatorios (D-10).
- **Motivo:** los fijos se pueden validar y corregir con el estado.
- **Precisada por D-90.**

### D-37 · Precio como número interpretado como decimal exacto
- **Fecha:** 2026-11
- **Decisión:** `unitPrice` es un número JSON que el orquestador interpreta como decimal exacto, nunca como coma flotante. En modo tolerante se normalizan formas textuales del precio.
- **Motivo:** es el formato que un SLM genera con más naturalidad.
- **Descartado:** precio como cadena.

### D-38 · La oferta no incluye importe total
- **Fecha:** 2026-11
- **Decisión:** no hay campo de importe total.
- **Motivo:** es redundante y abriría fallos aritméticos ajenos al objetivo.

### D-39 · Criterio de corrección de la oferta
- **Fecha:** 2026-11
- **Decisión:** se extiende D-31 a la oferta. Un término ausente, fuera de rango o que exigiría redondear no se corrige: se reintenta. Un término ausente nunca se completa con la oferta anterior.
- **Motivo:** completar o redondear sería decidir contenido de la negociación (D-02).

### D-40 · Configuración de la sesión en documento propio
- **Fecha:** 2026-11
- **Decisión:** la configuración de la sesión se documenta en `configuracion-sesion.md`, fuera de `protocolo.md`.
- **Motivo:** el protocolo define mensajes; la configuración define con qué valores se ejecuta cada sesión.
- **Ampliada por D-59, D-86 y D-90.**

## Actos y control

### D-41 · Apertura y papeles en la configuración de la sesión
- **Fecha:** 2026-11
- **Decisión:** la configuración de la sesión indica qué empresa abre y el papel de cada una (comprador o vendedor).
- **Descartado:** que abra siempre el comprador.
- **Precisada por D-90.**

### D-42 · ACCEPT sin campos
- **Fecha:** 2026-11
- **Decisión:** ACCEPT no lleva campos y acepta la última oferta del rival.
- **Motivo:** con ofertas alternas solo hay una oferta aceptable, y el eco del turno (D-28) ya detecta aceptaciones fuera de sitio.
- **Descartado:** `acceptedTurn`; repetir la oferta aceptada.
- **Precisada por D-73, D-77 y D-84.**

### D-43 · WITHDRAW con motivo opcional
- **Fecha:** 2026-11
- **Decisión:** WITHDRAW admite `reason` (cadena, opcional), validado solo por tipo.
- **Motivo:** útil para el registro y el análisis; su contenido queda fuera de alcance (D-02).
- **Precisada por D-74.**

### D-44 · PROPOSE y COUNTEROFFER se distinguen por el turno
- **Fecha:** 2026-11
- **Decisión:** en modo tolerante, el tipo entre PROPOSE y COUNTEROFFER se corrige según el turno. Precisa D-26.
- **Motivo:** comparten cuerpo; el turno es dato del estado (D-31) y elimina la ambigüedad.
- **Precisada por D-73.**

### D-45 · Ofertas repetidas permitidas
- **Fecha:** 2026-11
- **Decisión:** el protocolo no prohíbe repetir ofertas.
- **Motivo:** es estrategia (contenido), fuera de alcance por D-02.

### D-46 · TURN_REQUEST autosuficiente
- **Fecha:** 2026-11
- **Decisión:** cada TURN_REQUEST incluye papel, términos fijos y actos permitidos, no solo el primero.
- **Motivo:** el agente no guarda estado de sesión, en coherencia con D-04; se evita que la configuración del agente no coincida con la de la sesión.
- **Descartado:** que cada empresa configure esos datos en su agente.

### D-47 · Actos permitidos explícitos
- **Fecha:** 2026-11
- **Decisión:** TURN_REQUEST incluye `allowedActs`.
- **Motivo:** decirle al SLM qué actos puede usar reduce fallos de antemano.
- **Descartado:** que el agente lo deduzca del turno.

### D-48 · Motivo del reintento al agente
- **Fecha:** 2026-11
- **Decisión:** en los reintentos, TURN_REQUEST incluye `retryReason` con los fallos del intento anterior.
- **Motivo:** ayuda al agente a no repetir el error. Es información para el agente, no una corrección (D-02).

### D-49 · SESSION_CLOSE no espera acto
- **Fecha:** 2026-11
- **Decisión:** la respuesta del agente a SESSION_CLOSE se registra y se ignora; un fallo en el envío no altera el resultado.
- **Precisada por D-64, D-70 y D-84.**

## Fallos, límites y cierre

### D-50 · Catálogo de códigos de fallo
- **Fecha:** 2026-11
- **Decisión:** catálogo único de códigos en la sección «Códigos de fallo» de `protocolo.md`, usado en `retryReason` y en los registros de fallos y coerciones. El campo se indica con ruta con puntos y prefijo `envelope`, `body` o `task`.
- **Motivo:** fallos y coerciones comparten vocabulario, y `retryReason` forma parte del protocolo.
- **Ampliada por D-60, D-71, D-89, D-100 y D-103.**

### D-51 · Máximo de reintentos por turno
- **Fecha:** 2026-11
- **Decisión:** configurable por sesión, con 2 reintentos por defecto (3 intentos). El parámetro cuenta reintentos, no intentos.
- **Motivo:** margen para un fallo puntual del SLM sin alargar sesiones rotas.

### D-52 · Tiempo máximo por turno
- **Fecha:** 2026-11
- **Decisión:** configurable por sesión, con 60 s por defecto. Superarlo es un intento fallido (`TURN_TIMEOUT`), se envía `CancelTask` sin esperar resultado y las respuestas tardías se descartan por `taskId`. Precisa D-58.
- **Motivo:** los SLMs en la nube tienen latencia variable; el `taskId` del intento en curso identifica las respuestas válidas.

### D-53 · Motivo de aborto con último fallo
- **Fecha:** 2026-11
- **Decisión:** `abortReason` es un enumerado cuyo único valor actual es `RETRIES_EXHAUSTED`, acompañado de `lastFailure` con el último fallo del turno.
- **Motivo:** todo aborto pasa por agotar reintentos; `lastFailure` explica por qué.
- **Precisada por D-61.**

### D-54 · Máximo de turnos y resultado NO_AGREEMENT
- **Fecha:** 2026-11
- **Decisión:** máximo de turnos configurable por sesión. Al alcanzarlo, la sesión termina con `outcome = NO_AGREEMENT`.
- **Motivo:** agotar los turnos es un final normal de la negociación, no un fallo irrecuperable; no afecta a D-07.
- **Descartado:** tratarlo como `ABORTED` con `TURN_LIMIT_REACHED`.

### D-55 · SESSION_CLOSE en el caso de uso de cierre
- **Fecha:** 2026-11
- **Decisión:** el envío de SESSION_CLOSE pertenece al CU de cierre; los demás casos de uso terminan al pasar la sesión a cierre.
- **Precisada por D-64.**

### D-56 · Máximo de turnos por defecto
- **Fecha:** 2026-11
- **Decisión:** `maxTurns` vale 10 por defecto y debe ser ≥ 2.
- **Motivo:** cinco ofertas por empresa bastan para ver si una estrategia converge. Con menos de 2 turnos no cabe ninguna aceptación.

### D-57 · El último turno termina sin respuesta
- **Fecha:** 2026-11
- **Decisión:** si el último turno termina en COUNTEROFFER, la sesión cierra con NO_AGREEMENT. TURN_REQUEST incluye `turnsLeft` para que el agente sepa que es el último turno.
- **Motivo:** la regla de cada turno es la misma hasta el final.
- **Descartado:** un turno de cierre extra en el que solo se permite ACCEPT o WITHDRAW.

## Máquina de estados

Diseño completo en `maquina-estados.md`.

### D-58 · Turno con sondeo
- **Fecha:** 2026-11
- **Decisión:** `SendMessage` con `returnImmediately = true`. El orquestador guarda en el estado externalizado el `taskId` y, en el primer turno de cada agente, el `contextId` devueltos antes de empezar a esperar. Después consulta la Task con `GetTask` hasta que llega a un estado final o se supera el tiempo máximo del turno (D-52). Sustituye a D-24.
- **Motivo:** en modo bloqueante, si se supera el tiempo del turno, el orquestador no conoce el `taskId`, que A2A reserva al servidor, ni el `contextId` en el primer turno de cada agente, que D-20 deja al servidor. Sin ellos no se puede enviar `CancelTask`, ni rellenar `referenceTaskIds`, ni descartar respuestas tardías (D-20, D-52), ni retomar la espera tras una caída (D-04).
- **Descartado:** mantener el modo bloqueante con excepciones para el caso de tiempo superado.
- **Precisada por D-52 y D-68.**

### D-59 · Intervalo de sondeo
- **Fecha:** 2026-11
- **Decisión:** `pollIntervalSeconds` en la configuración de la sesión: 1 s por defecto, mayor que 0 y menor que `turnTimeoutSeconds`. Amplía D-40.
- **Motivo:** ajustar el sondeo a la latencia de cada despliegue sin tocar código.

### D-60 · Estados de la Task no previstos en D-23
- **Fecha:** 2026-11
- **Decisión:** una Task en `TASK_STATE_CANCELED` falla con `TASK_CANCELED`. Una Task en `TASK_STATE_INPUT_REQUIRED`, en `TASK_STATE_AUTH_REQUIRED` o en cualquier estado fuera de la lista conocida (incluido `TASK_STATE_UNSPECIFIED`) falla con `TASK_INTERRUPTED`, y se envía `CancelTask` sin esperar resultado. Ninguno de los dos fallos es corregible: se pasa a reintento. Amplía D-23 y D-50.
- **Motivo:** sin esta regla, el sondeo esperaría hasta agotar el tiempo del turno ante un estado que no va a cambiar.

### D-61 · Elección de `lastFailure`
- **Fecha:** 2026-11
- **Decisión:** si el último intento tiene varios fallos, `lastFailure` es el primero según el orden de validación: Task, sobre, cuerpo, coherencia. Precisa D-53.
- **Motivo:** es determinista y apunta a la causa más temprana.
- **Descartado:** convertir `lastFailure` en una lista.

### D-62 · Respuesta con Message en lugar de Task
- **Fecha:** 2026-11
- **Decisión:** si `SendMessage` responde con un Message, el intento falla con `MISSING_ACT` en el campo `task`, sin `taskId`. Precisa D-20 y D-23.
- **Motivo:** no hay Artifact de acto, y así no hace falta un código nuevo.
- **Precisada por D-68.**

### D-63 · Control de concurrencia del estado
- **Fecha:** 2026-11
- **Decisión:** el registro de sesión lleva un arrendamiento (instancia que la procesa y caducidad) y un número de versión. Una instancia solo retoma una sesión si su arrendamiento ha caducado, y lo renueva mientras trabaja. Toda escritura exige que la versión no haya cambiado desde la lectura; si cambió, la escritura se rechaza y la instancia descarta su trabajo. Cada transición escribe el registro de sesión y las entradas de los registros de forma atómica.
- **Motivo:** la recuperación tras caída (D-04) permite que dos instancias procesen la misma sesión. El arrendamiento evita casi todo el trabajo duplicado y la versión impide que el estado se corrompa.
- **Descartado:** solo versión, porque no permite saber cuándo retomar una sesión.
- **Precisada por D-65, D-96, D-108, D-119 y D-121.**

### D-64 · Envío de `SESSION_CLOSE`
- **Fecha:** 2026-11
- **Decisión:** se envía a ambas empresas, con su `contextId` si lo tienen, mediante `SendMessage` con `returnImmediately = true` y sin sondeo. Hay un intento por empresa, sin reintento, y los envíos son independientes. Si se produce un error de transporte o no hay respuesta en `turnTimeoutSeconds`, el envío se marca como fallido. El sobre lleva el `turn` del turno que provocó el cierre. Precisa D-49 y D-55.
- **Motivo:** el orquestador no espera ningún acto y el fallo no altera el resultado, así que basta con un envío acotado.
- **Precisada por D-70 y D-71.**

### D-65 · Duración del arrendamiento
- **Fecha:** 2026-11
- **Decisión:** el arrendamiento dura `turnTimeoutSeconds + pollIntervalSeconds` y se renueva en cada transición, en cada sondeo y antes de cada `SendMessage`. No es un parámetro configurable. Precisa D-63.
- **Motivo:** el intervalo más largo sin renovar es una llamada a `SendMessage`, acotada por `turnTimeoutSeconds`. Derivarlo de la sesión garantiza que siempre la cubre.
- **Descartado:** un parámetro de despliegue fijo.
- **Precisada por D-108.**

### D-66 · `messageId` persistido
- **Fecha:** 2026-11
- **Decisión:** el orquestador genera el `messageId` de cada intento al entrar en `READY` y lo guarda en el registro de sesión. Si reenvía el intento tras una caída, reutiliza el mismo `messageId`.
- **Motivo:** A2A permite a los agentes detectar duplicados por `messageId`, lo que evita la Task huérfana cuando el orquestador cae justo después de enviar.

### D-67 · Generación de `sessionId`
- **Fecha:** 2026-11
- **Decisión:** el orquestador genera `sessionId` como UUID al crear la sesión. La creación es una escritura condicional que falla si el identificador ya existe.
- **Motivo:** no depende del almacén y cumple la restricción del sobre.

### D-68 · Task desaparecida durante el sondeo
- **Fecha:** 2026-11
- **Decisión:** si `GetTask` responde `TaskNotFoundError`, el intento falla con `MISSING_ACT` en el campo `task`. Precisa D-58 y D-62.
- **Motivo:** ya no hay forma de obtener el acto; seguir sondeando solo agotaría el tiempo del turno.

## Almacén del estado

### D-69 · Almacén del estado: PostgreSQL
- **Fecha:** 2026-11
- **Decisión:** el estado externalizado se guarda en PostgreSQL. El registro de sesión y los registros de solo añadir (actos aceptados, fallos y coerciones) son tablas de la misma base de datos y se escriben en la misma transacción. Arrendamientos e instantes se miden con el reloj del servidor de base de datos. La versión de PostgreSQL y el controlador de Python se fijan en `feature/setup`.
- **Motivo:** cumple todos los requisitos de `maquina-estados.md` sin piezas extra: transacciones entre tablas, escritura condicional por versión (D-63, D-67), un único reloj (D-65), búsqueda de sesiones con el arrendamiento caducado y consultas para el análisis.
- **Descartado:** SQLite, porque limita la recuperación a la misma máquina; Redis, por las transacciones entre estructuras y el análisis; Firestore, por la dependencia de un proveedor y la dificultad de los tests.
- **Precisada por D-107 y D-125.**

## Cierre y validación de actos

Decisiones tomadas al diseñar CU-02 y CU-03.

### D-70 · Registro de envíos de cierre
- **Fecha:** 2026-11
- **Decisión:** registro de solo añadir con una entrada por cada envío de `SESSION_CLOSE`: empresa, `turn`, instante, resultado (enviado o fallido) y, según el caso, `taskId` y estado de la Task, indicación de que llegó un Message, o código del fallo (`AGENT_UNREACHABLE`, `TURN_TIMEOUT` o `AGENT_ERROR`). Se escribe en la misma transacción que la marca del envío en el registro de sesión. Las definiciones de `AGENT_UNREACHABLE` y `TURN_TIMEOUT` se amplían al envío de cierre. Precisa D-49 y D-64.
- **Motivo:** D-49 pide registrar la respuesta y `maquina-estados.md` no tenía dónde. El registro de fallos es por intento de turno y exige `attempt` y `field`.
- **Descartado:** reutilizar el registro de fallos; guardar solo el estado del envío en el registro de sesión.
- **Precisada por D-85.**

### D-71 · Respuesta de error A2A a `SendMessage`
- **Fecha:** 2026-11
- **Decisión:** si el agente responde a `SendMessage` con un error A2A en lugar de una Task o un Message, en un turno el intento falla con `AGENT_ERROR` en el campo `task`, sin `taskId`; no es corregible y pasa a reintento con el error en `retryReason`. En el cierre, el envío se marca como fallido con `AGENT_ERROR`, sin reintento. Amplía D-23 y D-50; precisa D-64.
- **Motivo:** el agente recibió la petición y la rechazó; no es un error de transporte. El reintento con `retryReason` es el mecanismo existente para pedir al agente que se corrija.
- **Descartado:** que el orquestador se autocorrija, porque construye sus mensajes de forma determinista; reintentar el cierre, porque contradice D-64; ampliar `AGENT_UNREACHABLE`, porque no distingue en el análisis un agente inalcanzable de uno que rechaza la petición.

### D-72 · El encaje del cuerpo se evalúa antes de validarlo
- **Fecha:** 2026-11
- **Decisión:** el encaje del cuerpo con los esquemas de los actos se evalúa sobre el cuerpo tal como llega, antes de descartar campos no definidos (D-34). Si el tipo se corrige (D-26), el cuerpo se valida con el tipo corregido. El orden de `lastFailure` no cambia (D-61). Precisa D-26 y D-34.
- **Motivo:** si los campos se descartaran antes, un cuerpo de `WITHDRAW` con sobre `ACCEPT` quedaría vacío y se aceptaría como acuerdo.
- **Descartado:** validar el cuerpo según el tipo del sobre antes de evaluar el encaje.

### D-73 · `ACCEPT` con la oferta vigente repetida
- **Fecha:** 2026-11
- **Decisión:** en modo tolerante, un `ACCEPT` cuyo cuerpo trae una oferta idéntica a la vigente tras normalizarla se mantiene como `ACCEPT`: la oferta se descarta y se registra la coerción con `ACT_BODY_MISMATCH`. D-44 solo corrige entre `PROPOSE` y `COUNTEROFFER` cuando el sobre es uno de los dos. Cualquier otro sobre `ACCEPT` o `WITHDRAW` con oferta tiene un encaje no corregible y se reintenta. Precisa D-26, D-42 y D-44.
- **Motivo:** corregir entre actos de efecto opuesto decidiría el resultado de la negociación (D-02). La oferta repetida se recupera comparándola con un dato del estado (D-31), sin cambiar el sentido del acto.
- **Descartado:** corregir `ACCEPT` o `WITHDRAW` con oferta a `COUNTEROFFER`; reintentar siempre.

### D-74 · `reason` con tipo incorrecto
- **Fecha:** 2026-11
- **Decisión:** un `reason` que no sea cadena falla con `WRONG_TYPE` en `body.reason` y no es corregible en ningún modo. Precisa D-43.
- **Motivo:** solo los números tendrían una conversión natural a cadena, y D-43 limita la validación de `reason` a su tipo.
- **Descartado:** convertirlo a cadena en modo tolerante.

## Peticiones compuestas

Decisiones tomadas al ampliar el alcance a lo que espera Unicaja: un agente que negocie con uno o varios para cerrar una compraventa, de forma trazable con A2A.

### D-75 · Ámbito: compradores particulares o negocios
- **Fecha:** 2026-11
- **Decisión:** el comprador puede ser un particular o un negocio; los vendedores son negocios. Sustituye a D-03.
- **Motivo:** el caso de uso que plantea Unicaja (p. ej. «viaje a Madrid por 200 €») incluye compradores particulares.
- **Descartado:** limitar el ámbito a compraventa entre negocios.

### D-76 · Petición compuesta
- **Fecha:** 2026-11
- **Decisión:** una petición del usuario con un presupuesto total se descompone en varias negociaciones en paralelo, una sesión por partida (D-35). Cada sesión se decide teniendo en cuenta el estado de las demás.
- **Motivo:** una compra real puede requerir varios productos de vendedores distintos bajo un mismo presupuesto.
- **Descartado:** negociar las partidas en secuencia, porque pierde el paralelismo.

### D-77 · Acuerdos provisionales hasta cerrar el paquete
- **Fecha:** 2026-11
- **Decisión:** el acuerdo de una sesión no es firme hasta que el paquete completo encaja en el presupuesto o el usuario aprueba el ajuste. Si la petición termina sin compra, los acuerdos provisionales se liberan. Precisa D-42: `ACCEPT` produce un acuerdo provisional. La fase de confirmación y liberación queda pendiente de diseño.
- **Motivo:** permite renegociar (D-78, D-79) sin duplicar compras ni dejar al usuario con partidas sueltas.
- **Descartado:** acuerdos vinculantes con presupuesto repartido de antemano; negociación secuencial.
- **Precisada por D-84.**

### D-78 · Presupuesto inviable
- **Fecha:** 2026-11
- **Decisión:** si los acuerdos no caben en el presupuesto, se presenta al usuario una corrección aproximada (D-81) y se espera su aprobación antes de abrir una nueva ronda. Si no la aprueba, la petición termina sin compra.
- **Motivo:** el usuario decide si acepta pagar más; un presupuesto inviable es un final normal de la ronda, no un fallo irrecuperable, y no afecta a D-07.

### D-79 · Alcance de la nueva ronda
- **Fecha:** 2026-11
- **Decisión:** el usuario decide qué partidas se renegocian y cuáles mantienen su acuerdo provisional.
- **Motivo:** renegociar solo lo que falló es más rápido; reabrir todo permite redistribuir el presupuesto. Elegir es del usuario.
- **Descartado:** fijar una de las dos opciones en el sistema.

### D-80 · Coordinación en el agente comprador
- **Fecha:** 2026-11
- **Decisión:** la coordinación entre las sesiones de una petición vive en el agente del comprador, con dos niveles: un coordinador de la petición y un negociador por sesión que responde a los `TURN_REQUEST`. El orquestador media cada sesión por separado y no conoce el presupuesto ni su reparto. El coordinador guarda su propio estado de la petición y recibe las aprobaciones del usuario (D-78, D-79).
- **Motivo:** el orquestador es el árbitro neutral y la fuente de la traza; conocer el presupuesto del comprador le daría información privada de una parte (D-06).
- **Descartado:** que el orquestador haga de coordinador.

### D-81 · Cálculo de la corrección aproximada
- **Fecha:** 2026-11
- **Decisión:** el coordinador calcula la corrección sumando el importe (`unitPrice × quantity`, D-38) de la última oferta del vendedor en cada partida sin acuerdo viable y el importe de las partidas con acuerdo provisional. Una partida sin ninguna oferta del vendedor queda sin estimación y se le dice así al usuario.
- **Motivo:** es un dato observado en la negociación y trazable. Se usa la última oferta, no la más baja, porque D-45 permite estrategias no monótonas.
- **Descartado:** la oferta más baja del vendedor; una estimación propia del agente.

### D-82 · `SESSION_CLOSE` con las últimas ofertas
- **Fecha:** 2026-11
- **Decisión:** si el resultado no es `AGREEMENT`, el cuerpo de `SESSION_CLOSE` incluye la última oferta de cada parte que haya llegado a ofertar. Nombre del campo pendiente de fijar en `protocolo.md`. Obliga a revisar AC-02-03.
- **Motivo:** si el último turno es del vendedor y termina en `COUNTEROFFER` (D-57), el comprador nunca recibe esa oferta y D-81 quedaría desfasada. La oferta ya iba dirigida al rival, así que no rompe la neutralidad.
- **Descartado:** usar la última oferta del vendedor que vio el comprador.

### D-83 · Agrupación de sesiones por petición
- **Fecha:** 2026-11
- **Decisión:** el orquestador agrupa las sesiones de una petición bajo un `requestId`, que genera como UUID al abrir la primera ronda, y numera las rondas (`round`). Guarda qué sesiones pertenecen a cada ronda y qué partidas se renegocian o mantienen su acuerdo provisional. No guarda el presupuesto ni la corrección propuesta al usuario.
- **Motivo:** la trazabilidad debe mostrar la compraventa completa, no sesiones sueltas, sin exponer los límites privados del comprador (D-80).
- **Descartado:** que la agrupación viva solo en el coordinador.

## Confirmación de acuerdos

Decisiones tomadas al diseñar la fase de confirmación y liberación de acuerdos provisionales (D-77).

### D-84 · Estado `HELD` para acuerdos provisionales
- **Fecha:** 2026-11
- **Decisión:** un `ACCEPT` aceptado lleva la sesión a un estado nuevo, `HELD`, no terminal, entre `NEGOTIATING` y `CLOSING`, con la oferta vigente como oferta acordada (D-42). Desde `HELD`, la confirmación del coordinador lleva a `CLOSING` con `outcome = AGREEMENT` y `agreedOffer`; la liberación lleva a `CLOSING` con `outcome = RELEASED`, un resultado nuevo de `SESSION_CLOSE`. `NO_AGREEMENT`, `WITHDRAWN` y `ABORTED` siguen yendo directos a `CLOSING`. En `HELD` no hay turno ni Task en curso: una caída no exige ninguna acción al retomar y la sesión no necesita arrendamiento mientras espera. Una sesión puede seguir en `HELD` durante varias rondas (D-79). Precisa D-42, D-49 y D-77; obliga a revisar `maquina-estados.md` y CU-02.
- **Motivo:** mantiene el significado de `CLOSING` (resultado decidido, falta comunicarlo) y de `CLOSED` (terminal), y decide el resultado en una única transición atómica (D-63).
- **Descartado:** cerrar la sesión con un resultado `PROVISIONAL` y resolver la confirmación fuera de ella, porque contradice que `CLOSED` es definitivo.

### D-85 · Mensaje `AGREEMENT_HELD`
- **Fecha:** 2026-11
- **Decisión:** al entrar en `HELD`, el orquestador envía a las dos partes un mensaje de control nuevo, `AGREEMENT_HELD`, con la oferta acordada y el instante de caducidad de la reserva (D-86) en el cuerpo, y en el sobre el `turn` del `ACCEPT`, `sessionId` y `sender = ORCHESTRATOR`. Se envía como `SESSION_CLOSE` (D-64): `returnImmediately = true` sin sondeo, un intento por parte, envíos independientes, respuesta registrada e ignorada, y un fallo no altera el estado de la sesión. El registro de envíos de cierre (D-70) pasa a ser un registro de envíos de control sin acto, con el tipo de mensaje como campo. Amplía D-32; precisa D-70.
- **Motivo:** el vendedor necesita saber que debe reservar, y el coordinador, que hubo acuerdo cuando el `ACCEPT` lo emitió el vendedor. Reutiliza el mecanismo de envío de CU-02 y deja en la traza cuándo supo cada parte que había acuerdo.
- **Descartado:** no avisar hasta el `SESSION_CLOSE` final; crear un registro aparte para `AGREEMENT_HELD`.
- **Precisada por D-95 y D-107.**

### D-86 · Plazo de reserva
- **Fecha:** 2026-11
- **Decisión:** `holdTimeoutSeconds` en la configuración de la sesión: 1800 s por defecto, mayor que 0. Al entrar en `HELD`, el orquestador calcula la caducidad con el reloj de la base de datos (D-69), la guarda en el registro de sesión y la envía en `AGREEMENT_HELD`. Si vence sin decisión, la sesión pasa a `CLOSING` con `RELEASED`. `RELEASED` lleva un motivo: decisión del comprador o plazo vencido. La caducidad se detecta con una búsqueda periódica en la base de datos, como los arrendamientos caducados (D-04, D-63); la instancia que procesa la caducidad toma el arrendamiento para esa transición. El plazo no está garantizado para partidas que se mantienen entre rondas (D-79): si caduca durante una ronda, la partida queda liberada por plazo y entra en la siguiente corrección (D-81). Amplía D-40.
- **Motivo:** el plazo lo impone el árbitro neutral, es determinista y queda en la traza. Un valor fijo amplio cubre la mayoría de los casos sin añadir mecanismos; la caducidad ya está tratada, así que en el peor caso solo se renegocia una partida.
- **Descartado:** renovar el plazo al empezar cada ronda, por complejidad (se puede añadir después con un segundo `AGREEMENT_HELD`); que cada vendedor declare su plazo en la oferta, porque lo convertiría en contenido negociable; 300 s, porque no cubre una ronda.
- **Precisada por D-107, D-111, D-119, D-121 y D-122.**

Nombres fijados en D-92.

## Interfaz entre el coordinador y el orquestador

Decisiones tomadas al diseñar cómo pide el coordinador del comprador (D-80) que se abran rondas (D-83) y se resuelvan acuerdos provisionales (D-84).

### D-87 · El orquestador es servidor A2A del coordinador
- **Fecha:** 2026-11
- **Decisión:** el orquestador publica su propia AgentCard y declara `urn:tfm:negociacion:v1` con `required = true` (D-18). El coordinador es cliente A2A del orquestador y le envía mensajes de una familia nueva, peticiones del comprador, con sobre en `metadata` y cuerpo en una Part `data` (D-19). En sentido orquestador → coordinador no hay canal nuevo: el agente comprador ya recibe `AGREEMENT_HELD` y `SESSION_CLOSE` de cada sesión. El agente comprador es a la vez servidor A2A del orquestador y cliente suyo. Amplía D-21 con una tercera familia. No afecta a D-05, que trata de cómo obtiene el orquestador los actos de un turno.
- **Motivo:** Unicaja pide trazabilidad con A2A; si las peticiones del comprador viajaran por otro canal, la parte de la traza que explica por qué se abrió una ronda o se confirmó un acuerdo quedaría fuera del protocolo.
- **Descartado:** una API HTTP propia del orquestador, porque su registro sería un añadido fuera del protocolo y habría dos formas de hablar con el orquestador.

### D-88 · Peticiones `OPEN_ROUND` y `RESOLVE_HOLDS`
- **Fecha:** 2026-11
- **Decisión:** la familia de peticiones del comprador tiene dos mensajes:
  - `OPEN_ROUND`: lleva la configuración de cada sesión de la ronda, una por partida, según `configuracion-sesion.md`, y el `requestId` a partir de la segunda ronda. El orquestador genera el `requestId` en la primera ronda (D-83), numera la ronda, crea las sesiones (D-67) y las arranca. Responde con `requestId`, número de ronda y el `sessionId` de cada partida.
  - `RESOLVE_HOLDS`: lleva dos listas de `sessionId`, las que se confirman y las que se liberan. El orquestador aplica toda la decisión en una sola transacción: cada sesión sale de `HELD` hacia `CLOSING` con `AGREEMENT` o con `RELEASED` por decisión del comprador (D-84, D-86).

  El orquestador responde a cada petición con una Task que completa enseguida, con el resultado en un Artifact (como D-20). Renegociar (D-79) es un `RESOLVE_HOLDS` que libera lo que no se mantiene seguido de un `OPEN_ROUND`. El coordinador proporciona la configuración de cada sesión, incluidos los identificadores de las partes (D-30). El contenido exacto de `OPEN_ROUND` depende de cerrar `configuracion-sesion.md`.
- **Motivo:** dos operaciones con un solo efecto cada una son fáciles de validar y de leer en la traza. La resolución en una transacción garantiza que el paquete se confirma entero o no se confirma (D-77), lo que es posible porque todas las sesiones viven en la misma base de datos (D-69).
- **Descartado:** que `OPEN_ROUND` lleve las partidas que se mantienen y libere las demás, porque esconde una liberación dentro de una apertura.
- **Precisada por D-93, D-94, D-96, D-97, D-98 y D-110.**

### D-89 · Peticiones del comprador no válidas
- **Fecha:** 2026-11
- **Decisión:** las peticiones del comprador no se autocorrigen: se rechazan enteras. La Task termina en `TASK_STATE_REJECTED` y su mensaje de estado lleva una lista de `{code, field}` con códigos del catálogo (D-50). Casos:
  - `OPEN_ROUND` con alguna configuración que incumple sus restricciones (`maquina-estados.md`, sección 5): se rechaza la ronda entera y no se crea ninguna sesión.
  - `OPEN_ROUND` con un `requestId` desconocido o de otro comprador: rechazo.
  - `OPEN_ROUND` con un vendedor cuya AgentCard no declara la extensión: no es rechazo; esa sesión queda en `NOT_STARTED` (D-25), el resto arranca y la respuesta lo indica.
  - `RESOLVE_HOLDS` con alguna sesión que no está en `HELD` (ya resuelta, caducada o sin acuerdo): se rechaza entera, indicando qué sesiones y en qué estado.
  - `RESOLVE_HOLDS` con una sesión en las dos listas o con las dos listas vacías: rechazo.
  - Cualquier petición cuyo `sender` no es el comprador de la petición: rechazo.

  Cada petición, aceptada o rechazada, se añade a un registro nuevo de solo añadir con su tipo, `requestId`, ronda, resultado y códigos de rechazo, en la misma transacción que sus efectos (D-63, D-69). Amplía D-50 con códigos nuevos, cuyos nombres se fijan en `protocolo.md` (propuesta: `INVALID_CONFIG`, `UNKNOWN_REQUEST`, `NOT_HELD`, `NOT_AUTHORIZED`).
- **Motivo:** la autocorrección es para los actos que genera un SLM en la negociación (D-02); el coordinador construye sus peticiones con código, como el orquestador las suyas (D-71). Rechazar entero mantiene la atomicidad de D-77: si una reserva caduca mientras llega la confirmación, el coordinador recibe el motivo y recalcula con el estado real.
- **Descartado:** autocorregir las peticiones del comprador; aplicar las partes válidas de una petición.
- **Ampliada por D-92, D-100 y D-103. Precisada por D-93, D-94, D-98, D-101, D-102, D-111, D-112, D-113, D-118 y D-128.**

## Configuración de la sesión

Decisiones tomadas al cerrar `configuracion-sesion.md`, que pasa a ser el cuerpo de cada sesión en `OPEN_ROUND` (D-88).

### D-90 · Estructura y nombres de la configuración
- **Fecha:** 2026-11
- **Decisión:** la configuración de una sesión tiene estos campos:
  - `fixedTerms`: objeto `{productId, unit, currency}`, obligatorio, igual al que viaja en `TURN_REQUEST` (D-36, D-46).
  - `parties`: lista obligatoria de exactamente dos `{partyId, role, agentCardUrl}`, con `partyId` distintos y un `BUYER` y un `SELLER` (D-30, D-41).
  - `openingPartyId`: obligatorio, uno de los `partyId` de `parties` (D-41).
  - `validationMode`: enumerado obligatorio `STRICT` / `TOLERANT` (D-11).
  - `maxRetries`, `turnTimeoutSeconds`, `pollIntervalSeconds`, `maxTurns` y `holdTimeoutSeconds`: opcionales, con las restricciones de D-51, D-52, D-56, D-59 y D-86; si faltan, se aplica su valor por defecto (D-91).

  En todas las sesiones de un `OPEN_ROUND`, el `partyId` del `BUYER` es el mismo y coincide con el `sender` de la petición; las rondas siguientes de la misma petición mantienen ese comprador (D-89). `sessionId`, `requestId`, número de ronda y duración del arrendamiento no forman parte de la configuración. Amplía D-40; precisa D-11, D-30, D-36 y D-41.
- **Motivo:** `fixedTerms` se copia sin transformar en `TURN_REQUEST`. «Party» es neutro y resuelve en los nombres de campo el vocabulario de D-75. `agentCardUrl` indica al orquestador dónde comprobar la AgentCard (D-25) y llamar a cada agente, incluido el negociador del comprador.
- **Descartado:** un registro de partes en el orquestador con alta previa de cada vendedor, porque añade una pieza y un proceso de alta; se puede añadir más adelante.
- **Precisada por D-99, D-102 y D-129.**

### D-91 · Valores por defecto globales y valores efectivos guardados
- **Fecha:** 2026-11
- **Decisión:** los valores por defecto son globales y fijos en el código: `maxRetries = 2`, `turnTimeoutSeconds = 60`, `pollIntervalSeconds = 1`, `maxTurns = 10` y `holdTimeoutSeconds = 1800`. El orquestador guarda en el registro de sesión los valores efectivos, ya resueltos con los por defecto, no la configuración tal como llegó. Las restricciones entre parámetros se comprueban sobre los valores efectivos; si alguna falla, la ronda se rechaza (D-89). Precisa `maquina-estados.md`, sección 3: la «copia completa de la configuración» del registro de sesión es la de los valores efectivos.
- **Motivo:** cada sesión puede sobrescribir cualquier parámetro, así que una capa por despliegue apenas añade nada. Guardar los valores efectivos deja en la traza exactamente con qué valores se ejecutó cada sesión, aunque los valores por defecto cambien en otra versión del código.
- **Descartado:** valores por defecto configurables por despliegue.

## Consolidación de documentos

Concreciones hechas al incorporar D-75 a D-91 en `protocolo.md`, `maquina-estados.md` y los CU.

### D-92 · Nombres de campos, tipos de contenido y código `INVALID_REQUEST`
- **Fecha:** 2026-11
- **Decisión:** se fijan estos nombres, pendientes en D-82, D-86, D-88 y D-89:
  - `AGREEMENT_HELD`: `heldOffer` (Oferta) y `heldUntil` (instante ISO 8601 en UTC).
  - `SESSION_CLOSE`: `releaseReason`, enumerado `BUYER_DECISION` / `HOLD_EXPIRED`, y `lastOffers`, lista de `{partyId, offer}`.
  - `OPEN_ROUND`: `requestId` y `sessions`, lista de `{itemId, config}`, con `itemId` distinto dentro de la ronda. Resultado: `requestId`, `round` y `sessions`, lista de `{itemId, sessionId, started, failedPartyId}`.
  - `RESOLVE_HOLDS`: `requestId`, `confirm` y `release`. Resultado: `requestId`, `confirmed` y `released`.
  - Rechazo de una petición: `rejections`, lista de `{code, field}`.
  - Tipos de contenido: `application/vnd.tfm.negociacion.peticion+json` para peticiones del comprador y `application/vnd.tfm.negociacion.resultado+json` para su resultado.
  - Código nuevo `INVALID_REQUEST`: `RESOLVE_HOLDS` con las dos listas vacías o con una sesión en las dos. Amplía D-89.
- **Motivo:** cierra los nombres que las decisiones dejaban para `protocolo.md`, con las convenciones de D-29.
- **Ampliada por D-114. Precisada por D-104 y D-116.**

### D-93 · Sobre y alcance de las peticiones del comprador
- **Fecha:** 2026-11
- **Decisión:** el sobre de las peticiones del comprador lleva `type` y `sender`, no lleva `sessionId` ni `turn` y nunca se corrige. `RESOLVE_HOLDS` lleva `requestId`, y todas sus sesiones deben pertenecer a esa petición; si no, se rechaza con `NOT_HELD`. Precisa D-88 y D-89.
- **Motivo:** las peticiones no pertenecen a una sesión ni a un turno. El `requestId` permite comprobar que el comprador solo resuelve sesiones de su propia petición.
- **Precisada por D-104.**

### D-94 · El resultado de `OPEN_ROUND` espera a la comprobación de AgentCards
- **Fecha:** 2026-11
- **Decisión:** la Task de `OPEN_ROUND` se completa cuando todas las sesiones de la ronda han salido de `CREATED`. El resultado indica, por sesión, si empezó (`started`) y, si no, qué parte falló (`failedPartyId`). Precisa D-88 y D-89.
- **Motivo:** una sesión en `NOT_STARTED` no envía `SESSION_CLOSE` (D-25), así que el resultado de `OPEN_ROUND` es la única forma de que el coordinador lo sepa.
- **Descartado:** completar la Task al crear las sesiones, sin esperar a la comprobación.
- **Precisada por D-97 y D-99.**

### D-95 · Envíos de `AGREEMENT_HELD` pendientes al salir de `HELD`
- **Fecha:** 2026-11
- **Decisión:** si una sesión sale de `HELD` con envíos de `AGREEMENT_HELD` pendientes, esos envíos se marcan como descartados y no se hacen. El `SESSION_CLOSE` comunica el resultado final. Precisa D-85.
- **Motivo:** avisar de un acuerdo provisional que ya no existe solo confundiría a la parte.
- **Descartado:** completar los envíos pendientes antes del `SESSION_CLOSE`.

### D-96 · `RESOLVE_HOLDS` sin arrendamiento
- **Fecha:** 2026-11
- **Decisión:** `RESOLVE_HOLDS` no necesita el arrendamiento de las sesiones que resuelve. Escribe cada sesión de forma condicional por versión; si alguna versión cambió, relee y vuelve a evaluar, y si alguna sesión ya no está en `HELD` rechaza la petición con `NOT_HELD`. Libera el arrendamiento de las sesiones resueltas. Una instancia que estaba enviando `AGREEMENT_HELD` a una de ellas ve rechazada su escritura y descarta su trabajo, y ese envío queda sin entrada en el registro de control. La caducidad del plazo sí toma el arrendamiento. Precisa D-63 y D-88.
- **Motivo:** la decisión llega de fuera, no de un trabajo en curso de la sesión; esperar arrendamientos ajenos retrasaría la respuesta al coordinador. Liberar el arrendamiento permite empezar el cierre sin esperar a que caduque. Perder la entrada de un `AGREEMENT_HELD` se acepta porque ese envío no altera el estado (D-85).
- **Descartado:** que `RESOLVE_HOLDS` tome el arrendamiento de cada sesión antes de escribir.
- **Precisada por D-111 y D-115.**

## Apertura de rondas

Decisiones tomadas al diseñar CU-04.

### D-97 · Tasks de las peticiones del comprador en PostgreSQL
- **Fecha:** 2026-11
- **Decisión:** el orquestador, como servidor A2A del coordinador (D-87), guarda las Tasks de las peticiones del comprador en la misma base de datos PostgreSQL que el estado de las sesiones (D-69). La Task de un `OPEN_ROUND` se escribe así:
  - si se acepta, se crea en `TASK_STATE_WORKING` en la misma transacción que las sesiones, el registro de petición y la entrada del registro de peticiones;
  - si se rechaza, se crea directamente en `TASK_STATE_REJECTED` en la misma transacción que la entrada del registro de peticiones;
  - pasa a `TASK_STATE_COMPLETED`, con su Artifact de resultado, en la misma transacción que saca de `CREATED` la última sesión de la ronda (D-94).

  `GetTask` del coordinador se responde con la Task guardada. En `feature/setup` se comprueba si `a2a-sdk` ofrece un almacén de Tasks en base de datos que sirva para esto. Precisa D-04, D-88 y D-94.
- **Motivo:** con la Task en memoria, una caída entre crear las sesiones y completar la Task dejaría la petición sin respuesta, en contra de D-04. Escribirla en la misma transacción que las sesiones mantiene la atomicidad de D-63.
- **Descartado:** almacén de Tasks en memoria; almacén de Tasks en una pieza aparte de la base de datos.
- **Precisada por D-110 y D-126.**

### D-98 · `OPEN_ROUND` duplicado
- **Fecha:** 2026-11
- **Decisión:** el orquestador detecta un `OPEN_ROUND` duplicado por el par `sender` + `messageId`, comprobado antes de validar la petición. Ante un duplicado devuelve la Task de la petición original en su estado actual, sin crear rondas ni sesiones y sin añadir entradas a ningún registro. El par es único en el registro de peticiones: si dos copias llegan a la vez, la segunda escritura falla y se devuelve la Task de la primera. Si el sobre no permite leer `sender`, no se comprueba el duplicado y la petición se rechaza. Precisa D-88 y D-89.
- **Motivo:** si el coordinador cae justo después de enviar y reenvía la petición, sin esta regla se abriría una segunda ronda con sesiones duplicadas, que podrían acabar en compras dobles. A2A prevé que el servidor detecte duplicados por `messageId`, como se espera de los agentes (D-66).
- **Descartado:** no detectar duplicados; detectarlos por el contenido de la petición.
- **Ampliada por D-109. Precisada por D-128.**

### D-99 · Comprobación de AgentCards
- **Fecha:** 2026-11
- **Decisión:** en `CREATED`, el orquestador obtiene las AgentCards de las dos partes de la sesión en paralelo, con un intento por parte y el `turnTimeoutSeconds` efectivo de la sesión como tiempo máximo. Una parte falla si su AgentCard no se puede obtener (error de transporte, tiempo superado o respuesta no interpretable como AgentCard) o si no declara `urn:tfm:negociacion:v1` con `required = true` (D-25). Si fallan las dos, `failedPartyId` es la primera según el orden de `parties`. Cada sesión se comprueba por separado, aunque una parte aparezca en varias sesiones de la ronda. Precisa D-25, D-90 y D-94.
- **Motivo:** reutiliza un parámetro que ya existe y es determinista. Convertir `failedPartyId` en una lista cambiaría D-92.
- **Descartado:** reintentar la obtención; un tiempo máximo propio; guardar en caché las AgentCards entre sesiones.
- **Precisada por D-129.**

### D-100 · Ronda nueva con trabajo pendiente: `ROUND_CONFLICT`
- **Fecha:** 2026-11
- **Decisión:** un `OPEN_ROUND` con `requestId` se rechaza con el código nuevo `ROUND_CONFLICT` en dos casos:
  - alguna sesión de la petición está en `CREATED` o `NEGOTIATING`: campo `body.requestId`;
  - alguna entrada de `sessions` tiene el mismo `itemId` que una sesión de la petición en `HELD`: campo `body.sessions.<i>.itemId`.

  Amplía D-50 y D-89.
- **Motivo:** la corrección de D-81 se calcula sobre una ronda terminada, y reabrir una partida en `HELD` permitiría dos acuerdos para la misma partida. Para renegociar una partida mantenida, el coordinador la libera antes con `RESOLVE_HOLDS` (D-88).
- **Descartado:** permitirlo y dejar la responsabilidad al coordinador.
- **Precisada por D-105.**

### D-101 · Rechazos completos y competencia entre rondas
- **Fecha:** 2026-11
- **Decisión:** `rejections` recoge en una sola pasada todos los fallos de la petición, ordenados por ruta. Las comprobaciones que dependen de un campo con fallo estructural (`MISSING_FIELD`, `WRONG_TYPE`, `UNKNOWN_VALUE`) no se hacen sobre ese campo. Si dos `OPEN_ROUND` de la misma petición compiten, la escritura condicional por versión del registro de petición decide cuál entra (D-63). El que pierde relee y vuelve a evaluar la petición, incluidos el número de ronda y `ROUND_CONFLICT`. Precisa D-89.
- **Motivo:** el coordinador corrige todos los fallos de una vez, como el agente con `retryReason` (D-48). La versión ya resuelve la concurrencia en el resto del estado.
- **Descartado:** parar en el primer fallo.
- **Precisada por D-117.**

### D-102 · `sender` distinto del comprador en `OPEN_ROUND`
- **Fecha:** 2026-11
- **Decisión:** en `OPEN_ROUND`, cada código cubre un caso:
  - `INVALID_CONFIG`: el `partyId` del `BUYER` no es el mismo en todas las sesiones de la ronda.
  - `NOT_AUTHORIZED`, en `envelope.sender`: el `partyId` del `BUYER` es el mismo en todas las sesiones, pero distinto del `sender`. Vale para cualquier ronda.
  - `UNKNOWN_REQUEST`, en `body.requestId`: el `requestId` no existe o su comprador no es el `sender`. No se distingue entre los dos casos, para no revelar si la petición existe.

  Precisa D-89 y D-90; obliga a revisar «Restricciones en `OPEN_ROUND`» de `configuracion-sesion.md` y la tabla «Peticiones no válidas» de `protocolo.md`.
- **Motivo:** tal como estaban los documentos, `NOT_AUTHORIZED` no tenía ningún caso propio en `OPEN_ROUND` y los otros dos códigos se solapaban con él.
- **Descartado:** tratar la coincidencia del `BUYER` con el `sender` como `INVALID_CONFIG`.
- **Precisada por D-113 y D-128.**

### D-103 · Message sin forma de petición: `INVALID_MESSAGE`
- **Fecha:** 2026-11
- **Decisión:** un Message dirigido al orquestador que no tiene forma de petición se rechaza con el código nuevo `INVALID_MESSAGE` en el campo `message`, con la Task en `TASK_STATE_REJECTED` y una entrada en el registro de peticiones. Son casos de `INVALID_MESSAGE`:
  - falta la cabecera `A2A-Extensions` con la URI de la extensión;
  - falta la URI en `extensions`;
  - falta el sobre en `metadata["urn:tfm:negociacion:v1"]`;
  - no hay exactamente una Part, o esa Part no es `data` con el `mediaType` de petición.

  No se valida el sobre ni el cuerpo. La entrada del registro lleva el `type` y el `sender` solo si se pudieron leer. El catálogo de D-50 admite `message` como zona de campo, junto a `envelope`, `body` y `task`. Amplía D-50 y D-89.
- **Motivo:** rechazar con Task deja toda petición recibida en el registro y en la traza, como pide D-87.
- **Descartado:** responder con un error A2A, sin Task ni entrada en el registro.

### D-104 · Sobre del resultado de una petición
- **Fecha:** 2026-11
- **Decisión:** el Artifact de resultado y el mensaje de estado de un rechazo llevan sobre en `metadata["urn:tfm:negociacion:v1"]`, con estos campos:
  - `type` igual al de la petición;
  - `sender = ORCHESTRATOR`;
  - sin `sessionId` ni `turn`.

  Llevan también la URI en `extensions`. Precisa D-19, D-92 y D-93.
- **Motivo:** el `mediaType` de resultado ya identifica la respuesta, así que no hace falta ampliar el enumerado de `type`.
- **Descartado:** tipos propios de resultado (`OPEN_ROUND_RESULT`, `RESOLVE_HOLDS_RESULT`).
- **Precisada por D-106.**

### D-105 · Partida ya confirmada en `ROUND_CONFLICT`
- **Fecha:** 2026-11
- **Decisión:** un `OPEN_ROUND` se rechaza también con `ROUND_CONFLICT` en `body.sessions.<i>.itemId` si el `itemId` coincide con el de una sesión de la petición en `CLOSING` o `CLOSED` con `outcome = AGREEMENT`. Precisa D-100.
- **Motivo:** reabrir una partida confirmada daría una compra doble, igual que reabrir una en `HELD`.

### D-106 · Rechazo sin sobre cuando no se puede leer `type`
- **Fecha:** 2026-11
- **Decisión:** si una petición se rechaza con `INVALID_MESSAGE` (D-103) y no se pudo leer un `type` de petición válido (`OPEN_ROUND` o `RESOLVE_HOLDS`), el mensaje de estado del rechazo no lleva sobre. Lleva solo la Part `data` de resultado con `rejections` y la URI en `extensions`. En los demás casos se aplica D-104. Precisa D-104.
- **Motivo:** no existe un valor de `type` correcto que poner sin inventarlo, y el `mediaType` de resultado ya identifica la respuesta.
- **Descartado:** usar siempre `type = OPEN_ROUND`, porque sería falso para un `RESOLVE_HOLDS` mal formado.

## Envío de `AGREEMENT_HELD`

Decisiones tomadas al diseñar CU-05.

### D-107 · Plazo vencido con envíos de `AGREEMENT_HELD` pendientes
- **Fecha:** 2026-11
- **Decisión:** antes de enviar `AGREEMENT_HELD`, el orquestador comprueba con el reloj de la base de datos, en la misma operación en que renueva el arrendamiento, si `heldUntil` ha vencido. Si ha vencido, no envía `AGREEMENT_HELD` a ninguna parte y continúa directamente con la caducidad del plazo (CU-07), sin soltar el arrendamiento: la sesión pasa a `CLOSING` con `RELEASED` y `releaseReason = HOLD_EXPIRED`, y los envíos pendientes se marcan como descartados. Cuando una sesión en `HELD` tiene a la vez envíos pendientes y `heldUntil` vencido, se aplica la caducidad. Precisa D-69, D-85 y D-86; obliga a revisar la tabla «Qué hace la instancia que toma una sesión» de `maquina-estados.md`, sección 3.
- **Motivo:** avisar de una reserva que ya ha vencido es lo que evita el criterio de descartar los envíos pendientes al salir de `HELD`. El `SESSION_CLOSE` con `HOLD_EXPIRED` ya comunica el resultado. El caso puede darse tras una caída, porque la recuperación tarda hasta la duración del arrendamiento y `holdTimeoutSeconds` puede ser menor.
- **Descartado:** enviar `AGREEMENT_HELD` igualmente y dejar que la caducidad cierre después, porque la parte recibiría dos mensajes contradictorios seguidos.

### D-108 · Liberar el arrendamiento al terminar los envíos de `AGREEMENT_HELD`
- **Fecha:** 2026-11
- **Decisión:** la transacción que marca como enviado o fallido el último envío de `AGREEMENT_HELD` pendiente libera también el arrendamiento de la sesión, que sigue en `HELD`. Se libera aunque los dos envíos hayan fallado. Precisa D-63 y D-65; obliga a revisar la fila «Envío de `AGREEMENT_HELD`» de «Escrituras por transición» en `maquina-estados.md`, sección 3.
- **Motivo:** en `HELD` sin envíos pendientes no queda trabajo en curso. Sin liberar el arrendamiento, la búsqueda de caducidad tendría que esperar a que caduque, hasta 61 s con los valores por defecto, para liberar la sesión por plazo. `RESOLVE_HOLDS` ya libera el arrendamiento de las sesiones que resuelve por el mismo motivo.
- **Descartado:** dejar que el arrendamiento caduque solo.

## Resolución de acuerdos provisionales

Decisiones tomadas al diseñar CU-06.

### D-109 · `RESOLVE_HOLDS` duplicado
- **Fecha:** 2026-11
- **Decisión:** D-98 se aplica también a `RESOLVE_HOLDS`. El orquestador busca en el registro de peticiones una entrada con el mismo `sender` y `messageId` antes de validar la petición. Si existe, devuelve la Task de esa petición en su estado actual y no escribe nada. Si dos copias llegan a la vez, la segunda escritura falla por la unicidad del par y se devuelve la Task de la primera. Si el sobre no permite leer `sender`, no se comprueba el duplicado y la petición se rechaza. Amplía D-98; cierra la pregunta abierta de `maquina-estados.md`, sección 6, y obliga a revisar «Peticiones duplicadas» de `protocolo.md`.
- **Motivo:** el par `sender` + `messageId` ya es único en el registro de peticiones, así que un reenvío fallaría al insertarse. Si se volviera a evaluar, se rechazaría con `NOT_HELD` un paquete que sí se resolvió, y el coordinador recalcularía a partir de un fracaso que no ocurrió.
- **Descartado:** detectar el duplicado por el contenido de la petición, por el mismo motivo que en D-98.

### D-110 · Task de `RESOLVE_HOLDS` creada en estado final
- **Fecha:** 2026-11
- **Decisión:** la Task de un `RESOLVE_HOLDS` se crea directamente en `TASK_STATE_COMPLETED`, con su Artifact de resultado, en la misma transacción que las sesiones resueltas y la entrada del registro de peticiones. Si la petición se rechaza, se crea en `TASK_STATE_REJECTED` en la misma transacción que la entrada del registro de peticiones. No pasa por `TASK_STATE_WORKING`. Precisa D-88 y D-97; obliga a revisar «Tasks de las peticiones del comprador» de `maquina-estados.md`, sección 3.
- **Motivo:** a diferencia de `OPEN_ROUND` (D-94), no queda trabajo asíncrono después de la transacción, así que un estado intermedio nunca sería observable.
- **Descartado:** crearla en `TASK_STATE_WORKING` y completarla después, como `OPEN_ROUND`.

### D-111 · Plazo vencido sin procesar en `RESOLVE_HOLDS`
- **Fecha:** 2026-11
- **Decisión:** al evaluar un `RESOLVE_HOLDS`, cada sesión en `HELD` se compara con el reloj de la base de datos (D-69) en la misma transacción. Si su `heldUntil` ha vencido, cuenta como que no está en `HELD` y la petición se rechaza entera con `NOT_HELD` en la ruta de ese `sessionId`, aunque la búsqueda de caducidad todavía no haya procesado la sesión. El rechazo no aplica la caducidad: la sesión sigue en `HELD` hasta que la procese CU-07. Precisa D-86, D-89 y D-96.
- **Motivo:** el vendedor recibió `heldUntil` en `AGREEMENT_HELD` y puede haber liberado la reserva al vencer. Sin esta regla, el resultado dependería de cuándo pase la búsqueda periódica. Sigue el mismo criterio que D-107. La comparación usa la fila que `RESOLVE_HOLDS` ya lee, así que no añade consultas.
- **Descartado:** confirmar o liberar la sesión mientras la caducidad no se haya procesado; aplicar la caducidad dentro de la transacción del rechazo, porque un rechazo no tiene efectos en las sesiones (D-89).

### D-112 · `NOT_HELD` sin estado de la sesión
- **Fecha:** 2026-11
- **Decisión:** el rechazo de `RESOLVE_HOLDS` por `NOT_HELD` indica qué sesiones fallan solo con la ruta de su `sessionId` (`body.confirm.<i>` o `body.release.<i>`), sin su estado. Se mantiene el formato `{code, field}` de `rejections` (D-92). Precisa D-89, donde decía «indicando qué sesiones y en qué estado».
- **Motivo:** el coordinador ya conoce el `heldUntil` de cada sesión por `AGREEMENT_HELD` y sabe qué ha resuelto antes. El estado final le llega con `SESSION_CLOSE`. Devolver el estado obligaría a crear un valor que la máquina no tiene para el plazo vencido sin procesar (D-111), y a ocultarlo en las sesiones de otra petición para no revelar información ajena (como D-102).
- **Descartado:** añadir a cada elemento de `rejections` un campo opcional con el estado de la sesión.

### D-113 · `NOT_AUTHORIZED` sin caso propio en `RESOLVE_HOLDS`
- **Fecha:** 2026-11
- **Decisión:** en `RESOLVE_HOLDS` no se usa `NOT_AUTHORIZED`. Un `sender` que no es el comprador del `requestId` se rechaza con `UNKNOWN_REQUEST` en `body.requestId`, sin distinguirlo de un `requestId` inexistente. Precisa D-89 y D-102; cierra la nota de `protocolo.md` que dejaba este caso para el CU.
- **Motivo:** el comprador solo se conoce a través del `requestId`, y no distinguir los dos casos evita revelar si la petición existe, como en D-102.
- **Descartado:** `NOT_AUTHORIZED` en `envelope.sender` cuando el `requestId` existe pero es de otro comprador.

### D-114 · `sessionId` repetido en una misma lista
- **Fecha:** 2026-11
- **Decisión:** un `RESOLVE_HOLDS` con el mismo `sessionId` dos o más veces en `confirm`, o dos o más veces en `release`, se rechaza con `INVALID_REQUEST` en la ruta de cada aparición después de la primera. Amplía D-92.
- **Motivo:** las peticiones del comprador no se autocorrigen (D-89), así que no se quitan los duplicados sin avisar.
- **Descartado:** quitar los duplicados en silencio.
- **Precisada por D-116.**

### D-115 · Arranque del cierre tras `RESOLVE_HOLDS`
- **Fecha:** 2026-11
- **Decisión:** tras confirmar la transacción de un `RESOLVE_HOLDS` aceptado, la misma instancia intenta tomar el arrendamiento de cada sesión resuelta, que queda libre por D-96, y lanza el envío de `SESSION_CLOSE` (CU-02). Si no lo consigue, porque otra instancia se adelanta o la propia cae, la sesión la recoge la búsqueda de sesiones con trabajo pendiente y sin arrendamiento. Precisa D-96.
- **Motivo:** las partes reciben `SESSION_CLOSE` enseguida, sin depender del periodo de la búsqueda.
- **Descartado:** dejar el cierre solo a la búsqueda periódica.
- **Precisada por D-119.**

### D-116 · Rutas de `INVALID_REQUEST`
- **Fecha:** 2026-11
- **Decisión:** en `RESOLVE_HOLDS`, `INVALID_REQUEST` se indica así:
  - las dos listas vacías: un solo fallo en `body`;
  - un `sessionId` en las dos listas: un fallo en cada una de sus apariciones, en `body.confirm.<i>` y en `body.release.<j>`.

  Si un `sessionId` está en las dos listas y además repetido en alguna, se marcan todas sus apariciones, con un solo fallo por ruta, sin añadir los de D-114. Como en `message` y `task`, la ruta puede ser solo la zona. Precisa D-92 y D-114; obliga a revisar la tabla «Peticiones no válidas» de `protocolo.md`.
- **Motivo:** con las dos listas vacías el fallo es la combinación, no una lista concreta, así que lleva una sola entrada. Con una sesión en las dos listas, ninguna aparición es la correcta: marcar solo una daría a entender que la otra está bien, y el coordinador podría confirmar por error una compra que quería liberar.
- **Descartado:** dos fallos, en `body.confirm` y `body.release`, para las listas vacías; marcar solo la aparición posterior por ruta, siguiendo D-114.

### D-117 · Sin comprobación de sesiones si el `requestId` falla
- **Fecha:** 2026-11
- **Decisión:** en `RESOLVE_HOLDS`, si `requestId` tiene cualquier fallo, sea estructural (`MISSING_FIELD`, `WRONG_TYPE`) o `UNKNOWN_REQUEST`, no se comprueba la pertenencia ni el estado de las sesiones, así que no se añade ningún `NOT_HELD`. Las comprobaciones de `INVALID_REQUEST` (D-114, D-116) sí se hacen, porque no dependen de la petición. Precisa D-101.
- **Motivo:** la pertenencia de una sesión depende de la petición. Con un `requestId` que no se reconoce, todas las sesiones darían `NOT_HELD` como consecuencia de un único error, y el coordinador tiene que arreglar primero el `requestId`. Extiende a `UNKNOWN_REQUEST` el criterio de D-101 para los fallos estructurales.
- **Descartado:** comprobar las sesiones igualmente para recoger en una sola pasada también los fallos derivados.

### D-118 · Ronda de `RESOLVE_HOLDS` en el registro de peticiones
- **Fecha:** 2026-11
- **Decisión:** la entrada de un `RESOLVE_HOLDS` en el registro de peticiones lleva como ronda la última ronda abierta de la petición en el momento de recibirla. Si el `requestId` falla o no se pudo leer, la entrada no lleva ronda, como tampoco lleva `requestId`. Precisa D-89; obliga a revisar «Registros de solo añadir» de `maquina-estados.md`, sección 3, y «Registro» de `protocolo.md`.
- **Motivo:** un `RESOLVE_HOLDS` puede resolver sesiones de varias rondas (partidas mantenidas, D-79), así que la ronda de las sesiones no da un valor único. La última ronda abierta indica cuándo decidió el coordinador, y con el registro de petición la traza muestra la secuencia de la compraventa (D-83, D-87).
- **Descartado:** no guardar ronda y deducir el momento por el instante de la entrada.

## Caducidad del plazo de reserva

Decisiones tomadas al diseñar CU-07.

### D-119 · Una sola búsqueda de sesiones con trabajo pendiente
- **Fecha:** 2026-11
- **Decisión:** la caducidad del plazo de reserva (D-86) y la recuperación de sesiones (D-63, D-115) usan una sola búsqueda periódica en la base de datos. Encuentra las sesiones con trabajo pendiente cuyo arrendamiento está libre o caducado. Hay trabajo pendiente en estos casos:
  - `CREATED`, `NEGOTIATING` y `CLOSING`;
  - `HELD` con envíos de `AGREEMENT_HELD` pendientes;
  - `HELD` con `heldUntil` vencido según el reloj de la base de datos (D-69).

  Lo que hace la instancia con cada sesión encontrada es lo que indica la tabla «Qué hace la instancia que toma una sesión» de `maquina-estados.md`, sección 3. Precisa D-63, D-86 y D-115; obliga a revisar «Caducidad del plazo» en «Concurrencia y recuperación» de `maquina-estados.md`, sección 3.
- **Motivo:** la tabla de recuperación ya incluye la sesión en `HELD` con el plazo vencido, así que es la misma consulta con un caso más. Dos búsquedas tendrían dos periodos y dos procesos compitiendo por las mismas filas.
- **Descartado:** una búsqueda propia para la caducidad del plazo.
- **Precisada por D-120.**

### D-120 · Periodo de la búsqueda
- **Fecha:** 2026-11
- **Decisión:** la búsqueda de D-119 se ejecuta cada 5 s. Es una constante fija en el código, no un parámetro de la sesión ni del despliegue. El retraso máximo en retomar una sesión tras una caída pasa a ser la duración del arrendamiento más este periodo. Precisa D-119; obliga a revisar «Duración del arrendamiento» de `maquina-estados.md`, sección 5.
- **Motivo:** una búsqueda cubre todas las sesiones, así que no puede depender de la configuración de una. No hace falta ajustarlo: por D-111, el resultado no depende de cuándo se procese la caducidad; el periodo solo retrasa el `SESSION_CLOSE` y la recuperación. Sigue el criterio de D-65 y D-91.
- **Descartado:** un parámetro de despliegue, porque solo compensaría para estudiar en los experimentos el efecto del periodo, que no es un objetivo del TFM.

### D-121 · Caducidad en una sola transacción que toma el arrendamiento
- **Fecha:** 2026-11
- **Decisión:** la caducidad del plazo se aplica con una sola escritura condicional por versión. La escritura comprueba con el reloj de la base de datos que:
  - la sesión sigue en `HELD`;
  - `heldUntil` ha vencido;
  - el arrendamiento está libre o caducado o, si se llega desde CU-05 2a (D-107), es de esta instancia;
  - la versión no ha cambiado desde la lectura.

  En la misma transacción escribe `CLOSING` con `outcome = RELEASED`, `releaseReason = HOLD_EXPIRED` y `lastOffers` (D-82); marca como descartados los envíos de `AGREEMENT_HELD` pendientes (D-95); deja pendientes los envíos de `SESSION_CLOSE` a las dos partes, y pone el arrendamiento a nombre de esta instancia con su caducidad renovada (D-65). Si alguna condición falla, no escribe nada y descarta su trabajo; la siguiente pasada de la búsqueda vuelve a evaluar la sesión si sigue cumpliendo las condiciones. Cada sesión se procesa en su propia transacción. Precisa D-63 y D-86.
- **Motivo:** la transición no tiene ninguna operación de E/S, así que tomar antes el arrendamiento solo añadiría una escritura y un hueco en el que puede entrar un `RESOLVE_HOLDS`. Sigue cumpliendo D-86, porque el arrendamiento se toma en la misma escritura que la transición.
- **Descartado:** tomar el arrendamiento en una escritura previa y hacer la transición en otra.

### D-122 · Arranque del cierre tras la caducidad
- **Fecha:** 2026-11
- **Decisión:** tras confirmar la transacción de D-121, la misma instancia continúa con el envío de `SESSION_CLOSE` (CU-02) sin soltar el arrendamiento. Si cae antes de terminar, otra instancia retoma la sesión en `CLOSING` cuando el arrendamiento caduca, mediante la búsqueda de D-119. Precisa D-86; es el equivalente de D-115 para la caducidad.
- **Motivo:** la instancia ya tiene el arrendamiento y la sesión, así que las partes reciben el cierre enseguida. Soltar el arrendamiento para acelerar la recuperación tras una caída abriría un hueco en el que otra instancia podría tomar la sesión mientras esta todavía envía. El resultado ya está guardado, así que el retraso de una recuperación no lo altera.
- **Descartado:** liberar el arrendamiento tras la transición, como en D-96; dejar el cierre solo a la búsqueda periódica.

## Reglas de autocorrección

### D-123 · `autocorreccion.md` como fuente única, con prefijo `R-xx`
- **Fecha:** 2026-11
- **Decisión:** las reglas de autocorrección viven solo en `autocorreccion.md`, con identificador `R-xx`. `AC-cc-nn` significa siempre criterio de aceptación de una tarjeta. `protocolo.md` y las tarjetas citan las reglas por su `R-xx`; los criterios conservan su ejemplo concreto y añaden `(R-xx)`. Toda `R-xx` está cubierta por algún `AC-cc-nn`. En el registro de coerciones, la «decisión aplicada» es el `R-xx` de la regla; `code` se mantiene como vocabulario común (D-50). Las decisiones D-xx no se modifican y `autocorreccion.md` las cita.
- **Motivo:** las reglas estaban repartidas entre `protocolo.md` y las tarjetas, y `AC-xx` tenía dos sentidos. Citar la regla en la coerción deja en la traza qué se aplicó y por qué.
- **Descartado:** un campo nuevo en el registro de coerciones, porque «decisión aplicada» ya existe; sustituir los ejemplos de los criterios por la referencia, porque el test dejaría de salir del criterio.

### D-124 · Python 3.14 confirmada
- **Fecha:** 2026-11
- **Decisión:** el proyecto usa Python 3.14. `a2a-sdk` 1.3.0, que implementa A2A 1.0 (`PROTOCOL_VERSION_CURRENT = '1.0'`), y LangGraph 1.2.20 resuelven con ella. Cierra la provisionalidad de D-13.
- **Motivo:** comprobado en `feature/setup` con `uv add` y, para LangGraph, con `uv lock` en un proyecto temporal.

### D-125 · PostgreSQL 18.6 y psycopg
- **Fecha:** 2026-11
- **Decisión:** PostgreSQL 18.6, en contenedor para desarrollo y tests, y `psycopg` como controlador. Precisa D-69.
- **Motivo:** en la prueba real, `psycopg` y `asyncpg` cumplen lo mismo y la diferencia es de 0,07 ms por transacción. `psycopg` da `rowcount` como entero, más legible en la escritura condicional de D-63.
- **Descartado:** `asyncpg`, porque devuelve el resultado como texto; PostgreSQL 17, por ser anterior.

### D-126 · Tabla y TaskStore propios para las Tasks
- **Fecha:** 2026-11
- **Decisión:** el orquestador guarda las Tasks de las peticiones del comprador en una tabla propia, dentro de su transacción, con una implementación propia de la interfaz `TaskStore` de `a2a-sdk`. Queda por comprobar cómo llama el manejador del SDK a `save` al implementar D-87. Precisa D-97.
- **Motivo:** D-97 exige la misma transacción que las sesiones, y `save` abre y confirma su propia sesión en los dos almacenes de `a2a-sdk` 1.3.0.
- **Descartado:** `DatabaseTaskStore` y `VersionedDatabaseTaskStore`, por ese motivo.
- **Precisada por D-127.**

## Servidor A2A del orquestador

Decisiones tomadas al implementar D-87 en `feature/abrir-ronda`.

### D-127 · `RequestHandler` propio para las peticiones del comprador
- **Fecha:** 2026-11
- **Decisión:** el orquestador implementa la interfaz `RequestHandler` de `a2a-sdk` y usa sus rutas JSON-RPC y de AgentCard. `on_message_send` valida y escribe la Task en su transacción; `on_get_task` lee la tabla; los demás métodos responden `UnsupportedOperationError`. No usa `TaskStore` ni `AgentExecutor`. Precisa D-126 y cierra su comprobación pendiente.
- **Motivo:** en `a2a-sdk` 1.3.0, `DefaultRequestHandler` llama a `save` desde otra tarea de asyncio y después de que el ejecutor emita el evento, sin pasarle ninguna transacción, y una Task completada por otra instancia no pasa por él. Así no se cumple D-97.
- **Descartado:** un `TaskStore` que reciba la conexión en `context.state`, porque depende de detalles internos del SDK y no resuelve la Task completada por otra instancia.

### D-128 · Autenticación bearer del coordinador
- **Fecha:** 2026-11
- **Decisión:** todo acceso al orquestador salvo su AgentCard exige `Authorization: Bearer <token>`. Cada token corresponde a un `partyId` y se configura en el despliegue. La AgentCard lo declara como esquema HTTP bearer. Sin credencial válida, el orquestador responde 401 con `WWW-Authenticate`, sin Task ni entrada en el registro de peticiones, como excepción a D-89 y D-103. Además:
  - Un `sender` distinto de la identidad autenticada se rechaza con `NOT_AUTHORIZED` en `envelope.sender` en `OPEN_ROUND`, y con `UNKNOWN_REQUEST` en `body.requestId` en `RESOLVE_HOLDS` (D-113). Hay un solo fallo por ruta.
  - El duplicado (D-98, D-109) solo se busca si `sender` es la identidad autenticada. La entrada del registro de peticiones guarda la identidad, y el par `sender` + `messageId` solo es único entre las entradas cuyo `sender` es su identidad.
  - Cada Task guarda su identidad. `GetTask` de otra identidad responde `TaskNotFoundError`, sin distinguirla de una Task inexistente.

  Precisa D-89, D-98 y D-102. Cierra la pregunta de `maquina-estados.md`, sección 6.
- **Motivo:** A2A 1.0 exige autenticar cada petición, y la identidad no viaja en el mensaje: comparar el `sender` solo comparaba un valor declarado. Sin la regla de unicidad, un comprador podría bloquear los `messageId` de otro enviándolos con su `sender`.
- **Descartado:** OAuth2 u OpenID Connect y TLS mutuo, por la infraestructura que añaden. Esta decisión no cubre TLS, caducidad de tokens ni rotación sin reinicio.

### D-129 · Orígenes permitidos para `agentCardUrl`
- **Fecha:** 2026-11
- **Decisión:** el origen (esquema, host y puerto) de cada `agentCardUrl` debe estar en una lista fijada en el despliegue. Si no lo está, la ronda se rechaza con `INVALID_CONFIG` en `body.sessions.<i>.config.parties.<j>.agentCardUrl` y no se hace ninguna petición de red. Una redirección no se sigue: cuenta como AgentCard que no se puede obtener (D-99). Precisa D-90 y D-99.
- **Motivo:** el orquestador hace un GET a una dirección que recibe del cliente. Sin límite, se le podría usar para sondear servicios internos.
- **Descartado:** dejar la sesión en `NOT_STARTED` para un origen no permitido, porque un error de configuración parecería un fallo del agente; bloquear redes privadas, porque es vulnerable a DNS rebinding y obliga a una excepción en desarrollo local. No es el registro de partes que descarta D-90: no da de alta partes, solo orígenes.
- **Precisada por D-131.**

## Cliente A2A del orquestador

Decisiones tomadas al implementar CU-01 y CU-03 en `feature/turnos`.

### D-130 · Cliente JSON-RPC propio hacia los agentes
- **Fecha:** 2026-11
- **Decisión:** el orquestador llama a los agentes con `httpx` y JSON-RPC propio, y lee las respuestas con los números sin pasar por coma flotante.
- **Motivo:** los tipos protobuf de `a2a-sdk` 1.3.0 no distinguen 10 de 10.0 ni conservan todos los decimales, y eso incumple R-11 y D-37.
- **Descartado:** el cliente de `a2a-sdk`, porque obligaría a cambiar R-11 y D-37.
- **Precisada por D-132.**

### D-131 · URL de servicio de los agentes
- **Fecha:** 2026-11
- **Decisión:** al comprobar la AgentCard, una parte también falla si no ofrece una interfaz JSON-RPC o si el origen de su URL no está en la lista de D-129. La sesión queda en `NOT_STARTED`. La URL válida se guarda en el registro de sesión y no se vuelve a pedir la tarjeta. Precisa D-99 y D-129.
- **Motivo:** esa es la dirección que se llama de verdad. Sin límite, un agente podría dirigir al orquestador a un servicio interno. Guardarla permite retomar la sesión desde otra instancia.
- **Descartado:** releer la tarjeta antes de cada envío; no comprobar el origen.

### D-132 · Enteros con parte decimal nula
- **Fecha:** 2026-11
- **Decisión:** en los campos enteros de un acto (`turn`, `quantity`, `deliveryDays`, `paymentDays`), un número JSON con parte decimal nula es un entero: 10.0 vale 10, en los dos modos y sin coerción. El orquestador lo guarda y lo reenvía como entero. Una cadena numérica sigue siendo `WRONG_TYPE` (R-02, R-11, R-12). Precisa D-130 y R-11.
- **Motivo:** `a2a-sdk` guarda los datos como números protobuf de coma flotante y envía 10 como 10.0. Si no, ningún agente hecho con el SDK pasaría el modo estricto.
- **Descartado:** volver al cliente del SDK, porque pierde el decimal exacto del precio (D-37); exigir a los agentes que no usen los tipos del SDK.

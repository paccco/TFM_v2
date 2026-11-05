# Política de proceso — TFM

**Este fichero es la única fuente de las reglas de proceso.** `CLAUDE.md`, las skills, los subagentes y `docs/latex/CLAUDE.md` lo citan por sección (`proceso.md §N`), no lo copian. Si encuentras una regla en otro sitio que contradice este fichero, manda este fichero: avisa al desarrollador de la contradicción.

Cambiar este fichero lo decide el desarrollador.

---

## 1. Fuente de verdad y decisiones

- El diseño (esquemas, máquinas de estado, validaciones, casos de uso) lo decide el desarrollador fuera de la sesión del agente. El agente implementa.
- **`docs/contexto/` es la fuente de verdad.** Si el código y `docs/contexto/` discrepan, o la especificación es ambigua, para y pregunta. No modifiques la especificación por tu cuenta.
- Las decisiones de `docs/contexto/decisiones.md` (D-xx) están cerradas: no las reabras ni propongas alternativas salvo que el desarrollador lo pida.
- `docs/latex/` es documentación para personas, no especificación: nunca se usa como fuente de reglas.
- Los cambios en `protocolo.md`, `maquina-estados.md`, `autocorreccion.md` y `decisiones.md` se muestran al desarrollador como diff y solo se guardan con su aprobación.

## 2. Código

El proyecto se reescribió en Python para que el desarrollador entienda todo el código. Por tanto:

- Código simple y explícito antes que ingenioso. Sin metaprogramación, sin abstracciones «por si acaso», sin dependencias que no se hayan acordado.
- Una rama, un objetivo.
- Docstrings y comentarios en español que citen la regla o decisión que implementan (`D-07`, `AC-03`, `CU-02`).
- Anotaciones de tipo en todas las funciones, métodos y estructuras de datos públicas (D-16).
- Al terminar cada tarea, resumen de 5-10 líneas: qué se ha hecho, por qué, qué parte de `docs/contexto/` implementa y qué se ha supuesto. Lo supuesto va en «Preguntas abiertas».

## 3. Ponytail

- Ponytail decide **cómo** implementar con el mínimo código, nunca **qué** se implementa.
- No es trabajo que se pueda saltar, aunque parezca redundante: lo que exige `docs/contexto/` (validaciones del esquema, reglas AC-xx, transiciones, reintentos, ABORTAR, registro de coerciones y sus tests), ni la actualización de `docs/latex/` de cada funcionalidad (§9).
- Si Ponytail y `docs/contexto/` chocan, manda `docs/contexto/`. Si crees que la especificación sobra, pregúntalo; no la recortes.
- El `revisor` y el `explorador` trabajan sin Ponytail (`PONYTAIL_SUBAGENT_MATCHER` en `.claude/settings.json`). `ponytail-review` juzga si sobra código; el `revisor`, si cumple `docs/contexto/`.

## 4. Secretos y datos

- Nadie lee ni pasa a ningún agente o modelo: `.env`, claves de proveedores de modelos, certificados, volcados del almacén de estado, documentación interna o datos de Unicaja.
- `.env` y cualquier fichero de secretos van en `.gitignore` desde el primer commit.
- A los modelos externos (§12) solo va material público o propio del repositorio.
- La información sensible y las decisiones de seguridad las resuelve el Orquestador, nunca un modelo externo.

## 5. Aprobación

- Nada que cree una rama se empieza sin un «aprobado» explícito del desarrollador. «Vale», «ok» o el silencio no cuentan.
- La propuesta se prepara con la skill `proponer-funcionalidad` (`feature/`, `feature/docs-`, `bugfix/`, `hotfix/`) o `cerrar-release` (`release/`).
- Solo se proponen casos de uso con estado «aprobado» en `docs/contexto/casos-de-uso/README.md`.
- **Propuesta completa** (`feature/`): rama, qué hará, CU/D/AC, ficheros, tests, capítulos de LaTeX, dependencias nuevas, dudas.
- **Propuesta corta** (`bugfix/`, `hotfix/`, `feature/docs-`): rama, qué hará, ficheros, tests.
- No existe el «aprobado con cambios»: ante cualquier corrección se rehace la propuesta entera y se espera otro «aprobado».
- Hasta el «aprobado» solo se lee y se delega en `explorador` y `gemini-lector`.
- Si durante la implementación cambia el alcance aprobado, se para y se presenta una propuesta nueva.

## 6. Ramas y permisos de Git

Solo el Orquestador ejecuta comandos de Git que modifican el repositorio. Los demás agentes solo leen.

### Gitflow

Las ramas se gestionan con la herramienta `git flow`, nunca a mano (`git switch -c`, `git checkout -b` o `git branch <nombre>` no se usan para crear ramas).

| Rama | Sale de | Vuelve a | Para qué |
|---|---|---|---|
| `main` | — | — | Solo versiones publicadas, cada una con su etiqueta |
| `develop` | `main` | — | Integración. El revisor compara contra ella |
| `feature/<cu-o-tema>` | `develop` | `develop` | Una funcionalidad |
| `feature/docs-<tema>` | `develop` | `develop` | Cambios solo de documentación o especificación |
| `bugfix/<tema>` | `develop` | `develop` | Corrección de algo aún no publicado |
| `release/vX.Y.Z` | `develop` | `main` y `develop` | Cierre de una versión (§10) |
| `hotfix/vX.Y.Z` | `main` | `main` y `develop` | Corrección urgente de una versión publicada |

### Confirmaciones

Cada uno de estos pasos lleva su propia confirmación del desarrollador, aparte del «aprobado» de §5:

- `git flow … finish` (fusiona; en `release/` y `hotfix/` también etiqueta).
- `git push` (de ramas y de etiquetas).
- `git tag`, `git merge`, `git rebase` y `git reset` fuera del flujo de `git flow`.

Nunca `git push --force`.

## 7. Commits y TDD

- Mensajes en español, citando la regla o caso implementado.
- **TDD estricto**: en cada capa, primero los tests y se comprueba que fallan por el motivo esperado (no por un error de importación o sintaxis); después el código mínimo que los hace pasar.
- Al menos un test por cada criterio de aceptación de la tarjeta del caso de uso. En `bugfix/` y `hotfix/`, un test que reproduce el fallo.

| Momento | Mensaje |
|---|---|
| Inicio de rama (commit vacío con la propuesta aprobada en el cuerpo) | `inicio: propuesta aprobada — CU-xx` |
| Tests de una capa, en rojo | `<capa>: tests en rojo — CU-xx` |
| Código de esa capa, en verde | `<capa>: implementación en verde — CU-xx` |
| Recortes aplicados de `ponytail-review` | `refactor: recortes de ponytail-review — CU-xx` |
| LaTeX, índice de casos de uso y, en `hotfix/`, CHANGELOG | `docs: LaTeX e índice — CU-xx` |
| Correcciones de hallazgos bloqueantes del revisor | `fix: hallazgos del revisor — CU-xx` |
| PDF en `hotfix/` (§9) | `hotfix: PDF de vX.Y.Z` |
| PDF en `release/` | `release: PDF de vX.Y.Z` |
| CHANGELOG y roadmap en `release/` | `release: CHANGELOG y roadmap de vX.Y.Z` |

Si no hay CU, se cita el tema de la rama.

## 8. Flujo por tarea

1. Si hace falta documentación externa, `gemini-lector` extrae reglas y dependencias.
2. Propuesta y «aprobado» (§5).
3. Rama con `git flow` y commit inicial (§6, §7).
4. Implementación con la skill `implementar-rama`, solo en las capas que toque la propuesta y en este orden:
   1. Esquemas de mensaje y validación estructural.
   2. Reglas de autocorrección (modo estricto y tolerante).
   3. Máquina de estados de la sesión.
   4. Orquestador: bucle pull, reintentos por turno, fallback ABORTAR, estado externalizado.
   5. Adaptador A2A.
   6. Agentes LangGraph de las empresas.
   7. Tests de extremo a extremo con agentes simulados.
5. Tests y lint completos.
6. `ponytail-review` sobre el diff (§3).
7. LaTeX e índice de casos de uso (§9).
8. `revisor`, si el cambio toca su cometido (§11).
9. Resumen (§2) y confirmación para el `finish` y después para el `push` (§6).

## 9. Documentación LaTeX y PDF

- `docs/latex/` contiene el manual de usuario (`manual/`) y la documentación técnica (`tecnica/`), un fichero por capítulo. Las reglas de redacción están en `docs/latex/CLAUDE.md`.
- La redacta el Orquestador; no se delega.
- Se actualiza en la misma rama que implementa la funcionalidad, antes de cerrarla. Los cambios solo de documentación van en `feature/docs-<tema>`.
- En cualquier rama que cambie el LaTeX, se compila con `latexmk` para comprobar que no hay errores; la salida va a `build/`, ignorada por Git.
- **PDF en `docs/pdfs/`**: solo se compilan, copian y suben en `release/`, y en `hotfix/` si el hotfix cambia el LaTeX. Ninguna otra rama toca `docs/pdfs/`, para evitar conflictos de binarios al fusionar.
- Si la compilación falla por un paquete que falta, se avisa al desarrollador; no se sustituye por otro.

## 10. Versiones y releases

- Etiquetas `vX.Y.Z`. La **minor** sube con cada hito del roadmap; la **patch**, con cada hotfix; `v1.0.0` es la versión que se entrega como TFM y solo se propone si el desarrollador lo pide.
- Hay release cuando se completa una funcionalidad marcada como importante en `docs/contexto/roadmap.md`. El Orquestador la propone con la skill `cerrar-release`; nunca la abre por su cuenta.
- Cada release y cada hotfix añade su entrada a `CHANGELOG.md`.

## 11. Agentes

### Orquestador (Claude Code, agente principal)

Reserva su contexto para las tareas de alto nivel. No delega:

- Implementación de la arquitectura y del diseño fijados en `docs/contexto/`.
- Lógica crítica: validación de mensajes, reglas de autocorrección, máquina de estados, reintentos y fallback ABORTAR.
- Depuración compleja.
- Escritura y edición de código.
- Redacción de `docs/latex/`.
- Comandos de Git que modifican el repositorio.
- Infraestructura local: entorno de Python, almacén de estado, arranque de agentes.

No toma decisiones de diseño nuevas: las plantea al desarrollador.

### explorador (subagente, Haiku)

- **Ejecución:** subagente de solo lectura (`.claude/agents/explorador.md`).
- **Cometido:** localizar ficheros, definiciones, llamadas y referencias cruzadas.
- **Salida:** solo rutas relativas y números de línea, sin volcados de código.

### gemini-lector (`llm`, prima la eficiencia)

- **Ejecución:** `files-to-prompt <rutas> | llm -m gemini-lector "<pregunta_concreta>"`
- **Cometido:** lecturas de volumen: especificación A2A, documentación de LangGraph y del SDK de A2A, changelogs, logs largos, varios casos de uso a la vez.
- **Salida:** respuesta concreta citando la fuente (fichero y sección, o ID de regla), sin reescribir los documentos.
- **Límites:** no escribe ficheros ni toma decisiones. Si detecta contradicciones, las lista y decide el Orquestador.

### gemini-analista (`llm`, prima la calidad)

- **Ejecución:** `files-to-prompt <contexto> docs/contexto/plantillas/caso-de-uso.md | llm -m gemini-analista "Redacta la tarjeta CU-xx ..."`
- **Cometido:** redactar o actualizar documentos estructurados: tarjetas de casos de uso (`docs/contexto/casos-de-uso/`) y entradas del catálogo de autocorrección.
- **Salida:** el documento completo, que el Orquestador revisa y guarda (§1 si toca documentos de diseño).
- **Límites:** no inventa actos, estados, reglas ni funcionalidades fuera de lo decidido. Lo que falte va a «Preguntas abiertas».

### revisor (subagente, Sonnet, contexto limpio)

- **Ejecución:** subagente de solo lectura (`.claude/agents/revisor.md`), lanzado sin el contexto de la tarea para que no dé por buenas las suposiciones con las que se escribió el código.
- **Cometido:** revisar antes de cerrar la rama todo cambio que toque:
  - esquema de mensajes y actos del protocolo;
  - máquina de estados de la sesión (transiciones, turnos, condiciones de fin);
  - reglas de autocorrección y modos estricto / tolerante (registro de coerciones);
  - reintentos por turno y fallback ABORTAR;
  - persistencia del estado externalizado;
  - comunicación A2A (autenticación, endpoints, tiempos de espera);
  - gestión de secretos y configuración de proveedores de modelos.
- **Salida:** hallazgos con fichero, línea, gravedad (bloqueante / mejora) y regla afectada. Si no hay ninguno, «Sin hallazgos».

## 12. Modelos externos

Se invocan siempre por alias, nunca por su ID.

| Alias | Modelo actual | Rol |
|---|---|---|
| `gemini-lector` | `gemini-3.7-flash` | Lecturas de volumen |
| `gemini-analista` | `gemini-3.8-flash` | Redacción de documentos estructurados |

- La configuración de alias y claves la hace el desarrollador, una vez por equipo (Debian y Arch). El agente nunca ejecuta `llm keys`.
- Cambiar de modelo lo decide el desarrollador: actualiza el alias y esta tabla.
- Si un alias falla porque el modelo ya no existe, el Orquestador avisa y no lo sustituye por otro.

## 13. Cuándo delegar

| Situación | Delega en |
|---|---|
| «¿Dónde está...?», «¿quién usa...?» | `explorador` |
| Leer más de ~3 ficheros largos, logs, documentación o varios casos de uso | `gemini-lector` |
| Redactar o actualizar una tarjeta de caso de uso o una entrada de catálogo | `gemini-analista` |
| Cambios del cometido del revisor (§11) | `revisor`, antes de cerrar la rama |
| Diseño, código, LaTeX, Git, infraestructura y decisiones | No se delega |

## 14. Cómo delegar y qué hacer con la respuesta

- Una pregunta concreta por encargo, con rutas exactas y el formato de salida esperado.
- Indica la fase o tarea (p. ej. `CU-03`, capa 2) para acotar.
- Respeta §4 en todo encargo.
- Con la respuesta, el Orquestador verifica rutas y líneas antes de editar, contrasta con `docs/contexto/` cualquier regla citada y, si el agente no cumple el encargo, aplica §15 en lugar de reintentar a ciegas.

## 15. Escalado

Cada nivel se intenta una sola vez. No se repite la misma consulta al mismo modelo.

| Agente | Primer fallo (respuesta incompleta, contradictoria o sin fuentes) | Segundo fallo |
|---|---|---|
| `explorador` | El Orquestador busca él mismo | — |
| `gemini-lector` | Repite la consulta, reformulada y más acotada, con `gemini-analista` | El Orquestador lee solo los fragmentos necesarios |
| `gemini-analista` | Repite una vez con las correcciones concretas | El Orquestador redacta y lo indica en el commit |
| `revisor` | Se relanza con una petición más acotada (un fichero o una regla) | Queda pendiente de revisión manual del desarrollador |

Casos especiales:

- **Error de cuota (HTTP 429):** no se escala a otro modelo externo. El Orquestador espera o hace la tarea él mismo, y avisa si se repite.
- **Resumen final:** se menciona cada escalado, para saber qué modelo hizo qué.

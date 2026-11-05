# TFM — Orquestador de negociación entre agentes A2A

## Qué es

Orquestador que media en negociaciones de compraventa entre negocios, llevadas a cabo por agentes que hablan el protocolo A2A, y que corrige en caliente los fallos de **estructura** de los mensajes mediante reglas deterministas. TFM del Máster en Ingeniería Informática (UGR) en colaboración con Unicaja.

## Cómo trabajamos

Todas las reglas de proceso (fuente de verdad, código, Ponytail, secretos, aprobación, Git, commits y TDD, LaTeX, versiones, agentes, modelos y escalado) están en `docs/contexto/proceso.md`, que se carga a continuación. Es la única fuente de esas reglas: si algo aquí o en otro fichero la contradice, manda `proceso.md`.

@docs/contexto/proceso.md

## Estructura del repositorio

```
CLAUDE.md
CHANGELOG.md             Una entrada por versión publicada
docs/
  contexto/              Lo que lee el agente. Fuente de verdad
    proceso.md           Reglas de proceso (única fuente)
    decisiones.md        Registro de decisiones cerradas (D-xx)
    roadmap.md           Hitos y funcionalidades que dan lugar a release
    protocolo.md         Actos, esquema de mensajes, ofertas
    maquina-estados.md   Estados y transiciones de una sesión de negociación
    autocorreccion.md    Catálogo de reglas de autocorrección (AC-xx)
    casos-de-uso/        Tarjetas CU-xx e índice con su estado
    plantillas/          Plantillas para gemini-analista
  latex/                 Lo que lee una persona. Reglas de redacción en latex/CLAUDE.md
    manual/              Manual de usuario, un fichero por capítulo
    tecnica/             Documentación técnica, un fichero por capítulo
  pdfs/                  PDF compilados (ver proceso.md §9)
.claude/
  agents/                Subagentes: explorador, revisor
  skills/                proponer-funcionalidad, implementar-rama, cerrar-release
  settings.json          Permisos
src/                     <se define con el desarrollador>
tests/
```

## Stack

- Lenguaje: Python 3.14, provisional hasta que `feature/setup` confirme que LangGraph y el SDK de A2A resuelven con ella; si no, 3.13 con aprobación del desarrollador (D-13)
- Agentes de las empresas: LangGraph, expuestos tras A2A
- Gestor de entorno y dependencias: `uv` (las dependencias se añaden con `uv add`, nunca con `pip`; `uv.lock` se versiona)
- Tests: `pytest`
- Lint y formato: `ruff`
- Tipos: anotaciones en todo el código, sin comprobador de tipos por ahora
- Almacén del estado externalizado: `<por decidir tras diseñar maquina-estados.md>`
- Documentación: LaTeX, sin plantilla institucional, compilada con `latexmk` y LuaLaTeX
- Modelos externos: Gemini vía `llm` (ver `proceso.md` §12)

No elijas tú lo que está marcado como «por decidir»: pregunta.

## Comandos

```
uv sync                                           (instalar dependencias)
uv run pytest                                     (ejecutar tests)
uv run ruff format . && uv run ruff check .       (formato y lint)
<levantar orquestador y agentes en local>
latexmk -lualatex -outdir=build <principal>.tex   (desde docs/latex/manual/ o docs/latex/tecnica/)
```

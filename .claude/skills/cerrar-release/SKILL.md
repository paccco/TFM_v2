---
name: cerrar-release
description: Propone, prepara y cierra una versión (rama release/) cuando se completa un hito importante del roadmap. Úsala cuando se cierre la rama de una funcionalidad marcada como importante en docs/contexto/roadmap.md, o cuando el desarrollador pida una release.
---

# Cerrar una release

Procedimiento para `docs/contexto/proceso.md` §10. Las reglas que cita (§N) están en ese fichero.

## Pasos

1. **Comprobar el hito.** Si algo falla, para y lista lo que falta:
   - Todas las ramas del hito en `docs/contexto/roadmap.md` están fusionadas en `develop`.
   - No hay ramas `feature/` o `bugfix/` abiertas del hito.
   - `develop` pasa tests y lint, y los dos documentos de `docs/latex/` compilan.
2. **Proponer la versión** (numeración en §10) y detenerte hasta un «aprobado» (§5):

   ```
   Release: vX.Y.Z
   Hito: <nombre del hito en el roadmap>
   Casos de uso incluidos: CU-xx, CU-yy…
   Decisiones nuevas desde la última versión: D-xx…
   Hotfixes incluidos: <lista, o «ninguno»>

   Responde «aprobado» para empezar.
   ```

3. **Abrir la rama**: `git flow release start vX.Y.Z`.
4. **PDF** (§9): compila los dos documentos, cópialos a `docs/pdfs/` y haz commit (§7).
5. **CHANGELOG y roadmap**: entrada de la versión al principio de `CHANGELOG.md` con su formato; el hito pasa a «publicado». Commit (§7).
6. **`finish`**: resume qué contiene la versión y pide confirmación para `git flow release finish vX.Y.Z` (§6). Detente.
7. **`push`**: tras el `finish`, pide confirmación aparte para el `push` de `main`, `develop` y la etiqueta (§6). Detente.

## Condiciones de parada

- Algún caso de uso del hito no está implementado.
- Fallan los tests, el lint o la compilación del LaTeX.
- Hay ramas abiertas que deberían entrar en la versión.
- El `finish` da conflictos: no los resuelvas por tu cuenta; avisa y espera.

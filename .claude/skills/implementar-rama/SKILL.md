---
name: implementar-rama
description: Implementa una propuesta ya aprobada por el desarrollador, desde abrir la rama con git flow hasta dejarla lista para cerrar. Úsala justo después de un «aprobado» a una propuesta de proponer-funcionalidad, para feature/, feature/docs-, bugfix/ y hotfix/.
---

# Implementar una rama aprobada

Procedimiento para `docs/contexto/proceso.md` §8. Las reglas que cita (§N) están en ese fichero. Sin un «aprobado» explícito a una propuesta, no empieces.

## Qué pasos aplican a cada tipo de rama

| Paso | `feature/` | `bugfix/` · `hotfix/` | `feature/docs-` |
|---|---|---|---|
| 1. Abrir rama | ✓ | ✓ (`hotfix/` sale de `main`) | ✓ |
| 2. Commit inicial | ✓ | ✓ | ✓ |
| 3. Capas con TDD | ✓ | ✓ (test que reproduce el fallo) | — |
| 4. Tests y lint | ✓ | ✓ | — |
| 5. `ponytail-review` | ✓ | ✓ | — |
| 6. LaTeX, índice, CHANGELOG, PDF | ✓ | Si cambia algo visible o documentado | ✓ (es el cambio en sí) |
| 7. Revisor | Si toca su cometido | Si toca su cometido | — |
| 8. Resumen y parada | ✓ | ✓ | ✓ |

## Pasos

1. **Abrir la rama** con `git flow`, del tipo y con el nombre exactos de la propuesta (§6).
2. **Commit inicial** vacío con la propuesta aprobada en el cuerpo (§7).
3. **Capas con TDD estricto** (§7), solo las que toque la propuesta y en el orden de §8. Por capa:
   - Escribe los tests, ejecútalos y comprueba que fallan por el motivo esperado. Commit en rojo.
   - Escribe el código mínimo, ejecuta todos los tests de la rama. Commit en verde.
4. **Tests y lint completos** con los comandos de `CLAUDE.md`. Si aún no están definidos, avisa y no continúes.
5. **`ponytail-review`** sobre el diff (§3). Aplica solo los recortes que no quiten nada exigido por `docs/contexto/`, vuelve a pasar tests y lint, y haz commit si has aplicado algo. Los descartados van al resumen con su motivo.
6. **Documentación** (§9), en un commit:
   - Capítulos de `docs/latex/` indicados en la propuesta, siguiendo `docs/latex/CLAUDE.md`, y compilación de comprobación.
   - Si esta rama completa todos los AC de la tarjeta según `docs/contexto/roadmap.md`, la tarjeta pasa a «implementado» en `docs/contexto/casos-de-uso/README.md`. Si quedan AC para otra rama, sigue en «aprobado».
   - En `hotfix/`, entrada de la versión patch en `CHANGELOG.md` (§10).
   - En `hotfix/` que haya cambiado `docs/latex/`: PDF a `docs/pdfs/`, en un commit aparte.
7. **Revisor** (§11), si el cambio toca su cometido, contra `develop` (contra `main` en `hotfix/`):
   - Bloqueantes: corrígelos, tests y lint, commit, y relanza una sola vez. Si siguen, para (§15).
   - Mejoras: no las apliques; van al resumen.
8. **Resumen** (§2), incluyendo recortes de Ponytail descartados y mejoras del revisor sin aplicar. Pide confirmación para el `finish`; tras él, confirmación aparte para el `push` (§6).

## Condiciones de parada

Para y avisa, sin cerrar la rama, si:

- Hay que salirse del alcance aprobado (vuelve a `proponer-funcionalidad`).
- `docs/contexto/` resulta ambiguo o contradictorio en algo que ha aparecido al implementar.
- Un test no falla en rojo como se esperaba, o falla en verde y no sabes arreglarlo sin cambiar lo aprobado.
- Hace falta una dependencia que no estaba en la propuesta.
- El revisor mantiene bloqueantes tras el segundo intento.

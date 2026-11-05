---
name: proponer-funcionalidad
description: Prepara la propuesta que el desarrollador debe aprobar antes de crear una rama feature/, feature/docs-, bugfix/ o hotfix/ (las release/ van con cerrar-release). Úsala siempre que te pidan implementar un caso de uso, corregir algo o cambiar documentación, antes de tocar Git o escribir ficheros.
---

# Proponer una funcionalidad

Procedimiento para cumplir `docs/contexto/proceso.md` §5. Las reglas están allí; aquí, los pasos y los formatos.

Durante toda la skill: solo lectura, y delegación únicamente en `explorador` y `gemini-lector`.

## Pasos

1. **Leer la especificación.** Si es un caso de uso, su tarjeta en `docs/contexto/casos-de-uso/` y las D-xx y AC-xx que cita.
2. **Comprobar que es implementable.** No hagas propuesta, y pregunta, si:
   - la tarjeta no existe o no está «aprobado» en `docs/contexto/casos-de-uso/README.md`;
   - cita reglas que no existen;
   - contradice otra parte de `docs/contexto/`;
   - es ambigua en algo que cambia la implementación.
3. **Localizar lo afectado** con `explorador`; documentación externa, si hace falta, con `gemini-lector`.
4. **Medir el alcance.** Si no cabe en una rama con un solo objetivo, propón dividirlo y pregunta por cuál empezar.
5. **Redactar la propuesta** con el formato que corresponda.
6. **Detenerte** esperando la respuesta.

## Formato completo (`feature/`)

```
Rama: feature/cu-xx-<tema>
Qué hará: <dos o tres frases>
Implementa: CU-xx · D-xx · AC-xx
Ficheros: <rutas que tocarás o crearás>
Tests: <al menos uno por criterio de aceptación de la tarjeta>
LaTeX: <capítulos de docs/latex/manual y docs/latex/tecnica que actualizarás>
Dependencias nuevas: <ninguna, o cuáles y por qué>
Dudas o suposiciones: <lista, o «ninguna»>

Responde «aprobado» para empezar.
```

## Formato corto (`bugfix/`, `hotfix/`, `feature/docs-`)

```
Rama: <tipo>/<tema>
Qué hará: <dos o tres frases>
Ficheros: <rutas>
Tests: <cuáles, o «no aplica» si es solo documentación>

Responde «aprobado» para empezar.
```

## Respuesta del desarrollador

| Respuesta | Qué haces |
|---|---|
| «aprobado» | Pasa a la skill `implementar-rama` con la propuesta tal cual |
| Correcciones de cualquier tipo | Rehaz la propuesta entera y vuelve a esperar |
| Cualquier otra cosa | No hagas nada. Si no está claro, pregunta |

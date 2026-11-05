# Documentación en LaTeX — reglas de redacción

Este fichero solo aplica cuando trabajas en `docs/latex/`. Cuándo se actualiza, quién la redacta, cómo se compila y cuándo se suben los PDF está en `docs/contexto/proceso.md` §9; aquí solo va **cómo se escribe**.

## Qué hay aquí

| Carpeta | Para quién | Qué cuenta |
|---|---|---|
| `manual/` | Quien usa el sistema | Cómo instalarlo, configurarlo, lanzar una negociación, leer el resultado y qué hacer ante cada error visible |
| `tecnica/` | Quien mantiene el código o evalúa el TFM | Arquitectura, componentes, flujo de una sesión, protocolo, máquina de estados, autocorrección, decisiones y pruebas |

Cada documento tiene un fichero principal y un fichero por capítulo, incluido desde el principal.

## Relación con `docs/contexto/`

- No copies la especificación: explícala, con ejemplos y diagramas, y cita los IDs (`D-xx`, `R-xx`, `AC-cc-nn`, `CU-xx`) para que se pueda contrastar.
- Nunca introduzcas aquí una regla, un acto, un estado o un comportamiento que no esté en `docs/contexto/` o en el código. Si al redactar ves un hueco o una contradicción, para y pregunta.
- Documenta lo implementado, no lo previsto. Lo pendiente, si se menciona, va marcado como tal.

## Estilo

- Español, en registro técnico claro. Frases cortas.
- Sin plantilla institucional por ahora: preámbulo propio y sobrio, común a los dos documentos. No añadas paquetes sin acordarlo.
- Los términos del protocolo se escriben igual que en `docs/contexto/` (`PROPOSE`, `COUNTEROFFER`, `ACCEPT`, `WITHDRAW`, `ABORTED`; D-32).
- Diagramas de estados y de secuencia generados desde fuente (no imágenes pegadas), para que se puedan revisar en el diff.
- Nada confidencial de Unicaja, claves ni datos reales en ejemplos.

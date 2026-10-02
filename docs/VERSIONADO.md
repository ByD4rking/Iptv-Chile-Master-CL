# Política de versionado

## Estados

| Estado | Significado |
|---|---|
| 🟢 ESTABLE | Versión validada y apta para producción. |
| 🟡 BETA | Mejora funcional bajo pruebas reales y regresión. |
| 🟠 RC | Candidata a estable; solo se aceptan correcciones críticas. |
| 🔴 EXPERIMENTAL | Prueba de arquitectura o comportamiento todavía no validado. |

## Flujo

`ESTABLE → BETA → RC → ESTABLE`

Cada mejora importante debe desarrollarse fuera de `main`, conservar un punto de rollback y documentar cambios, pruebas y riesgos.

## Reglas

1. `main` conserva la versión estable.
2. Toda mejora de comportamiento relevante comienza como BETA o EXPERIMENTAL.
3. Una Action exitosa no convierte automáticamente una versión en estable.
4. Para pasar a RC deben existir pruebas repetidas y regresión del sistema.
5. Para pasar a ESTABLE deben estar superados los criterios de estabilidad, calidad, seguridad, aislamiento y regresión.
6. Las listas Principal, GOD y Pluto deben permanecer aisladas cuando una mejora pertenece al Generador.
7. Cada versión debe indicar qué cambió, qué se verificó y qué queda pendiente.
8. Debe existir un punto de rollback antes de integrar cambios de riesgo.

## Identificación

Formato recomendado:

- `v1.0.0` — 🟢 ESTABLE
- `v1.1.0-beta.1` — 🟡 BETA
- `v1.1.0-beta.2` — 🟡 BETA
- `v1.1.0-rc.1` — 🟠 RC
- `v1.1.0` — 🟢 ESTABLE

El número de versión solo debe avanzar cuando el cambio tenga un estado verificable.

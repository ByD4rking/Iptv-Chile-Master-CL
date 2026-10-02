# Changelog — IPTV Chile Master

## v1.1.0-beta.1 — 🟡 BETA

**Estado:** experimental, no sustituye todavía a la versión estable de `main`.

### Mejoras implementadas
- Validación de continuidad HLS mediante varios segmentos consecutivos.
- La publicación de HLS requiere reproducción válida y continuidad comprobada.
- Historial persistente de muestras por endpoint, limitado para evitar crecimiento indefinido.
- Métricas de disponibilidad de 7 y 30 días cuando existe historial suficiente.
- Registro explícito de estabilidad, segmentos comprobados y motivo de fallo.
- Workflow dedicado para probar la mejora sin publicar cambios en las listas estables.
- Verificación de aislamiento para evitar modificaciones accidentales fuera del Generador.

### Criterio de esta beta
Una respuesta HTTP 200 o un manifiesto HLS válido por sí solo no se considera suficiente para publicar un stream HLS.

### Pendiente antes de RC
- Ejecutar y revisar varias corridas reales del pipeline.
- Confirmar que la continuidad HLS reduce falsos positivos sin eliminar streams válidos de forma excesiva.
- Revisar métricas de recuperación/reconexión con datos reales.
- Ejecutar regresión completa de Principal, GOD y Pluto sin cambios en sus listas protegidas.

### Promoción
`beta → RC → estable` solamente después de superar los criterios de calidad definidos en `docs/VERSIONADO.md` y `docs/CALIDAD.md`.

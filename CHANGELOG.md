# 📋 Historial de versiones

## v1.1.0-beta.1 — 🟡 BETA

Primera beta de la nueva línea de estabilidad y calidad.

### Mejoras aplicadas

- Validación HLS basada en reproducción real y **3 segmentos consecutivos**.
- Reintentos con backoff ante fallos transitorios.
- Historial persistente por endpoint/fuente para diferenciar fallos aislados de inestabilidad repetida.
- Cuarentena temporal de endpoints con fallos persistentes.
- Selección de endpoint priorizando estabilidad histórica antes que resolución nominal.
- Manifest de pipeline para comprobar que los artefactos pertenecen al mismo snapshot.
- Self-test ampliado para detectar inconsistencias, duplicados y selección incorrecta.
- Directivas de reconexión/caché conservadas en la salida M3U.
- Quality gates específicos para la beta.
- Verificación de aislamiento para impedir cambios accidentales en Principal, Pluto y scripts externos.

### Estado

Esta versión es **BETA** y no sustituye v1.0.0 — 🟢 ESTABLE.

La promoción seguirá: v1.1.0-beta.1 → pruebas → v1.1.0-beta.2 → v1.1.0-rc.1 → v1.1.0

Una ejecución verde de Actions no basta por sí sola para promover a estable.

## v1.0.0 — 🟢 ESTABLE

Versión estable de referencia del proyecto.

- Lista principal, GOD y Pluto TV mantienen alcances independientes.
- IPTV-CHILE-GENERADOR permanece aislado de las listas maestras y Pluto.
- El proyecto utiliza validaciones y automatizaciones para mantenimiento y publicación.
- Los enlaces RAW y las descargas directas se documentan por playlist.

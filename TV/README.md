# IPTV Chile TV

Implementación independiente del reproductor para **Fire TV, Samsung Tizen y LG webOS**.

## Qué queda implementado

- Catálogo desde `IPTV-CHILE-GENERADOR.m3u`.
- Reproductor HTML5/HLS.
- Detección de `error`, `stalled` y `ended`.
- Reconexión con backoff exponencial y máximo de 6 intentos.
- Navegación con teclado/control remoto.
- Build Fire TV mediante Gradle.
- Empaquetado Samsung Tizen mediante CLI de Tizen Studio.
- Empaquetado LG webOS mediante `ares-package`.
- CI separado del generador IPTV.

## Validación

CI puede validar código, estructura y builds cuando los SDK están disponibles. La instalación y reproducción en un televisor físico **no puede ser simulada** y debe ejecutarse en el hardware correspondiente.

Las listas maestras y Pluto no son modificadas por esta aplicación.
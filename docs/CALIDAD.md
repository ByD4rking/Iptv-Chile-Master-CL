# Criterios de calidad

La calidad de un stream no se determina únicamente por HTTP 200.

## Puertas de calidad

### 📺 Estabilidad
- Manifest HLS válido.
- Segmentos accesibles.
- Varios segmentos consecutivos válidos.
- Reproducción comprobada.
- Historial de fallos y recuperaciones.
- Tasa de disponibilidad 7/30 días cuando haya muestras suficientes.

### 🎞️ Calidad técnica
Evolución prevista del sistema:
- resolución;
- bitrate;
- FPS;
- códec de vídeo;
- códec de audio;
- presencia de audio y vídeo.

### ⚡ Rendimiento
Evolución prevista:
- TTFB/latencia;
- timeouts;
- errores por segmento;
- tiempo de recuperación;
- número de reconexiones.

### 🧠 Salud
El Health Score debe combinar señales observables y no sustituir las mediciones primarias.

## Regla de publicación

Un stream HLS no debe publicarse como saludable si falla la reproducción o la continuidad mínima exigida por la validación activa.

## Principio

**Menos streams realmente utilizables es preferible a inflar el catálogo con streams que se cortan durante la reproducción.**

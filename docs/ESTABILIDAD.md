# Estabilidad de streams

## Objetivo

Medir estabilidad de reproducción real, no solamente disponibilidad HTTP.

## Pipeline

`SOURCE → DISCOVERY → CANDIDATE → VALIDATION → HLS CONTINUITY → HEALTH → DECISION → PUBLICATION`

## HLS

La validación comprueba segmentos consecutivos para detectar fallos que una consulta aislada puede ocultar.

La continuidad mínima activa en esta beta es de **3 segmentos consecutivos**.

## Historial

El Generador conserva muestras recientes por endpoint, con límite de **120 muestras**, para evitar crecimiento indefinido.

Las métricas derivadas incluyen disponibilidad de 7 y 30 días cuando existe suficiente historial.

## Recuperación

La siguiente evolución debe distinguir:
- fallos transitorios: timeout, 502, 503, reset y errores temporales de segmento;
- fallos persistentes: 404, 410 y recursos inexistentes;
- degradación HLS: manifiesto válido pero segmentos ausentes, congelados o no reproducibles.

La estrategia de retry/reconexión debe ser específica al tipo de fallo y no generar tráfico innecesario hacia fuentes que ya no existen.

## Aislamiento

La mejora de estabilidad se prueba en el Generador y no debe modificar las playlists Principal, GOD o Pluto salvo una integración explícita y validada.

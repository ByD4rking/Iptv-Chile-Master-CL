# FASE 2 — Validación y normalización segura de fuentes M3U

## Qué corrige automáticamente (solo en memoria)
- Elimina BOM UTF-8.
- Uniforma saltos CRLF/CR a LF.
- Recorta espacios periféricos de las líneas y asegura un salto final.
- Conserva nombres, categorías, logos y URLs de canal.

## Qué nunca intenta reparar
- Respuestas HTML, páginas de error o contenido vacío.
- Cabeceras M3U ausentes o inválidas.
- Entradas EXTINF sin URI o URI mal formadas.
- Codificación UTF-8 corrupta.
- URLs de canal ausentes o inventadas.

La normalización no escribe ni publica archivos. Las fuentes se validan antes de generar snapshots; si el contenido no es inequívocamente una M3U válida, la auditoría falla de forma cerrada y conserva la fuente original sin alterarla.

Se admiten esquemas de stream habituales y no HTTP (por ejemplo RTSP y RTMP); la validación no reduce todas las señales a HTTP(S).

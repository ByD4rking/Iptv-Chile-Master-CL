# FASE 3 — Auditoría operativa con datos reales

**Fecha de ejecución:** 2026-11-25  
**Rama de trabajo:** `phase3/validacion-operativa-20261125`  
**Playlist examinada:** `IPTV-CHILE-MAESTRA_CORREGIDO.m3u`  
**Modo:** solo lectura; ninguna URL, categoría o referencia de logo fue modificada.

## Identidad y regresiones

Comparación del snapshot anterior de `main` con la playlist actual:

- Canales antes/después: **4.516 / 4.516**.
- Coincidencias: **4.516**.
- Altas/bajas detectadas: **0 / 0**.
- Ambigüedades restantes: **0**.
- Cambios de categoría: **1**, señalado como violación pendiente de clasificación.
- Cambios de stream: **477**; se informan, no se sustituyen.
- Logos reemplazados entre snapshots: **0**.
- Huellas de stream duplicadas: **1**. La misma URL aparece en `Señal Perú TV (404p) [Not 24/7]` y `Señal Perú TV HD [No 24/7] (Lima)`; no se elimina ninguna entrada.

El cambio de categoría detectado es `PTV OnLine`, de `Entretenimiento / Cine / Series` a `Bolivia`. La ubicación en Bolivia parece coherente con el nombre y la organización regional, pero se conserva como hallazgo hasta que quede clasificado explícitamente. El detector no revierte movimientos automáticamente.

La primera ejecución produjo miles de falsas altas/bajas por tratar `channelId="-1"` como identidad y por no distinguir variantes con identificadores compartidos. Se corrigió: se descartan IDs placeholder, se distinguen opciones explícitas, se usan streams idénticos para desambiguar cuando corresponde y se conservan como ambiguos los casos sin evidencia suficiente. La prueba real terminó con 4.516/4.516 coincidencias y cero altas, bajas o ambigüedades.

## Compatibilidad de logos

Auditoría estática de las 4.516 entradas:

- Referencias de logo únicas: **2.997**.
- Referencias inválidas: **0**.
- Canales sin `tvg-logo` y sin `logo`: **76**.
- Referencias que requieren revisión por formato/transporte: **141**.
- Conflictos entre `tvg-logo` y `logo`: **17**.
  - **12** tienen evidencia de que `tvg-logo` coincide con `tvg-id` y `logo` apunta a otro ID Pluto.
  - **5** requieren revisión manual.

El informe solo recomienda revisar. No descarga imágenes, no reemplaza campos y no certifica el renderizado. La prueba visual en Televizo y SS IPTV sigue pendiente; no se debe marcar compatibilidad real hasta probar ambos reproductores.

## Recuperación de fuentes

Se inspeccionaron **26 fuentes configuradas**. **12** superaron la validación estructural estricta; las demás se omitieron y no se usaron como candidatas.

Con la playlist principal, el historial de salud y las fuentes M3U válidas:

- Canales que requieren recuperación según el historial: **1.033**.
- Canales de las fuentes candidatas: **5.848**.
- Canales con una propuesta no ambigua: **4**.
- Candidatos ambiguos descartados: **244**.

Propuestas encontradas:

| Canal | Fuente | Coincidencia |
|---|---|---|
| Los Simpson Latino | JMIGUE-IPTVSV | Nombre y categoría únicos |
| RPP TV (Perú - Nacional) | JMIGUE-IPTVSV | Nombre y categoría únicos |
| Comercio TV | SPECIAL-fear_factor | Identidad fuerte |
| KCHTV SD (Guayas) [Opc.2] | JMIGUE-IPTVSV | Nombre y categoría únicos |

Son propuestas, no fuentes verificadas. No se ha confirmado reproducción HLS de estos candidatos y no se reemplazó ninguna URL. Cada candidato debe superar una prueba real de reproducción antes de cualquier sustitución.

## Recuperación de logos faltantes

Cruce de los **76** canales sin logo con las 12 fuentes M3U válidas:

- **52** propuestas de referencia de logo.
- **37** con identidad fuerte (ID coincidente y único).
- **15** por nombre/categoría únicos, de menor confianza.
- **0** propuestas ambiguas.
- **24** canales sin una referencia candidata.

Las propuestas usan formatos raster admitidos por la auditoría (PNG/JPEG/WebP/GIF). Ninguna se aplicó a la playlist. Se mantienen como propuestas hasta verificar que la imagen se descarga y se muestra correctamente en Televizo y SS IPTV.

## Estado y límites

- Los scripts y el workflow de FASE 3 pasaron sus pruebas automatizadas y la auditoría operativa terminó correctamente.
- El informe operativo puede contener hallazgos que el detector clasifica como violaciones; que el workflow termine correctamente significa que la auditoría se ejecutó y guardó sus resultados, no que todas las reglas del snapshot estén limpias.
- No se modificaron la playlist principal, `IPTV-CHILE-MAESTRA_GOD.m3u`, el Generador ni sus workflows.
- No se cambió ningún logo ni se sustituyó ninguna URL.
- FASE 3 no está completa: falta verificar reproducción de candidatos y probar visualmente logos en Televizo y SS IPTV.

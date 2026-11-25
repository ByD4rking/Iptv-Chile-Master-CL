# FASE 3 — Auditoría operativa con datos reales

**Fecha de ejecución:** 2026-11-25  
**Rama de trabajo:** `phase3/validacion-operativa-20261125`  
**Playlist examinada:** `IPTV-CHILE-MAESTRA_CORREGIDO.m3u`  
**Modo:** solo lectura; ninguna URL, categoría o referencia de logo fue modificada.

## Identidad y regresiones

Comparación del snapshot anterior de `main` con la playlist actual:

- Canales antes/después: **4.516 / 4.516**.
- Coincidencias: **4.516**.
- Altas/bajas: **0 / 0**.
- Ambigüedades: **0**.
- Cambios de categoría: **1**, aprobado mediante excepción exacta y documentada.
- Cambios de stream informados: **477**; no se sustituyó ninguna URL.
- Logos reemplazados entre snapshots: **0**.
- Huellas de stream duplicadas: **1**.

El cambio de categoría corresponde a **PTV OnLine**, de `Entretenimiento / Cine / Series`
a `Bolivia`. Se comprobó la fuente IPTVSV de JMigue85 y el canal aparece allí con
`group-title="Bolivia"`; por eso se incorporó una excepción exacta al detector.
El resultado de regresiones quedó **aprobado, sin violaciones**.

La huella duplicada corresponde a la misma URL usada por `Señal Perú TV (404p)
[Not 24/7]` y `Señal Perú TV HD [No 24/7] (Lima)`. Se conserva como hallazgo:
no se elimina ninguno de los dos canales sin evidencia adicional.

La identidad fue corregida para descartar IDs placeholder como `channelId="-1"`,
distinguir variantes explícitas y usar evidencia de stream cuando procede. Resultado:
4.516/4.516 coincidencias sin altas, bajas ni ambigüedades.

## Compatibilidad y recuperación de logos

Auditoría estática de las 4.516 entradas:

- Referencias de logo únicas: **2.997**.
- Referencias inválidas: **0**.
- Canales sin `tvg-logo` ni `logo`: **76**.
- Referencias que requieren revisión por formato/transporte: **141**.
- Conflictos entre `tvg-logo` y `logo`: **17** (12 con evidencia de ID Pluto y 5 manuales).

Recuperación de logos:

- Propuestas: **52** (37 identidad fuerte y 15 fallback único).
- Recursos únicos comprobados: **47**.
- Descargas y firmas válidas: **47/47** (42 PNG y 5 JPEG).
- Canales sin propuesta: **24**.
- Propuestas ambiguas: **0**.

Ningún logo se aplicó ni se reemplazó. La descarga y la firma válida no prueban
renderizado en Televizo o SS IPTV; esa validación visual sigue pendiente.

## Recuperación y prueba de fuentes

Se inspeccionaron **26 fuentes configuradas**; **12** superaron la validación
estructural M3U. El historial marcaba **1.033** canales para revisión y las fuentes
candidatas aportaron **5.848** registros. Se generaron cuatro propuestas no ambiguas;
244 coincidencias ambiguas fueron descartadas.

| Canal | Fuente | Identidad | Prueba de muestra |
|---|---|---|---|
| Los Simpson Latino | JMIGUE-IPTVSV | Fallback único | **Correcta** |
| RPP TV (Perú - Nacional) | JMIGUE-IPTVSV | Fallback único | **Correcta** |
| Comercio TV | CERESLABX-US-TV | Fuerte | **Correcta** |
| KCHTV SD (Guayas) [Opc.2] | JMIGUE-IPTVSV | Fallback único | **Correcta** |

La etiqueta anterior `SPECIAL-fear_factor` se corrigió a `CERESLABX-US-TV`.
La playlist fuente contiene tanto Comercio TV como Fear Factor; el nombre anterior
era engañoso porque la URL apunta a una playlist general de EE. UU.

Las cuatro alternativas superaron una prueba HTTP de manifiesto/muestra de segmento
desde GitHub Actions. Esto confirma una muestra reproducible en ese entorno, no
reproducción continua, estabilidad a largo plazo ni acceso desde todas las regiones.
No se reemplazó ninguna URL en la playlist principal.

## Estado y límites

- Las pruebas automatizadas de identidad, regresiones, logos y recuperación pasaron
  en la rama de FASE 3.
- El workflow es de auditoría; no publica cambios en listas.
- No se modificaron `IPTV-CHILE-MAESTRA_CORREGIDO.m3u`,
  `IPTV-CHILE-MAESTRA_GOD.m3u`, `IPTV-CHILE-GENERADOR/**` ni sus workflows.
- No se cambió ningún logo ni se sustituyó ninguna URL.
- **FASE 3 aún no está completa:** falta probar visualmente los logos en Televizo y
  SS IPTV. La prueba de fuentes es una muestra corta, no un test de reproducción
  prolongada.

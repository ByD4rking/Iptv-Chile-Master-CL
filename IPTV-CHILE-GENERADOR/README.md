# IPTV-CHILE-GENERADOR

Generador **independiente** de playlist M3U para canales de Chile.

## 🔒 Regla de aislamiento

Este proyecto **no usa como fuente** ninguna de las listas maestras, Pluto ni scripts externos del repositorio.

### Fuentes externas independientes

Las fuentes se definen en `config/sources.json` y actualmente incluyen:

- IPTV-ORG Chile
- DearBulut Chile
- JROMERO Chile

Se descargan por HTTPS durante la ejecución. Si una fuente falla, las demás pueden seguir aportando canales.

Las URLs se identifican por su dirección: **misma URL = mismo stream**, aunque tenga nombres diferentes.

## Flujo de generación

```
sources.json
     ↓
collect.py
     ↓
channels.json
     ↓
check.py ──→ status.json + history.json
     ↓
quality.py ─→ quality.json
     ↓
generate.py
     ↓
IPTV-CHILE-GENERADOR.m3u
     ↓
selftest.py
```

### Componentes

- **collect.py**: descarga y normaliza las fuentes y mantiene `data/source_health.json` con éxitos, fallos consecutivos, último error y última descarga válida por fuente.
- **check.py**: comprueba disponibilidad y mide latencia.
- **quality.py**: detecta resolución/bitrate y valida reproducción real: para HLS comprueba playlist, variante y al menos un segmento; para streams directos verifica que la respuesta no sea HTML y contenga datos.
- **generate.py**: solo publica URLs con disponibilidad HTTP y reproducción verificada; prioriza resolución, bitrate, latencia y finalmente prioridad de fuente.
- **fix_encoding.py**: corrige problemas de codificación en metadatos; nunca altera URLs.
- **guard.py**: calcula huellas de las áreas protegidas.
- **selftest.py**: verifica integridad, unicidad, procedencia, salud de fuentes y que cada URL publicada tenga reproducción verificada.

## 🛡️ Protección de las otras listas

El workflow del generador verifica antes y después de ejecutarse:

- `IPTV-CHILE-MAESTRA_CORREGIDO.m3u`
- `IPTV-CHILE-MAESTRA_GOD.m3u`
- `pluto/output/playlists/`
- `scripts/`

Si detecta una modificación fuera de `IPTV-CHILE-GENERADOR/`, la ejecución falla y **no publica cambios**.

El commit automático solo añade:

```
IPTV-CHILE-GENERADOR/
```

## 📡 Salud y fallos de fuentes

Cada ejecución registra por fuente:

- cantidad de comprobaciones;
- éxitos y fallos acumulados;
- fallos consecutivos;
- última ejecución exitosa;
- último fallo y mensaje de error;
- cantidad de entradas de la última descarga válida.

Una fuente que falla no elimina las demás: si al menos una fuente independiente responde correctamente, la generación continúa. Si fallan todas, el workflow se detiene en lugar de publicar una M3U basada en datos inciertos.

## ▶️ Validación real de reproducción

El generador no considera suficiente un `HTTP 200`. Las URLs HLS pasan por una validación adicional de playlist, variante y segmento. Una URL que responda pero no entregue un segmento reproducible queda fuera de la M3U final.

## 📦 Historial

El historial de disponibilidad se limita automáticamente a las últimas **5.000 URLs**, evitando que `history.json` crezca indefinidamente.

## 🚫 Dependencias prohibidas

No se permiten:

- rutas locales del PC en `sources.json`;
- dependencia de las M3U maestras;
- dependencia de Pluto;
- escritura fuera de `IPTV-CHILE-GENERADOR/`;
- duplicados de URL;
- publicación de una M3U que contenga URLs que no provengan de las fuentes configuradas.

## Automatización

El workflow se ejecuta:

- cada 6 horas;
- manualmente mediante `workflow_dispatch`;
- ante cambios del propio generador.

Las acciones externas usadas por el workflow están fijadas a commits SHA para reducir el riesgo de cambios inesperados en dependencias.
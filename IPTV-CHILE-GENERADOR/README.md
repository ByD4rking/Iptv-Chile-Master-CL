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

- **collect.py**: descarga y normaliza las fuentes.
- **check.py**: comprueba disponibilidad y mide latencia.
- **quality.py**: detecta resolución y bitrate.
- **generate.py**: selecciona streams online, priorizando calidad y después prioridad de fuente.
- **fix_encoding.py**: corrige problemas de codificación en metadatos; nunca altera URLs.
- **guard.py**: calcula huellas de las áreas protegidas.
- **selftest.py**: verifica integridad de datos, unicidad y procedencia de URLs.

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
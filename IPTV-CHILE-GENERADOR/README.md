# IPTV-CHILE-GENERADOR

Generador independiente de playlist M3U de Chile.

## Aislamiento

Este proyecto solo debe escribir dentro de IPTV-CHILE-GENERADOR/.

Rutas externas de solo lectura:
- IPTV-CHILE-MAESTRA_CORREGIDO.m3u
- IPTV-CHILE-MAESTRA_GOD.m3u
- pluto/output/playlists/
- scripts/

El CI guarda SHA-256 antes de ejecutar y falla si una ruta externa cambia. El commit automático solo añade IPTV-CHILE-GENERADOR.

## Flujo

collect.py -> check.py -> quality.py -> generate.py

fix_encoding.py corrige nombres sin alterar URLs.
guard.py audita el perímetro.

La URL es el identificador único; el nombre no se usa para deduplicar.

sources.json admite path local y url HTTP/HTTPS. Las rutas locales actuales funcionan en PC, pero GitHub Actions no puede leer archivos del equipo local. Para automatización remota completa se deben configurar fuentes HTTP/HTTPS.

Salida única: IPTV-CHILE-GENERADOR.m3u.

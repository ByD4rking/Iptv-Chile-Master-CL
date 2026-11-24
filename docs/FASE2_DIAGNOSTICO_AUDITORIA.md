# FASE 2 — Diagnóstico de auditoría en solo lectura

**Rama:** `phase2/diagnostico-auditoria-20261124`

## Alcance de esta entrega

- Comparar los atributos `tvg-logo` y `logo` entre dos snapshots M3U.
- Detectar altas y bajas por identidad de canal, sin editar ninguna lista.
- Clasificar errores de fuentes separando restricciones de acceso, fallos transitorios, respuestas inválidas y candidatos a caída permanente.
- Exigir al menos dos observaciones independientes (ejecuciones distintas) para confirmar un HTTP 404/410; los reintentos dentro de una misma ejecución no cuentan.
- Redactar valores sensibles de parámetros de URL en los detalles del reporte.

## Límites de seguridad

Esta herramienta no hace peticiones de red, no valida reproducción HLS, no actualiza URLs, no modifica logos, no mueve canales y no publica listas. Un cambio de logo se informa como anomalía para revisión humana; nunca se corrige automáticamente.

No se modifican:
- `IPTV-CHILE-MAESTRA_GOD.m3u`
- `IPTV-CHILE-GENERADOR/` ni sus workflows
- `IPTV-CHILE-MAESTRA_CORREGIDO.m3u`
- workflows de publicación principal o Pluto

## Ejecución manual

```bash
python scripts/auditoria_comparativa_solo_lectura.py \
  --before /ruta/playlist-anterior.m3u \
  --after /ruta/playlist-actual.m3u \
  --source-report /ruta/auditoria_principal.json
```

El resultado se imprime en stdout. Para guardarlo, añadir `--output informe.json`.

## Aprobación

La integración requiere que el workflow dedicado de pruebas termine en verde y que la revisión confirme que el diff contiene únicamente esta herramienta, sus pruebas, su documentación y su workflow de validación aislado.

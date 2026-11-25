# FASE 3 — Entrega 2: detector de regresiones de playlist

## Qué comprueba
- Bajas de canales frente al snapshot anterior (bloqueadas por defecto).
- Cambios de categoría (bloqueados por defecto salvo transición exacta revisada).
- Reemplazo o eliminación de logos que ya existían (bloqueados por defecto).
- Cambios reales de URL de stream (informados; bloqueables con una opción).
- Duplicados de fingerprint de stream y coincidencias ambiguas (informados).
- Validez estructural M3U de ambos snapshots antes de comparar.

La rotación de JWT y los identificadores efímeros `sessionid`, `sid`, `deviceid`
y `clientid` se excluyen del fingerprint. Los valores nunca se imprimen ni se
guardan en el informe. Los parámetros semánticos como `country`, región e idioma
siguen formando parte del fingerprint para no ocultar cambios de distribución.

## Excepción explícita de categoría
Una transición revisada se permite solo con canal, categoría de origen y destino
exactos. La excepción no relaja otras categorías ni permite bajas o reemplazos
de logos.

```bash
python -m scripts.playlist_regression \
  --before anterior.m3u \
  --after actual.m3u \
  --allow-category-change "PTV OnLine|Entretenimiento / Cine / Series|Bolivia" \
  --output regresiones.json
```

Límites opcionales:
- `--max-removed N`
- `--max-category-changes N`
- `--max-logo-replacements N`
- `--fail-on-stream-change`
- `--allow-category-change "CANAL|ORIGEN|DESTINO"` (repetible)

El código de salida es 0 si pasa y 2 si encuentra una violación.

## Seguridad y alcance
Herramienta diagnóstica, sin escrituras en playlists ni acciones de publicación.
La excepción PTV OnLine se justificó al comprobar que la fuente IPTVSV de JMigue85
declara el canal en `group-title="Bolivia"`. No se crean excepciones genéricas.
No modifica GOD ni el Generador.

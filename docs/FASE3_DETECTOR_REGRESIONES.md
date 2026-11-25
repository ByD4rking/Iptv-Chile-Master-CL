# FASE 3 — Entrega 2: detector de regresiones de playlist

## Qué comprueba
- Bajas de canales frente al snapshot anterior (bloqueadas por defecto).
- Cambios de categoría (bloqueados por defecto).
- Reemplazo o eliminación de logos que ya existían (bloqueados por defecto).
- Cambios reales de URL de stream (informados; bloqueables con una opción).
- Duplicados de fingerprint de stream y coincidencias ambiguas (informados).
- Validez estructural M3U de ambos snapshots antes de comparar.

La rotación de JWT y otros parámetros efímeros se excluye del fingerprint para
evitar falsos positivos durante la renovación normal de Pluto TV.

## Uso
\`\`\`bash
python -m scripts.playlist_regression \
  --before anterior.m3u \
  --after actual.m3u \
  --output regresiones.json
\`\`\`

Límites opcionales:
- \`--max-removed N\`
- \`--max-category-changes N\`
- \`--max-logo-replacements N\`
- \`--fail-on-stream-change\`

El código de salida es 0 si pasa y 2 si encuentra una violación.

## Seguridad y alcance
Herramienta diagnóstica, sin escrituras en playlists ni acciones de publicación.
Todavía no está conectada al workflow de actualización principal: primero debe
validarse con snapshots históricos y casos reales. No modifica GOD ni el Generador.

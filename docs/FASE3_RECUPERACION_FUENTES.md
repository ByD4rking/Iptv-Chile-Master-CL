# FASE 3 — Entrega 4: propuestas de recuperación de fuentes

## Objetivo
Encontrar alternativas en fuentes M3U conocidas para canales con fallos persistentes,
sin reemplazar automáticamente la URL ni retirar el canal.

## Criterios
- Usa el historial de salud por URL y exige por defecto tres fallos consecutivos.
- Prioriza coincidencias únicas por identificadores de canal y proveedor.
- Usa nombre+categoría solo cuando no hay identificadores fuertes y la coincidencia
  es única.
- Descarta candidatos ambiguos y URLs que representan el mismo stream tras ignorar
  tokens de autenticación efímeros.
- Valida la estructura de cada M3U antes de analizarla.
- El informe no expone URLs completas ni tokens; identifica la fuente y el canal
  candidato mediante nombre y fingerprint.

## Uso
\`\`\`bash
python -m scripts.source_recovery \
  --playlist IPTV-CHILE-MAESTRA_CORREGIDO.m3u \
  --health scripts/health/principal_health.json \
  --candidate IPTVSV=fuente_iptvsv.m3u \
  --candidate MAGMA=fuente_magma.m3u \
  --output propuestas_recuperacion.json
\`\`\`

## Seguridad
La herramienta solo propone. No comprueba reproducción del candidato ni lo publica.
Antes de cambiar una URL, la alternativa debe superar una prueba real de reproducción
y una revisión de identidad/categoría. Ninguna modificación automática de listas,
logos, GOD o Generador está habilitada.

# FASE 3 — Entrega 3: diagnóstico de compatibilidad de logos

## Objetivo
Detectar problemas estáticos en las referencias de imagen sin modificar los logos
existentes ni afirmar que una URL se renderiza correctamente en un reproductor.

## Controles
- Referencias vacías por canal.
- URL relativa, esquema no HTTP(S), host ausente o credenciales embebidas.
- HTTP sin cifrar, extensiones desconocidas y SVG que requiere prueba real.
- Diferencias entre \`tvg-logo\` y \`logo\`.
- Referencias repetidas para detectar recursos compartidos.

## Uso
\`\`\`bash
python -m scripts.logo_client_compat --playlist lista.m3u --output logos.json
\`\`\`

## Límite importante
Este análisis no certifica compatibilidad efectiva con Televizo ni SS IPTV. Informa
candidatos y riesgos para validación visual real en ambos clientes. La auditoría
de disponibilidad y firma de imagen existente sigue siendo complementaria.
No reemplaza, elimina ni reescribe logos.

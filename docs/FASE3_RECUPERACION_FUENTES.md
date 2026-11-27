# FASE 3 — Entrega 4: recuperación y prueba de fuentes

## Objetivo
Encontrar alternativas para canales con fallos persistentes, validar su identidad y
probar una muestra real de reproducción antes de considerar cualquier sustitución.

## Criterios
- Usa el historial de salud por URL y exige por defecto tres fallos consecutivos.
- Prioriza coincidencias únicas por identificadores de canal y proveedor.
- Usa nombre+categoría solo cuando no hay identificadores fuertes y la coincidencia
  es única.
- Descarta candidatos ambiguos y URLs que representan el mismo stream tras ignorar
  tokens de autenticación efímeros.
- Valida la estructura de cada M3U antes de analizarla.
- Prueba el manifiesto HLS y solicita una muestra del primer segmento; también admite
  streams directos con una muestra limitada.
- Rechaza respuestas HTML, cuerpos vacíos, hosts no públicos y respuestas excesivas.
- El informe no expone URLs completas ni tokens; identifica la fuente y el canal
  candidato mediante nombre, estado y latencia.

## Uso
```bash
python -m scripts.source_recovery \
  --playlist IPTV-CHILE-MAESTRA_CORREGIDO.m3u \
  --health scripts/health/principal_health.json \
  --candidate IPTVSV=fuente_iptvsv.m3u \
  --candidate MAGMA=fuente_magma.m3u \
  --output propuestas_recuperacion.json

python -m scripts.source_candidate_probe \
  --playlist IPTV-CHILE-MAESTRA_CORREGIDO.m3u \
  --health scripts/health/principal_health.json \
  --candidate-manifest fuentes/manifest.json \
  --output prueba_reproduccion.json
```

## Resultado operativo
En la auditoría de 25-11-2026 se propusieron cuatro alternativas y las cuatro
superaron la prueba de manifiesto/muestra de segmento desde GitHub Actions:
Los Simpson Latino, RPP TV (Perú - Nacional), Comercio TV y KCHTV SD (Guayas)
[Opc.2]. Tres coincidencias son fallback único nombre/categoría y Comercio TV
tiene identidad fuerte. Esto no certifica reproducción continua ni disponibilidad
desde todas las regiones o reproductores.

## Seguridad
Las herramientas solo proponen y prueban. No sustituyen URLs, no modifican M3U y
no retiran canales. Cualquier cambio futuro exige revisión de identidad/categoría
y validación adicional. GOD y Generador permanecen fuera de alcance.

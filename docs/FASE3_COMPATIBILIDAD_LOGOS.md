# FASE 3 — Entrega 3: compatibilidad y validación de logos

## Objetivo
Detectar problemas en las referencias de imagen y comprobar que los recursos
propuestos sean realmente imágenes, sin modificar logos existentes.

## Controles estáticos
- Referencias vacías por canal.
- URL relativa, esquema no HTTP(S), host ausente o credenciales embebidas.
- HTTP sin cifrar, extensiones desconocidas y SVG que requiere prueba real.
- Diferencias entre `tvg-logo` y `logo`.
- Referencias repetidas para detectar recursos compartidos.

## Comprobación del recurso
`scripts.logo_asset_check` descarga únicamente candidatos unívocos para canales
sin logo. Comprueba respuesta HTTP, tamaño máximo, Content-Type y firma binaria
PNG/JPEG/GIF/WebP. Limita la descarga, valida redirecciones a hosts públicos y
no escribe URLs ni tokens en el informe.

```bash
python -m scripts.logo_client_compat --playlist lista.m3u --output logos.json
python -m scripts.logo_asset_check \
  --playlist lista.m3u \
  --candidate-manifest fuentes/manifest.json \
  --output logos_verificados.json
```

## Resultado operativo
De 76 canales sin referencia, el recuperador propuso 52 referencias de logo:
37 con identidad fuerte y 15 por nombre/categoría único. Se encontraron 24 sin
candidato y ninguna propuesta ambigua. Las 52 propuestas representan 47 recursos
únicos; **47/47 recursos descargaron y pasaron la validación de firma** (42 PNG y
5 JPEG). Ningún logo se aplicó a la playlist.

## Límite importante
La descarga y firma válida no certifican renderizado en Televizo ni SS IPTV. Sigue
pendiente la prueba visual en ambos reproductores. No se reemplaza, elimina ni
reescribe ningún logo existente.

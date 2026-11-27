# FASE 3 — Entrega 1: identidad permanente de canales

## Objetivo
Reconocer el mismo canal entre snapshots M3U aunque cambie el nombre, la categoría,
el proveedor o la URL, evitando bajas y altas falsas durante una sincronización.

## Implementación inicial
- Prioriza `tvg-id`, `channel-id`, `provider-channel-id` e identificadores de canal
  extraídos de patrones conocidos de URL.
- Ignora tokens de autenticación efímeros al comparar URLs, para que una renovación
  JWT no se interprete como cambio de stream.
- Usa nombre + categoría únicamente como fallback cuando la coincidencia es única
  en ambos snapshots.
- Si los identificadores son ambiguos, no adivina: informa el caso y conserva la
  distinción entre altas y bajas pendientes de revisión.
- Genera fingerprints de URL; nunca incluye la URL completa ni sus credenciales
  en el informe.
- Solo lectura: no modifica listas, logos, categorías, nombres ni streams.

## Uso
```bash
python -m scripts.channel_identity --before anterior.m3u --after actual.m3u --output identidad.json
```

## Límites de seguridad
Esta entrega es una herramienta de diagnóstico aislada. No se conecta todavía al
publicador ni al sincronizador, y no aplica sustituciones automáticas. La integración
operativa se hará después de validar su comportamiento con snapshots reales y
pruebas de regresión, manteniendo las protecciones de GOD y Generador.

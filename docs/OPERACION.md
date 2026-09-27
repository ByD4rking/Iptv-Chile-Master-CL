# Guía de operación

Esta guía describe las tareas habituales del repositorio sin alterar la ubicación actual de sus listas ni scripts.

## Requisitos

- Python 3.10 o superior recomendado.
- Acceso a Internet para descargar fuentes o verificar streams.
- `pip` para instalar las dependencias de cada componente.

```bash
python -m pip install -r scripts/requirements.txt
python -m pip install -r pluto/requirements.txt
```

## Herramientas de listas M3U

Ejecuta los comandos desde la raíz del repositorio.

| Comando | Propósito | Resultado principal |
| --- | --- | --- |
| `python scripts/actualizar_principal.py` | Actualiza la lista principal con las fuentes configuradas. | `IPTV-CHILE-MAESTRA_CORREGIDO.m3u` |
| `python scripts/mega_lista.py` | Construye la lista ampliada y organizada. | `IPTV-CHILE-MAESTRA_GOD.m3u` |
| `python scripts/generar_reporte.py` | Verifica las listas de la raíz y genera un resumen Markdown. | `REPORTE.md` |
| `python scripts/verificar_m3u.py <lista.m3u>` | Revisa una lista concreta y guarda los canales que fallan. | `canales_caidos.txt` |
| `python scripts/unificar_chile.py` | Ejecuta la utilidad de unificación para la lista de Chile. | Según la configuración del script |

### Opciones útiles de verificación

El verificador permite ajustar el impacto de la comprobación sobre los servidores de origen:

```bash
python scripts/verificar_m3u.py IPTV-CHILE-MAESTRA_CORREGIDO.m3u \
  --hilos 20 \
  --timeout 8 \
  --max-por-servidor 1 \
  --reintentos 1
```

Usa una cantidad moderada de hilos y conserva `--max-por-servidor 1` para no concentrar solicitudes sobre un mismo proveedor.

## Componente Pluto TV

El directorio `pluto/` mantiene su propio conjunto de dependencias y resultados.

```bash
# 1. Descargar y normalizar canales.
python pluto/src/channels.py

# 2. Generar la playlist M3U desde los canales obtenidos.
python pluto/src/playlist.py

# 3. Opcional: iniciar una API local.
python pluto/src/server.py
```

La API local se publica en `http://127.0.0.1:5000/` y expone `/channels`, `/playlist.m3u` y `/stream/<channel_id>`.

## Archivos generados y datos locales

| Ruta | Uso | Versionado |
| --- | --- | --- |
| `REPORTE.md` | Resumen de la última comprobación. | Sí |
| `scripts/aprendizaje.json` | Historial de resultados de verificación. | Sí |
| `pluto/output/channels.json` | Canales normalizados de Pluto. | Sí |
| `pluto/output/playlists/pluto.m3u` | Playlist generada de Pluto. | Sí |
| `pluto/config/client.json` | Datos locales de sesión del cliente. | No; está ignorado por Git. |

## Flujo recomendado para cambios

1. Mantén el cambio enfocado en una sola mejora.
2. Ejecuta la comprobación de sintaxis de los scripts modificados:

   ```bash
   python -m compileall scripts pluto/src
   ```

3. Si modificas un generador, ejecuta únicamente el generador correspondiente y revisa el resultado antes de incluirlo.
4. No subas tokens, sesiones, archivos temporales ni cachés.
5. Describe en el commit qué lista, script o documentación fue modificada.

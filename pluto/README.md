# Pluto TV

Componente para obtener los canales disponibles de Pluto TV, normalizarlos y generar una playlist M3U agrupada por contenido. Se mantiene separado de las listas Master para que pueda actualizarse sin modificar el resto del proyecto.

## Requisitos

Desde la raíz del repositorio:

```bash
python -m pip install -r pluto/requirements.txt
```

## Flujo de generación

```bash
# Obtiene y guarda los canales normalizados.
python pluto/src/channels.py

# Genera la playlist M3U desde los canales descargados.
python pluto/src/playlist.py
```

El resultado queda en:

```text
pluto/output/playlists/pluto.m3u
```

## API local opcional

Algunos enlaces de Pluto requieren una sesión vigente. La API local construye el enlace del canal cuando el reproductor lo solicita.

```bash
python pluto/src/server.py
```

Con el servidor activo, agrega esta URL al reproductor:

```text
http://127.0.0.1:5000/playlist.m3u
```

También están disponibles:

| Ruta | Descripción |
| --- | --- |
| `/` | Estado y rutas disponibles. |
| `/channels` | Canales normalizados en JSON. |
| `/playlist.m3u` | Playlist M3U servida localmente. |
| `/stream/<channel_id>` | Redirección al stream actualizado de un canal. |

> La API escucha únicamente en `127.0.0.1`, por lo que está pensada para usarse desde el mismo equipo donde se ejecuta.

## Archivos principales

| Archivo | Función |
| --- | --- |
| `src/client.py` | Cliente de sesión y construcción de URLs de stream. |
| `src/channels.py` | Descarga, clasifica y guarda canales. |
| `src/playlist.py` | Crea la playlist M3U ordenada por categoría. |
| `src/server.py` | Expone la API local opcional. |
| `output/channels.json` | Datos generados de los canales. |

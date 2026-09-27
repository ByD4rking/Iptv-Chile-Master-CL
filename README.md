# 🇨🇱 IPTV Chile Master

> Listas IPTV M3U organizadas para Chile y Latinoamérica, con herramientas simples para actualizarlas, verificarlas y generar una playlist local de Pluto TV.

[![Formato M3U](https://img.shields.io/badge/formato-M3U-1f6feb?style=flat-square)](#-listas-disponibles)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white)](#-uso-rápido)
[![Licencia](https://img.shields.io/badge/licencia-GPL--3.0-2ea44f?style=flat-square)](LICENSE)

## ✨ Qué incluye

- **Lista Master Original:** base principal del proyecto.
- **Lista Master GOD:** lista ampliada, sin URLs repetidas y agrupada por categorías en español.
- **Pluto TV:** generador de canales y playlist M3U, con una API local opcional.
- **Herramientas de mantenimiento:** actualización, verificación de streams y generación de reportes.

## 📺 Listas disponibles

| Lista | Qué contiene | Enlace directo |
| --- | --- | --- |
| 🇨🇱 **Master Original** | Lista principal mantenida por el proyecto. | [Abrir lista M3U](https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/IPTV-CHILE-MAESTRA_CORREGIDO.m3u) |
| 🔥 **Master GOD** | Canales de fuentes públicas, organizados y sin URLs duplicadas. | [Abrir lista M3U](https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/IPTV-CHILE-MAESTRA_GOD.m3u) |
| 🪐 **Pluto TV** | Playlist generada desde los canales disponibles de Pluto TV. | [Abrir lista M3U](https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto.m3u) |

> Copia cualquiera de los enlaces anteriores en un reproductor compatible con M3U, como VLC, Kodi, TiviMate o IPTV Smarters.

## 🗂️ Categorías de Master GOD

| | | | |
| --- | --- | --- | --- |
| 🇨🇱 Chile | 🌎 Latinoamérica | 🎬 Cine | 📺 Series |
| 🎌 Anime | 🧒 Infantil | 🎵 Música | ⚽ Deportes |
| 📰 Noticias | 🎭 Cultura | 📚 Documentales | 🎓 Educación |
| 🎉 Entretenimiento | 🌍 Países | | |

## 🪐 Pluto TV

El proyecto incluye un componente independiente para generar una lista de Pluto TV en español/Latinoamérica. No reemplaza las listas Master: funciona como una fuente adicional y ordenada por tipo de contenido.

```text
pluto/
├── src/channels.py       # Descarga y normaliza los canales
├── src/playlist.py       # Genera la playlist M3U
├── src/server.py         # API local opcional
└── output/playlists/     # Playlist resultante
```

### Generar la playlist de Pluto

```bash
python -m pip install -r pluto/requirements.txt
python pluto/src/channels.py
python pluto/src/playlist.py
```

La playlist se genera en `pluto/output/playlists/pluto.m3u`. Para usar una URL local que renueva los streams al abrirlos, inicia la API:

```bash
python pluto/src/server.py
```

Luego agrega `http://127.0.0.1:5000/playlist.m3u` a tu reproductor. Consulta la guía específica en [pluto/README.md](pluto/README.md).

## 🛠️ Uso rápido

### Instalación

```bash
git clone https://github.com/ByD4rking/Iptv-Chile-Master-CL.git
cd Iptv-Chile-Master-CL
python -m pip install -r scripts/requirements.txt
```

### Mantenimiento de listas

```bash
# Actualiza la lista principal desde las fuentes configuradas.
python scripts/actualizar_principal.py

# Genera la lista Master GOD.
python scripts/mega_lista.py

# Revisa disponibilidad y actualiza REPORTE.md.
python scripts/generar_reporte.py
```

En Windows, `actualizar-todo.ps1` reúne el flujo de actualización configurado para el proyecto.

## 📁 Estructura del repositorio

```text
.
├── IPTV-CHILE-MAESTRA_CORREGIDO.m3u  # Lista principal
├── IPTV-CHILE-MAESTRA_GOD.m3u        # Lista ampliada
├── pluto/                            # Generador y API local de Pluto TV
├── scripts/                          # Automatización y verificación M3U
├── docs/                             # Guías de operación
├── REPORTE.md                        # Último reporte de disponibilidad
└── actualizar-todo.ps1               # Actualización en Windows
```

Para ver todos los comandos, resultados generados y recomendaciones de mantenimiento, revisa la [guía de operación](docs/OPERACION.md).

## ⚠️ Uso responsable

- La disponibilidad de los streams puede cambiar, fallar temporalmente o estar limitada por región.
- Las transmisiones, marcas, logos y contenidos pertenecen a sus respectivos titulares.
- El repositorio no reclama propiedad sobre contenido de terceros ni garantiza la disponibilidad de las URLs.
- Respeta los derechos de autor, las condiciones de uso y las restricciones geográficas de cada fuente.

## 🤝 Contribuciones

Las mejoras pequeñas, claras y verificables son bienvenidas. Evita subir datos de sesión, tokens, cachés o archivos temporales, y comprueba los scripts modificados antes de enviar un cambio.

## 📄 Licencia

Este proyecto se distribuye bajo la [licencia incluida en el repositorio](LICENSE).

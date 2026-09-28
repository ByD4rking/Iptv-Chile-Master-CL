# 🇨🇱 IPTV Chile Master

> **Colección, organización y actualización automatizada de listas IPTV en formato M3U.**

IPTV Chile Master reúne y organiza diferentes fuentes IPTV públicas en playlists pensadas para un uso sencillo en reproductores compatibles con **M3U/M3U8**.

El proyecto mantiene una **lista principal**, una versión ampliada **GOD** y un conjunto de playlists **Pluto TV** independientes.

---

## 📺 1. Lista principal — IPTV Chile Master

La lista principal es la **playlist maestra del proyecto**.

Su estructura se mantiene organizada por categorías y prioriza la conservación de la distribución existente, evitando duplicar URLs de acceso y procurando mantener separadas las categorías específicas cuando corresponde.

### 🔗 RAW — Lista principal

**IPTV-CHILE-MAESTRA_CORREGIDO.m3u**

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/IPTV-CHILE-MAESTRA_CORREGIDO.m3u
~~~

### 📌 Características

- 🇨🇱 Chile como sección principal.
- 📺 Organización por categorías.
- ⚽ Categorías deportivas específicas.
- 🎬 Cine y series.
- 🎌 Anime.
- 🧒 Infantiles.
- 📰 Noticias e informativos.
- 🎵 Música.
- 🌎 Categorías por países.
- 🔞 Contenido adulto en su sección correspondiente.
- 🔗 Control de URLs duplicadas.
- 🧩 Conservación de categorías de origen cuando corresponde.
- 🔄 Actualización y revisión mediante automatizaciones del repositorio.

> **Recomendación:** si buscas la estructura principal y más controlada del proyecto, utiliza esta lista.

---

## 🔥 2. Lista GOD — IPTV Chile Master GOD

La **GOD** es una versión ampliada construida a partir de múltiples fuentes IPTV públicas.

Su objetivo es ofrecer una colección mucho más extensa, manteniendo una organización por categorías y eliminando URLs duplicadas durante el proceso de generación.

### 🔗 RAW — Lista GOD

**IPTV-CHILE-MAESTRA_GOD.m3u**

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/IPTV-CHILE-MAESTRA_GOD.m3u
~~~

### 📌 Características

- 📚 Mayor cantidad de contenido y fuentes.
- 🔗 Eliminación de URLs duplicadas.
- 🗂️ Organización automática de categorías.
- 🌎 Contenido internacional.
- 🇨🇱 Secciones específicas para Chile.
- ⚽ Deportes.
- 🎬 Cine y series.
- 🎌 Anime.
- 🧒 Infantil.
- 🎵 Música.
- 📰 Noticias.
- 🌍 Países y contenido internacional.

> **Diferencia principal:** la lista principal prioriza una estructura maestra controlada; la GOD está orientada a una colección más amplia de fuentes y canales.

---

# 🪐 3. Pluto TV

El proyecto también mantiene playlists específicas de **Pluto TV**, generadas y actualizadas dentro del repositorio.

Actualmente se publican **tres playlists oficiales**:

| Región | Playlist | RAW |
| :--- | :--- | :--- |
| 🌎 **Pluto TV LATAM** | Latinoamérica | [RAW M3U](https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_latam.m3u) |
| 🇪🇸 **Pluto TV España** | España | [RAW M3U](https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_es.m3u) |
| 🇲🇽 **Pluto TV México** | México | [RAW M3U](https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_mx.m3u) |

### 🔗 Enlaces directos

#### 🌎 Pluto TV LATAM

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_latam.m3u
~~~

Playlist orientada al contenido disponible para **Latinoamérica**.

#### 🇪🇸 Pluto TV España

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_es.m3u
~~~

Playlist específica para el catálogo de **España**.

#### 🇲🇽 Pluto TV México

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_mx.m3u
~~~

Playlist específica para el catálogo de **México**.

### 🧭 Prioridad de integración Pluto

Cuando un canal está disponible en más de una región, el proyecto utiliza una prioridad de integración para reducir duplicados:

**LATAM → España → México**

Esto permite aprovechar primero la versión LATAM cuando existe y utilizar las versiones regionales únicamente cuando aportan contenido que no está disponible en la anterior.

> Las playlists regionales de Pluto son independientes de la lista principal y de la lista GOD.

---

## ▶️ Cómo utilizar las listas

Puedes utilizar cualquiera de las URLs RAW anteriores en un reproductor compatible con listas IPTV mediante URL.

Algunos reproductores compatibles con M3U/M3U8 incluyen:

- 📺 TiviMate
- 📺 OTT Navigator
- ▶️ VLC
- 📱 Otros reproductores IPTV compatibles con URL M3U

### Pasos

1. Copia la URL **RAW** de la playlist que quieras utilizar.
2. Abre tu reproductor IPTV.
3. Selecciona la opción para añadir una lista mediante URL.
4. Pega la URL.
5. Guarda y actualiza la playlist.

---

## 🤖 Actualización y mantenimiento

El repositorio utiliza procesos automatizados para mantener y revisar las playlists.

Entre las tareas de mantenimiento se incluyen:

- 🔄 Actualización de fuentes.
- 🧹 Detección y eliminación de URLs duplicadas cuando corresponde.
- 🗂️ Organización de categorías.
- 🔎 Auditorías de integridad.
- 🛡️ Protección de categorías establecidas.
- 📊 Generación de reportes.
- 🪐 Actualización de las playlists Pluto TV.
- ✅ Verificaciones antes de publicar cambios.

La automatización busca **actualizar sin destruir la estructura existente**: los cambios deben ser controlados y las categorías establecidas no deben reorganizarse arbitrariamente.

---

## 🗂️ Estructura del proyecto

La organización principal del repositorio incluye:

~~~
IPTV-CHILE-MASTER-CL/
├── IPTV-CHILE-MAESTRA_CORREGIDO.m3u
├── IPTV-CHILE-MAESTRA_GOD.m3u
├── REPORTE.md
├── actualizar-todo.ps1
├── pluto/
│   └── output/
│       └── playlists/
│           ├── pluto_latam.m3u
│           ├── pluto_es.m3u
│           └── pluto_mx.m3u
└── scripts/
~~~

---

## ⚠️ Aviso importante

Este proyecto recopila y organiza **fuentes IPTV públicas de terceros**.

- La disponibilidad de los streams puede cambiar en cualquier momento.
- Un canal puede dejar de funcionar, cambiar de URL o desaparecer de una fuente.
- Los nombres, marcas, logos, programas y contenidos pertenecen a sus respectivos titulares.
- IPTV Chile Master no reclama propiedad sobre contenido perteneciente a terceros.
- El usuario es responsable de utilizar las listas de acuerdo con la legislación aplicable en su jurisdicción.

---

## 📜 Licencia

Consulta el archivo [LICENSE](LICENSE) del repositorio para conocer las condiciones aplicables al código y a los archivos del proyecto.

---

## 🇨🇱 IPTV Chile Master

**Una colección IPTV organizada, automatizada y en constante mantenimiento.**

*Principal · GOD · Pluto TV · M3U*

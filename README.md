# 🇨🇱 IPTV Chile Master

> **Colección, organización y actualización automatizada de listas IPTV en formato M3U.**

IPTV Chile Master reúne y organiza diferentes fuentes IPTV públicas en playlists pensadas para un uso sencillo en reproductores compatibles con **M3U/M3U8**.

El proyecto mantiene una **lista principal**, una versión ampliada **GOD** y un conjunto de playlists **Pluto TV independientes**.

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

El proyecto mantiene **tres playlists Pluto TV independientes**, cada una publicada como su propio archivo M3U.

### 🌎🇪🇸🇲🇽 Las tres listas son independientes

Puedes utilizar **una sola**, **dos** o **las tres** según lo que necesites. No es obligatorio cargarlas juntas.

La organización conjunta que utiliza el proyecto es únicamente una **regla interna de integración y mantenimiento** para evitar duplicados y aprovechar primero el contenido de LATAM cuando está disponible.

**Prioridad interna de integración:**

**LATAM → España → México**

Esto significa que, cuando un mismo canal aparece en varias regiones, el proyecto prioriza la versión LATAM y utiliza España o México cuando aportan contenido que no está disponible en una región anterior.

> **Importante:** esta prioridad no limita al usuario. Cada playlist Pluto puede utilizarse por separado y directamente mediante su URL RAW.

### 📋 Playlists oficiales

| Región | Archivo | Uso |
| :--- | :--- | :--- |
| 🌎 **Pluto TV LATAM** | `pluto_latam.m3u` | Contenido orientado a Latinoamérica |
| 🇪🇸 **Pluto TV España** | `pluto_es.m3u` | Contenido específico de España |
| 🇲🇽 **Pluto TV México** | `pluto_mx.m3u` | Contenido específico de México |

### 🔗 RAW — Pluto TV LATAM

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_latam.m3u
~~~

### 🔗 RAW — Pluto TV España

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_es.m3u
~~~

### 🔗 RAW — Pluto TV México

~~~
https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/main/pluto/output/playlists/pluto_mx.m3u
~~~

### 🧩 ¿Cómo elegir?

- **Solo quieres contenido latinoamericano:** utiliza **Pluto TV LATAM**.
- **Quieres específicamente contenido de España:** utiliza **Pluto TV España**.
- **Quieres específicamente contenido de México:** utiliza **Pluto TV México**.
- **Quieres ampliar la cobertura:** puedes cargar las tres listas en un reproductor que admita múltiples playlists.
- **Quieres evitar administrar varias listas:** puedes utilizar la lista principal o GOD del proyecto cuando corresponda.

> Pluto TV se mantiene como un bloque separado de la lista principal y de la GOD. Las tres playlists regionales conservan su identidad y pueden utilizarse libremente de forma individual.

---

## ▶️ 4. Reproductores compatibles

Las listas del proyecto son archivos **M3U/M3U8** y pueden utilizarse con distintos reproductores. La disponibilidad exacta puede variar según el modelo de TV, sistema operativo y tienda de aplicaciones.

### 📺 Reproductores para Smart TV

#### ⭐ SS IPTV — opción gratuita

**SS IPTV (Simple Smart IPTV)** es un reproductor gratuito para Smart TV que permite cargar playlists propias y reproducir contenido mediante Internet. Su documentación oficial contempla Smart TV de **LG, Samsung, Philips y Sony**, con diferencias de instalación según modelo y plataforma. citeturn1search0turn1search1turn1search4

- Compatible con playlists propias.
- Orientado especialmente a Smart TV.
- Permite cargar listas externas.
- No proporciona canales propios: debes añadir tu propia playlist.
- Es gratuito según la documentación oficial de SS IPTV. citeturn1search4

🔗 **Sitio oficial:** https://www.ss-iptv.com/

#### ▶️ VLC

VLC también puede utilizarse para abrir listas M3U/M3U8 y reproducir sus streams. Es una alternativa multiplataforma especialmente útil cuando el dispositivo permite instalar VLC.

---

### 🤖 Reproductores para Android / Android TV

#### ⭐ Televizo IPTV Player

Televizo permite utilizar **múltiples playlists M3U**, EPG, favoritos, búsqueda, Chromecast y selección de pistas de audio/subtítulos. Está disponible para teléfonos, tablets y televisores compatibles. citeturn0search1turn0search7

🔗 **Google Play:** https://play.google.com/store/apps/details?id=com.ottplay.ottplay

#### ⭐ TiviMate IPTV Player

TiviMate está diseñado especialmente para **Android TV** y navegación con control remoto. Admite M3U, Xtream Codes y Stalker Portal, además de múltiples listas, EPG, favoritos, búsqueda, catch-up, grabación y multivista. La aplicación ofrece funciones gratuitas y otras mediante compras dentro de la aplicación. citeturn0search2turn0search3

🔗 **Google Play:** https://play.google.com/store/apps/details?id=ar.tvplayer.tv

🔗 **Sitio oficial:** https://tivimate.com/

#### ⭐ OTT Navigator IPTV

OTT Navigator admite listas **M3U/M3U8**, múltiples listas, EPG, favoritos, búsqueda, Xtream Codes y reproducción adaptativa. Está disponible para Android y es una alternativa flexible para quienes manejan varias playlists. citeturn0search0turn0search5

🔗 **Google Play:** https://play.google.com/store/apps/details?id=com.ottnavigator.iptvnavigator

> **Nota:** estos reproductores no proporcionan las listas ni los canales del proyecto. Son herramientas para cargar y reproducir tus propias playlists.

### 🧭 Elección rápida

| Dispositivo | Opciones recomendadas |
| :--- | :--- |
| 📺 Smart TV LG / Samsung | **SS IPTV** |
| 📺 Smart TV compatible con VLC | **VLC** |
| 🤖 Android TV | **TiviMate / Televizo / OTT Navigator** |
| 📱 Android | **Televizo / OTT Navigator** |
| 💻 PC | **VLC** |

---

## 🛠️ Cómo utilizar las listas

1. Copia la URL **RAW** de la playlist que quieras utilizar.
2. Abre el reproductor IPTV de tu dispositivo.
3. Selecciona la opción para añadir una lista mediante URL.
4. Pega la URL.
5. Guarda la playlist.
6. Actualiza la lista cuando necesites obtener los cambios más recientes.

---

## 🤖 5. Actualización y mantenimiento

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

## 🗂️ 6. Estructura del proyecto

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

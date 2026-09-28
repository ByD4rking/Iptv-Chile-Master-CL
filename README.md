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

## ▶️ 4. Reproductores recomendados

Las listas del proyecto son archivos **M3U/M3U8** y pueden utilizarse en distintos dispositivos. La disponibilidad de cada aplicación puede variar según el sistema operativo, modelo de equipo y tienda de aplicaciones.

### 📱 Android — recomendación principal

#### ⭐ Televizo + MPV

**Televizo** como gestor/reproductor IPTV y **MPV** como reproductor externo forman una combinación muy útil cuando se busca una reproducción más flexible.

- Televizo permite gestionar playlists M3U y organizar el contenido.
- MPV puede utilizarse como reproductor externo para los streams.
- Si un canal presenta pantalla negra, cortes o problemas de decodificación en el reproductor integrado, probar **MPV** como reproductor externo puede ayudar.

### 💻 PC

#### ⭐ FredTV

**FredTV** es una opción orientada a la reproducción de listas IPTV en PC.

#### ▶️ MPV Player

**MPV** es una alternativa ligera y flexible para reproducir streams y archivos multimedia.

#### ▶️ IPTVnator

**IPTVnator** está orientado específicamente a listas IPTV y puede utilizarse para gestionar y reproducir playlists M3U/M3U8.

### 🍏 macOS

#### ⭐ IPTVnator

**IPTVnator** es una alternativa recomendada para macOS cuando se quiere trabajar directamente con playlists IPTV.

También puede utilizarse **MPV** o **VLC** como reproductor externo cuando sea necesario.

### 📱 iPhone / iPad

#### ⭐ GSE Smart IPTV + VLC

**GSE Smart IPTV** puede utilizarse para gestionar listas IPTV, mientras que **VLC** puede emplearse como reproductor externo cuando sea compatible con el flujo.

### 📺 Smart TV

#### 🤖 Android TV

**Televizo** es una de las opciones disponibles para Android TV y permite trabajar con playlists IPTV.

También puedes utilizar **TiviMate** u **OTT Navigator IPTV** si prefieres una interfaz orientada específicamente a televisión y control remoto.

#### 📺 Samsung, LG y otras Smart TV

**SS IPTV** es una opción gratuita para Smart TV que permite cargar playlists propias.

También puede utilizarse **IPTV Smarters Pro** en los dispositivos y versiones donde esté disponible, cargando manualmente la playlist M3U.

> **Importante:** la disponibilidad de una aplicación depende del modelo de TV, sistema operativo, región y tienda de aplicaciones. Si una aplicación no aparece en la tienda de tu televisor, utiliza una alternativa compatible con ese dispositivo.

### 🧭 Resumen por dispositivo

| Dispositivo | Opciones recomendadas |
| :--- | :--- |
| 📱 **Android** | **Televizo + MPV** |
| 🤖 **Android TV** | **Televizo / TiviMate / OTT Navigator** |
| 💻 **Windows / PC** | **FredTV / MPV / IPTVnator** |
| 🍏 **macOS** | **IPTVnator / MPV / VLC** |
| 📱 **iPhone / iPad** | **GSE Smart IPTV + VLC** |
| 📺 **Samsung / LG / Smart TV** | **SS IPTV / IPTV Smarters Pro** |

### 🛠️ Solución para pantalla negra, cortes o reproducción poco fluida

Si un canal funciona pero presenta **pantalla negra, cortes, congelamientos o reproducción poco fluida**, prueba primero un reproductor externo:

1. En Android, prueba **MPV** como reproductor externo desde Televizo.
2. Si MPV no está disponible, prueba **VLC**.
3. Comprueba nuevamente el mismo canal.
4. Si continúa sin funcionar, el problema puede estar en el propio stream, su servidor o su compatibilidad con el dispositivo.

> 💡 **Tip importante:** utilizar un reproductor externo no garantiza que un canal vaya a funcionar. Si el stream está caído, bloqueado o es incompatible, ningún reproductor podrá solucionarlo.

### ⚙️ Ajustes recomendados

Para problemas de compatibilidad de vídeo, puedes probar:

- **MPV:** revisar la configuración de decodificación y probar decodificación por software cuando la aceleración por hardware provoque incompatibilidades.
- **VLC:** revisar la configuración de decodificación de vídeo y probar decodificación por software si aparecen errores de imagen.
- Mantener actualizados el reproductor y el sistema operativo.
- Probar otro reproductor antes de descartar una URL.
- Comparar el mismo canal con otra URL de la playlist cuando exista una alternativa.

> **Nota:** la decodificación por software puede aumentar el uso de CPU. En equipos con recursos limitados, puede ser preferible mantener la aceleración por hardware si funciona correctamente.

> **Importante:** estos reproductores **no proporcionan los canales ni las listas del proyecto**. Son herramientas para cargar y reproducir tus propias playlists.

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

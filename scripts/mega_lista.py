# IPTV Chile Master
# Copyright (C) 2026 ByD4rk
#
# Este programa está basado/modificado a partir de software
# distribuido bajo la GNU General Public License v3.0.
#
# Este programa es software libre: puedes redistribuirlo y/o
# modificarlo bajo los términos de la GNU General Public License
# publicada por la Free Software Foundation, versión 3 o posterior.
#
# Este programa se distribuye con la esperanza de que sea útil,
# pero SIN NINGUNA GARANTÍA.
#
# GNU GPL v3.0:
# https://www.gnu.org/licenses/gpl-3.0.html

import re
import unicodedata
from pathlib import Path

import requests


# ============================================================
# RUTAS
# ============================================================

BASE = Path(__file__).resolve().parent.parent

PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
SALIDA = BASE / "IPTV-CHILE-MAESTRA_GOD.m3u"


# ============================================================
# FUENTES EXTERNAS
# ============================================================

FUENTES = [

    # --------------------------------------------------------
    # FUENTES IPTV-ORG
    # --------------------------------------------------------

    "https://iptv-org.github.io/iptv/countries/mx.m3u",
    "https://iptv-org.github.io/iptv/index.m3u",
    "https://iptv-org.github.io/iptv/countries/cl.m3u",
    "https://iptv-org.github.io/iptv/regions/latam.m3u",
    "https://iptv-org.github.io/iptv/regions/hispam.m3u",
    "https://iptv-org.github.io/iptv/regions/lac.m3u",
    "https://iptv-org.github.io/iptv/regions/southam.m3u",

    # --------------------------------------------------------
    # OTRAS FUENTES
    # --------------------------------------------------------

    "https://dearbulut.github.io/iptv/playlists/best.m3u",

    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/IPTVSV.m3u",

    "https://dearbulut.github.io/iptv/playlists/language/spa.m3u",

    "https://iptv-org.github.io/iptv/countries/us.m3u",

    "https://iptv-org.github.io/iptv/index.country.m3u",

    "https://dearbulut.github.io/iptv/playlists/online.m3u",

    "https://raw.githubusercontent.com/freecasthub/public-iptv/main/playlist.m3u",

    "https://iptv-org.github.io/iptv/regions/amer.m3u",

    "https://iptv-org.github.io/iptv/languages/spa.m3u",

    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",

    "https://iptv-org.github.io/iptv/index.category.m3u",

    "https://iptv-org.github.io/iptv/categories/sports.m3u",

    "https://iptv-org.github.io/iptv/categories/series.m3u",

    # --------------------------------------------------------
    # M3U.CL
    # --------------------------------------------------------

    "https://m3u.cl/lista/XXX.m3u",
    "https://m3u.cl/lista/religiosos.m3u",
    "https://m3u.cl/lista/musica.m3u",
    "https://m3u.cl/lista/LATAM.m3u",
    "https://m3u.cl/lista/VE.m3u",
    "https://m3u.cl/lista/DO.m3u",
    "https://m3u.cl/lista/PE.m3u",
    "https://m3u.cl/lista/PY.m3u",
    "https://m3u.cl/lista/MX.m3u",
    "https://m3u.cl/lista/ES.m3u",
    "https://m3u.cl/lista/EC.m3u",
    "https://m3u.cl/lista/CR.m3u",
    "https://m3u.cl/lista/CO.m3u",
    "https://m3u.cl/lista/CL.m3u",
    "https://m3u.cl/lista/BR.m3u",
    "https://m3u.cl/lista/BO.m3u",
    "https://m3u.cl/lista/AR.m3u",

    # --------------------------------------------------------
    # TOTAL Y TOP
    # --------------------------------------------------------

    "https://m3u.cl/lista/total.m3u",
    "https://m3u.cl/lista/top.m3u",

    # --------------------------------------------------------
    # PLUTO TV
    # --------------------------------------------------------

    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.ES.m3u",
    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u",
]


# ============================================================
# UTILIDADES
# ============================================================

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        c
        for c in texto
        if not unicodedata.combining(c)
    )

    return texto.lower().strip()


def contiene(texto, palabras):
    return any(
        palabra in texto
        for palabra in palabras
    )


# ============================================================
# CLASIFICADOR
# ============================================================

def clasificar(grupo, nombre):

    g = normalizar(grupo)
    n = normalizar(nombre)

    texto = f"{g} {n}"

    # --------------------------------------------------------
    # ADULTOS
    # --------------------------------------------------------

    indicadores_adultos = [
        "pornografia",
        "pornographic",
        "porn",
        "xxx",
        "sex channel",
        "sexo explicito",
        "explicit sex",
        "adult only",
        "adultos",
        "adult channel",
        "adult tv",
        "erotic tv",
        "erotica",
        "erotic",
    ]

    if re.search(
        r"(^|[\s:_-])18\+($|[\s:_-])",
        texto
    ):
        return "ADULTOS"

    if contiene(texto, indicadores_adultos):
        return "ADULTOS"

    # --------------------------------------------------------
    # ANIME
    # --------------------------------------------------------

    if contiene(texto, [
        "anime",
        "anime:",
        "japanese anime",
        "animacion japonesa",
        "otaku",
    ]):
        return "ANIME"

    # --------------------------------------------------------
    # INFANTIL
    # --------------------------------------------------------

    if contiene(texto, [
        "kids",
        "kid:",
        "children",
        "child:",
        "cartoon",
        "cartoons",
        "infantil",
        "ninos",
        "nina",
        "junior",
        "toons",
        "preschool",
        "preescolar",
    ]):
        return "INFANTIL"

    # --------------------------------------------------------
    # DEPORTES
    # --------------------------------------------------------

    if contiene(texto, [
        "sports",
        "sport:",
        "sport ",
        "deportes",
        "deporte",
        "football",
        "soccer",
        "futbol",
        "basketball",
        "basket",
        "nba",
        "tennis",
        "tenis",
        "baseball",
        "beisbol",
        "formula 1",
        "motorsport",
        "rugby",
        "boxing",
        "boxeo",
        "golf",
    ]):
        return "DEPORTES"

    # --------------------------------------------------------
    # NOTICIAS
    # --------------------------------------------------------

    if contiene(texto, [
        "news",
        "news:",
        "noticias",
        "noticia",
        "breaking news",
        "current affairs",
        "actualidad",
    ]):
        return "NOTICIAS"

    # --------------------------------------------------------
    # MÚSICA
    # --------------------------------------------------------

    if contiene(texto, [
        "music",
        "music:",
        "musica",
        "musical",
        "musique",
        "musica tv",
    ]):
        return "MÚSICA"

    # --------------------------------------------------------
    # CINE
    # --------------------------------------------------------

    if contiene(texto, [
        "movie",
        "movies",
        "movie:",
        "pelicula",
        "peliculas",
        "cine",
        "cinema",
        "film",
        "films",
    ]):
        return "CINE"

    # --------------------------------------------------------
    # SERIES
    # --------------------------------------------------------

    if contiene(texto, [
        "series",
        "series:",
        "serie",
        "tv series",
        "shows",
        "television series",
    ]):
        return "SERIES"

    # --------------------------------------------------------
    # DOCUMENTALES
    # --------------------------------------------------------

    if contiene(texto, [
        "documentary",
        "documentaries",
        "documentary:",
        "documental",
        "documentales",
    ]):
        return "DOCUMENTALES"

    # --------------------------------------------------------
    # CULTURA
    # --------------------------------------------------------

    if contiene(texto, [
        "culture",
        "culture:",
        "cultura",
        "arts",
        "art:",
        "arte",
        "history",
        "historia",
        "literature",
        "literatura",
        "books",
        "libros",
    ]):
        return "CULTURA"

    # --------------------------------------------------------
    # EDUCACIÓN
    # --------------------------------------------------------

    if contiene(texto, [
        "education",
        "educational",
        "educacion",
        "educativo",
        "school",
        "universidad",
        "university",
        "learning",
    ]):
        return "EDUCACIÓN"

    # --------------------------------------------------------
    # TECNOLOGÍA
    # --------------------------------------------------------

    if contiene(texto, [
        "technology",
        "tech",
        "tecnologia",
        "science",
        "ciencia",
        "computer",
        "computers",
    ]):
        return "TECNOLOGÍA"

    # --------------------------------------------------------
    # RELIGIÓN
    # --------------------------------------------------------

    if contiene(texto, [
        "religion",
        "religion:",
        "religiosa",
        "religioso",
        "cristian",
        "christian",
        "church",
        "iglesia",
        "gospel",
        "evangel",
    ]):
        return "RELIGIÓN"

    # --------------------------------------------------------
    # COCINA
    # --------------------------------------------------------

    if contiene(texto, [
        "cooking",
        "cook",
        "cocina",
        "culinaria",
        "food",
        "gastronomia",
        "gastronomy",
    ]):
        return "COCINA"

    # --------------------------------------------------------
    # ESTILO DE VIDA
    # --------------------------------------------------------

    if contiene(texto, [
        "lifestyle",
        "life style",
        "estilo de vida",
        "travel",
        "viajes",
        "viaje",
        "home",
        "hogar",
        "health",
        "salud",
    ]):
        return "ESTILO DE VIDA"

    # --------------------------------------------------------
    # ENTRETENIMIENTO
    # --------------------------------------------------------

    if contiene(texto, [
        "entertainment",
        "entretenimiento",
        "variety",
        "variedades",
        "reality",
        "talk show",
        "talkshow",
        "showbiz",
    ]):
        return "ENTRETENIMIENTO"

    # --------------------------------------------------------
    # PAÍSES
    # --------------------------------------------------------

    paises = [
        (["chile", " ch ", ":ch", "cl:"], "CHILE"),
        (["mexico", "méxico", " mexico:"], "MÉXICO"),
        (["argentina"], "ARGENTINA"),
        (["peru", "perú"], "PERÚ"),
        (["colombia"], "COLOMBIA"),
        (["ecuador"], "ECUADOR"),
        (["bolivia"], "BOLIVIA"),
        (["venezuela"], "VENEZUELA"),
        (["uruguay"], "URUGUAY"),
        (["paraguay"], "PARAGUAY"),
        (["brasil", "brazil"], "BRASIL"),
        (["espana", "españa", "spain"], "ESPAÑA"),
        (
            ["estados unidos", "united states", "usa"],
            "ESTADOS UNIDOS",
        ),
        (["canada", "canadá"], "CANADÁ"),
        (["francia", "france"], "FRANCIA"),
        (["italia", "italy"], "ITALIA"),
        (["alemania", "germany"], "ALEMANIA"),
        (["portugal"], "PORTUGAL"),
        (["japon", "japón", "japan"], "JAPÓN"),
        (["corea", "korea"], "COREA"),
    ]

    for palabras, resultado in paises:
        if contiene(texto, palabras):
            return resultado

    # --------------------------------------------------------
    # REGIONES
    # --------------------------------------------------------

    if contiene(texto, [
        "latam",
        "latin america",
        "latinoamerica",
        "latinoamérica",
        "south america",
        "sudamerica",
        "sudamérica",
    ]):
        return "LATINOAMÉRICA"

    if contiene(texto, [
        "international",
        "internacional",
        "world",
        "worldwide",
        "global",
    ]):
        return "INTERNACIONAL"

    return "OTROS"


# ============================================================
# DESCARGAR
# ============================================================

def descargar(url):

    print("-" * 60)
    print(f"Descargando:")
    print(url)

    try:

        respuesta = requests.get(
            url,
            timeout=90,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
        )

        respuesta.raise_for_status()

        texto = respuesta.text

        if "#EXTINF" not in texto:

            print(
                "  -> La fuente no contiene #EXTINF."
            )

            return []

        return texto.splitlines()

    except Exception as error:

        print(
            f"  -> ERROR: {error}"
        )

        return []


# ============================================================
# PROCESAR CANALES
# ============================================================

def procesar(lineas, vistos):

    resultado = []

    i = 0

    while i < len(lineas):

        linea = lineas[i].strip()

        if not linea.startswith("#EXTINF"):
            i += 1
            continue

        info = linea

        j = i + 1

        while (
            j < len(lineas)
            and not lineas[j].strip()
        ):
            j += 1

        if j >= len(lineas):
            break

        url = lineas[j].strip()

        if not url.startswith(
            ("http://", "https://")
        ):
            i = j + 1
            continue

        # ----------------------------------------------------
        # SIN URL DUPLICADAS
        # ----------------------------------------------------

        if url in vistos:
            i = j + 1
            continue

        vistos.add(url)

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        if "," in info:
            nombre = info.split(
                ",",
                1
            )[1].strip()
        else:
            nombre = "Canal"

        # ----------------------------------------------------
        # GROUP TITLE ORIGINAL
        # ----------------------------------------------------

        match = re.search(
            r'group-title="([^"]*)"',
            info,
            re.IGNORECASE
        )

        if match:
            grupo = match.group(1)
        else:
            grupo = ""

        # ----------------------------------------------------
        # CLASIFICAR
        # ----------------------------------------------------

        nuevo_grupo = clasificar(
            grupo,
            nombre
        )

        # ----------------------------------------------------
        # CAMBIAR GROUP TITLE
        # ----------------------------------------------------

        if re.search(
            r'group-title="',
            info,
            re.IGNORECASE
        ):

            info = re.sub(
                r'group-title="[^"]*"',
                f'group-title="{nuevo_grupo}"',
                info,
                count=1,
                flags=re.IGNORECASE,
            )

        else:

            info = info.replace(
                ",",
                f' group-title="{nuevo_grupo}",',
                1,
            )

        resultado.append(info)
        resultado.append(url)

        i = j + 1

    return resultado


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("       IPTV CHILE MASTER - GOD BUILDER V4")
    print("=" * 70)

    # --------------------------------------------------------
    # COMPROBAR PRINCIPAL
    # --------------------------------------------------------

    if not PRINCIPAL.exists():

        raise FileNotFoundError(
            f"No existe la lista principal:\n{PRINCIPAL}"
        )

    vistos = set()

    final = ["#EXTM3U"]

    # ========================================================
    # LISTA PRINCIPAL
    # ========================================================

    print(
        "\n[1/2] Procesando lista principal..."
    )

    principal = PRINCIPAL.read_text(
        encoding="utf-8",
        errors="ignore",
    ).splitlines()

    datos = procesar(
        principal,
        vistos,
    )

    final.extend(datos)

    print(
        f"Canales iniciales únicos: "
        f"{len(vistos)}"
    )

    # ========================================================
    # FUENTES EXTERNAS
    # ========================================================

    print(
        "\n[2/2] Procesando fuentes externas..."
    )

    for numero, fuente in enumerate(
        FUENTES,
        1,
    ):

        print()
        print(
            f"[FUENTE {numero}/{len(FUENTES)}]"
        )

        lineas = descargar(fuente)

        if not lineas:
            print(
                "  -> Fuente omitida."
            )
            continue

        antes = len(vistos)

        datos = procesar(
            lineas,
            vistos,
        )

        final.extend(datos)

        nuevos = len(vistos) - antes

        print(
            f"  -> Canales nuevos agregados: {nuevos}"
        )

    # ========================================================
    # GUARDAR
    # ========================================================

    SALIDA.write_text(
        "\n".join(final) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("       LISTA GOD V4 TERMINADA")
    print("=" * 70)

    print(
        f"Canales únicos totales: {len(vistos)}"
    )

    print(
        f"Archivo generado:\n{SALIDA}"
    )

    print(
        f"Tamaño: "
        f"{SALIDA.stat().st_size / 1024 / 1024:.2f} MB"
    )

    print()
    print(
        "Regla aplicada: una URL = un canal."
    )

    print(
        "Las fuentes externas solo agregan "
        "URLs que todavía no existen."
    )

    print()
    print(
        "Proceso terminado correctamente."
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
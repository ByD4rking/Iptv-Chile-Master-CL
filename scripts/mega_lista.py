# IPTV Chile Master
# Copyright (C) 2026 ByD4rk
#
# Este programa estÃ¡ basado/modificado a partir de software
# distribuido bajo la GNU General Public License v3.0.
#
# Este programa es software libre: puedes redistribuirlo y/o
# modificarlo bajo los tÃ©rminos de la GNU General Public License
# publicada por la Free Software Foundation, versiÃ³n 3 o posterior.
#
# Este programa se distribuye con la esperanza de que sea Ãºtil,
# pero SIN NINGUNA GARANTÃA.
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
    # IPTV-ORG
    # --------------------------------------------------------


    "https://iptv-org.github.io/iptv/index.m3u",
   

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
    # TOTAL / TOP
    # --------------------------------------------------------

    "https://m3u.cl/lista/total.m3u",
    "https://m3u.cl/lista/top.m3u",

    # --------------------------------------------------------
    # PLUTO TV — SOLO LAS FUENTES ACTIVAS DEL PROYECTO
    #
    # LATAM es la fuente prioritaria y ES/MX solo complementan.
    # Las listas regionales eliminadas NO se vuelven a consultar.
    # --------------------------------------------------------

    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_all.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_us.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_br.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_ar.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_cl.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_es.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_mx.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_latam.m3u",
]


# ============================================================
# MAPAS
# ============================================================

PAISES = {
    "ve": "VENEZUELA",
    "do": "REPÃšBLICA DOMINICANA",
    "pe": "PERÃš",
    "py": "PARAGUAY",
    "mx": "MEXICO",
    "es": "ESPAÑA",
    "ec": "ECUADOR",
    "cr": "COSTA RICA",
    "co": "COLOMBIA",
    "cl": "CHILE",
    "br": "BRASIL",
    "bo": "BOLIVIA",
    "ar": "ARGENTINA",
    "us": "ESTADOS UNIDOS",
    "ca": "CANADA",
    "gb": "REINO UNIDO",
    "fr": "FRANCIA",
    "de": "ALEMANIA",
    "it": "ITALIA",
    "no": "NORUEGA",
    "se": "SUECIA",
    "dk": "DINAMARCA",
}


# ============================================================
# ÃšNICAS EXCEPCIONES PLUTO
# ============================================================

PLUTO_ESPECIALES = {
    "es": "ESPAÑA",
    "mx": "MEXICO",
    "cl": "CHILE",
    "ar": "ARGENTINA",
}


# ============================================================
# UTILIDADES
# ============================================================

def normalizar(texto):
    texto = unicodedata.normalize(
        "NFKD",
        texto or "",
    )

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


def nombre_base_canal(nombre):
    return normalizar(
        re.sub(
            r"\s*\[OPC\.\d+\]\s*$",
            "",
            nombre or "",
            flags=re.IGNORECASE,
        )
    )


def obtener_nombre_archivo(url):
    return Path(
        url.split("?", 1)[0]
    ).name.lower()


# ============================================================
# DETECTAR PAÃS DE FUENTE
# ============================================================

def detectar_codigo_pais_desde_fuente(url):

    nombre = obtener_nombre_archivo(url)

    # --------------------------------------------------------
    # pluto_de.m3u
    # pluto_es.m3u
    # --------------------------------------------------------

    match = re.match(
        r"pluto[_-]([a-z]{2})\.m3u$",
        nombre,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).lower()

    # --------------------------------------------------------
    # PlutoTV.ES.m3u
    # PlutoTV.MX.m3u
    # --------------------------------------------------------

    match = re.match(
        r"plutotv\.([a-z]{2})\.m3u$",
        nombre,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).lower()

    # --------------------------------------------------------
    # ES.m3u / CL.m3u / BR.m3u...
    # --------------------------------------------------------

    match = re.match(
        r"([a-z]{2})\.m3u$",
        nombre,
        re.IGNORECASE,
    )

    if match:
        codigo = match.group(1).lower()

        if codigo in PAISES:
            return codigo

    return None


def es_fuente_pluto(url):

    nombre = obtener_nombre_archivo(url)

    return (
        nombre.startswith("pluto_")
        or nombre.startswith("plutotv.")
        or nombre == "pluto_all.m3u"
        or "pluto" in nombre
    )


# ============================================================
# DESCARGAR
# ============================================================

def descargar(url):

    print("-" * 60)
    print("Descargando:")
    print(url)

    try:

        respuesta = requests.get(
            url,
            timeout=90,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
            },
        )

        respuesta.raise_for_status()

        texto = respuesta.text

        if "#EXTINF" not in texto:

            print(
                "  -> La fuente no contiene #EXTINF."
            )

            return []

        lineas = texto.splitlines()

        print(
            f"  -> LÃ­neas descargadas: {len(lineas)}"
        )

        return lineas

    except requests.RequestException as error:

        print(
            f"  -> ERROR HTTP/DESCARGA: {error}"
        )

        return []

    except Exception as error:

        print(
            f"  -> ERROR: {error}"
        )

        return []


# ============================================================
# CLASIFICADOR TEMÃTICO
# ============================================================

def clasificar(grupo, nombre):

    g = normalizar(grupo)
    n = normalizar(nombre)

    texto = f"{g} {n}"

    # --------------------------------------------------------
    # ADULTOS
    #
    # IMPORTANTE:
    # Ya NO existe una carpeta general ADULTOS.
    #
    # El contenido adulto solamente entra mediante:
    # XXX.m3u -> XXX.+18.ADULTO
    #
    # Por eso NO se clasifica automÃ¡ticamente por nombre.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # ANIME
    # --------------------------------------------------------

    if contiene(texto, [
        "anime",
        "japanese anime",
        "animacion japonesa",
        "otaku",
        "one piece",
        "naruto",
        "pokemon",
        "yu-gi-oh",
        "yu gi oh",
        "dragon ball",
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
        "niÃ±os",
        "nina",
        "niÃ±a",
        "junior",
        "toons",
        "preschool",
        "preescolar",
        "baby shark",
        "pitufos",
        "rugrats",
        "popeye",
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
        "euronews",
    ]):
        return "NOTICIAS"

    # --------------------------------------------------------
    # MÃšSICA
    # --------------------------------------------------------

    if contiene(texto, [
        "music",
        "music:",
        "musica",
        "musical",
        "musique",
        "musica tv",
    ]):
        return "MÃšSICA"

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
    # EDUCACIÃ“N
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
        return "EDUCACIÃ“N"

    # --------------------------------------------------------
    # TECNOLOGÃA
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
        return "TECNOLOGÃA"

    # --------------------------------------------------------
    # RELIGIÃ“N
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
        return "RELIGIÃ“N"

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
        "competition",
        "competencia",
    ]):
        return "ENTRETENIMIENTO"

    # --------------------------------------------------------
    # PAÃSES
    # --------------------------------------------------------

    paises = [
        (["chile", " ch ", ":ch", "cl:"], "CHILE"),
        (["mexico", "mÃ©xico", " mexico:"], "MÃ‰XICO"),
        (["argentina"], "ARGENTINA"),
        (["peru", "perÃº"], "PERÃš"),
        (["colombia"], "COLOMBIA"),
        (["ecuador"], "ECUADOR"),
        (["bolivia"], "BOLIVIA"),
        (["venezuela"], "VENEZUELA"),
        (["uruguay"], "URUGUAY"),
        (["paraguay"], "PARAGUAY"),
        (["brasil", "brazil"], "BRASIL"),
        (["espana", "espaÃ±a", "spain"], "ESPAÃ‘A"),
        (["estados unidos", "united states", "usa"], "ESTADOS UNIDOS"),
        (["canada", "canadÃ¡"], "CANADÃ"),
        (["francia", "france"], "FRANCIA"),
        (["italia", "italy"], "ITALIA"),
        (["alemania", "germany"], "ALEMANIA"),
        (["portugal"], "PORTUGAL"),
        (["japon", "japÃ³n", "japan"], "JAPÃ“N"),
        (["corea", "korea"], "COREA"),
        (["reino unido", "united kingdom"], "REINO UNIDO"),
        (["noruega", "norway"], "NORUEGA"),
        (["suecia", "sweden"], "SUECIA"),
        (["dinamarca", "denmark"], "DINAMARCA"),
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
        "latinoamÃ©rica",
        "south america",
        "sudamerica",
        "sudamÃ©rica",
    ]):
        return "LATINOAMÃ‰RICA"

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
# EXTRAER ENTRADAS
# ============================================================

def extraer_entradas(lineas):

    entradas = []

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

        entradas.append(
            (info, url)
        )

        i = j + 1

    return entradas


# ============================================================
# GRUPOS PARA CADA FUENTE
# ============================================================

def grupos_para_fuente(
    fuente,
    info,
    nombre,
):

    archivo = obtener_nombre_archivo(
        fuente
    )

    codigo = detectar_codigo_pais_desde_fuente(
        fuente
    )

    # ========================================================
    # XXX
    # ========================================================

    if archivo == "xxx.m3u":
        return ["XXX.+18.ADULTO"]

    # ========================================================
    # RELIGIOSOS
    # ========================================================

    if archivo == "religiosos.m3u":
        return ["RELIGIÃ“N"]

    # ========================================================
    # MÃšSICA
    # ========================================================

    if archivo == "musica.m3u":
        return ["MÃšSICA"]

    # ========================================================
    # LATAM
    # ========================================================

    if archivo == "latam.m3u":
        return ["LATINOAMÃ‰RICA"]

    # ========================================================
    # M3U.CL POR PAÃS
    # ========================================================

    if (
        "m3u.cl/lista/" in fuente.lower()
        and codigo in PAISES
    ):
        return [PAISES[codigo]]

    # ========================================================
    # PLUTO
    # ========================================================

    if es_fuente_pluto(fuente):

        # ----------------------------------------------------
        # PLUTO ES / MX / CL / AR
        #
        # ÃšNICOS que pueden aparecer en:
        #
        # PLUTO TV
        # PAÃS
        # TEMÃTICA
        # ----------------------------------------------------

        if codigo in PLUTO_ESPECIALES:

            pais = PLUTO_ESPECIALES[codigo]

            grupo_original = ""

            if "group-title=" in info.lower():

                match = re.search(
                    r'group-title="([^"]*)"',
                    info,
                    re.IGNORECASE,
                )

                if match:
                    grupo_original = match.group(1)

            tematica = clasificar(
                grupo_original,
                nombre,
            )

            grupos = [
                "PLUTO TV",
                pais,
            ]

            if (
                tematica
                and tematica not in grupos
                and tematica != "OTROS"
            ):
                grupos.append(tematica)

            return grupos

        # ----------------------------------------------------
        # TODOS LOS DEMÃS PLUTO
        #
        # SOLO VAN A SU PAÃS.
        #
        # NO PLUTO TV.
        # NO TEMÃTICA.
        # ----------------------------------------------------

        if codigo in PAISES:

            return [PAISES[codigo]]

        # ----------------------------------------------------
        # PLUTO ALL
        #
        # Intenta encontrar paÃ­s en metadata/nombre.
        # ----------------------------------------------------

        if archivo == "pluto_all.m3u":

            grupo_original = ""

            if "group-title=" in info.lower():

                match = re.search(
                    r'group-title="([^"]*)"',
                    info,
                    re.IGNORECASE,
                )

                if match:
                    grupo_original = match.group(1)

            texto = normalizar(
                f"{grupo_original} {nombre}"
            )

            detecciones = [

                ([
                    "germany",
                    "alemania",
                    "deutschland",
                ], "ALEMANIA"),

                ([
                    "france",
                    "francia",
                ], "FRANCIA"),

                ([
                    "italy",
                    "italia",
                ], "ITALIA"),

                ([
                    "spain",
                    "espaÃ±a",
                    "espana",
                ], "ESPAÃ‘A"),

                ([
                    "mexico",
                    "mÃ©xico",
                ], "MÃ‰XICO"),

                ([
                    "argentina",
                ], "ARGENTINA"),

                ([
                    "chile",
                ], "CHILE"),

                ([
                    "brazil",
                    "brasil",
                ], "BRASIL"),

                ([
                    "canada",
                    "canadÃ¡",
                ], "CANADÃ"),

                ([
                    "united states",
                    "usa",
                    "united states of america",
                ], "ESTADOS UNIDOS"),

                ([
                    "united kingdom",
                    "uk",
                    "britain",
                    "england",
                ], "REINO UNIDO"),

                ([
                    "norway",
                    "noruega",
                ], "NORUEGA"),

                ([
                    "sweden",
                    "suecia",
                ], "SUECIA"),

                ([
                    "denmark",
                    "dinamarca",
                ], "DINAMARCA"),
            ]

            for palabras, pais in detecciones:

                if contiene(
                    texto,
                    palabras,
                ):
                    return [pais]

            return ["OTROS"]

    # ========================================================
    # FUENTES GENERALES
    # ========================================================

    grupo_original = ""

    if "group-title=" in info.lower():

        match = re.search(
            r'group-title="([^"]*)"',
            info,
            re.IGNORECASE,
        )

        if match:
            grupo_original = match.group(1)

    tematica = clasificar(
        grupo_original,
        nombre,
    )

    return [tematica]


# ============================================================
# AGREGAR A GRUPO
# ============================================================

def agregar_a_grupo(
    grupos,
    grupo,
    info,
    url,
    vistos_por_grupo,
    canales_por_grupo,
):

    if not grupo:
        grupo = "OTROS"

    # --------------------------------------------------------
    # URL DUPLICADA DENTRO DE ESTA CARPETA
    # --------------------------------------------------------

    if grupo not in vistos_por_grupo:
        vistos_por_grupo[grupo] = set()

    if url in vistos_por_grupo[grupo]:
        return False

    vistos_por_grupo[grupo].add(url)

    # --------------------------------------------------------
    # NOMBRE
    # --------------------------------------------------------

    if "," in info:
        nombre = info.split(
            ",",
            1,
        )[1].strip()

    else:
        nombre = "Canal"

    base = nombre_base_canal(
        nombre
    )

    if grupo not in canales_por_grupo:
        canales_por_grupo[grupo] = {}

    numero = (
        canales_por_grupo[grupo].get(
            base,
            0,
        )
        + 1
    )

    canales_por_grupo[grupo][base] = numero

    if numero == 1:
        nombre_final = nombre

    else:
        nombre_final = (
            f"{nombre} [OPC.{numero}]"
        )

    # --------------------------------------------------------
    # REEMPLAZAR NOMBRE
    # --------------------------------------------------------

    if "," in info:

        info = (
            info.split(",", 1)[0]
            + ","
            + nombre_final
        )

    # --------------------------------------------------------
    # GROUP TITLE
    # --------------------------------------------------------

    if re.search(
        r'group-title="',
        info,
        re.IGNORECASE,
    ):

        info = re.sub(
            r'group-title="[^"]*"',
            f'group-title="{grupo}"',
            info,
            count=1,
            flags=re.IGNORECASE,
        )

    else:

        info = info.replace(
            ",",
            f' group-title="{grupo}",',
            1,
        )

    # --------------------------------------------------------
    # AGREGAR
    # --------------------------------------------------------

    if grupo not in grupos:
        grupos[grupo] = []

    grupos[grupo].append(info)
    grupos[grupo].append(url)

    return True


# ============================================================
# PROCESAR FUENTE
# ============================================================

def procesar_fuente(
    fuente,
    lineas,
    grupos,
    vistos_por_grupo,
    canales_por_grupo,
):

    nuevas = 0

    entradas = extraer_entradas(
        lineas
    )

    for info, url in entradas:

        if "," in info:
            nombre = info.split(
                ",",
                1,
            )[1].strip()

        else:
            nombre = "Canal"

        destinos = grupos_para_fuente(
            fuente,
            info,
            nombre,
        )

        for destino in destinos:

            if agregar_a_grupo(
                grupos,
                destino,
                info,
                url,
                vistos_por_grupo,
                canales_por_grupo,
            ):

                nuevas += 1

    return nuevas


# ============================================================
# ORDEN DE GRUPOS
# ============================================================

ORDEN_GRUPOS = [

    # --------------------------------------------------------
    # PLUTO
    # --------------------------------------------------------

    "PLUTO TV",

    # --------------------------------------------------------
    # LATINOAMÃ‰RICA
    # --------------------------------------------------------

    "ARGENTINA",
    "BOLIVIA",
    "BRASIL",
    "CHILE",
    "COLOMBIA",
    "COSTA RICA",
    "ECUADOR",
    "ESPAÃ‘A",
    "MÃ‰XICO",
    "PARAGUAY",
    "PERÃš",
    "REPÃšBLICA DOMINICANA",
    "URUGUAY",
    "VENEZUELA",

    # --------------------------------------------------------
    # RESTO DEL MUNDO
    # --------------------------------------------------------

    "ESTADOS UNIDOS",
    "CANADÃ",
    "REINO UNIDO",
    "FRANCIA",
    "ALEMANIA",
    "ITALIA",
    "NORUEGA",
    "SUECIA",
    "DINAMARCA",
    "PORTUGAL",
    "JAPÃ“N",
    "COREA",

    # --------------------------------------------------------
    # REGIONES
    # --------------------------------------------------------

    "LATINOAMÃ‰RICA",
    "INTERNACIONAL",

    # --------------------------------------------------------
    # TEMÃTICAS
    # --------------------------------------------------------

    "ANIME",
    "INFANTIL",
    "DEPORTES",
    "NOTICIAS",
    "MÃšSICA",
    "CINE",
    "SERIES",
    "DOCUMENTALES",
    "CULTURA",
    "EDUCACIÃ“N",
    "TECNOLOGÃA",
    "RELIGIÃ“N",
    "COCINA",
    "ESTILO DE VIDA",
    "ENTRETENIMIENTO",
    "OTROS",

    # --------------------------------------------------------
    # XXX SIEMPRE AL FINAL
    # --------------------------------------------------------

    "XXX.+18.ADULTO",
]


# ============================================================
# ORDENAR GRUPOS
# ============================================================

def ordenar_grupos(grupos):

    posicion = {
        grupo: i
        for i, grupo in enumerate(
            ORDEN_GRUPOS
        )
    }

    def clave(grupo):

        if grupo == "XXX.+18.ADULTO":
            return (
                999999,
                grupo,
            )

        return (
            posicion.get(
                grupo,
                500,
            ),
            grupo,
        )

    return sorted(
        grupos.keys(),
        key=clave,
    )


# ============================================================
# SOUTH PARK AL FINAL DE ANIME
#
# IMPORTANTE:
# South Park SOLO llegarÃ¡ aquÃ­ si previamente fue clasificado
# dentro de ANIME por la temÃ¡tica de la fuente.
#
# Ya NO se fuerza South Park -> ANIME.
# ============================================================

def ordenar_anime(contenido):

    bloques = []

    i = 0

    while i < len(contenido):

        if not contenido[i].startswith(
            "#EXTINF"
        ):
            i += 1
            continue

        if i + 1 >= len(contenido):
            break

        info = contenido[i]
        url = contenido[i + 1]

        nombre = ""

        if "," in info:

            nombre = info.split(
                ",",
                1,
            )[1]

        if normalizar(
            nombre
        ).startswith(
            "south park"
        ):

            bloques.append(
                (
                    "south",
                    [
                        info,
                        url,
                    ],
                )
            )

        else:

            bloques.append(
                (
                    "normal",
                    [
                        info,
                        url,
                    ],
                )
            )

        i += 2

    normales = [
        bloque
        for tipo, bloque in bloques
        if tipo == "normal"
    ]

    south = [
        bloque
        for tipo, bloque in bloques
        if tipo == "south"
    ]

    resultado = []

    for bloque in normales:
        resultado.extend(bloque)

    for bloque in south:
        resultado.extend(bloque)

    return resultado


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 75)
    print(
        "       IPTV CHILE MASTER - GOD BUILDER V8"
    )
    print("=" * 75)

    print()
    print("IMPORTANTE:")
    print(
        "El archivo GOD original NO serÃ¡ reemplazado."
    )
    print(
        f"Se generarÃ¡:\n{SALIDA}"
    )
    print()

    # --------------------------------------------------------
    # COMPROBAR PRINCIPAL
    # --------------------------------------------------------

    if not PRINCIPAL.exists():

        raise FileNotFoundError(
            f"No existe la lista principal:\n{PRINCIPAL}"
        )

    # --------------------------------------------------------
    # ESTRUCTURAS
    # --------------------------------------------------------

    grupos = {}

    # URL por carpeta
    vistos_por_grupo = {}

    # OPC.X por carpeta
    canales_por_grupo = {}

    # ========================================================
    # LISTA PRINCIPAL
    # ========================================================

    print("=" * 75)
    print(
        "[1] PROCESANDO LISTA PRINCIPAL"
    )
    print("=" * 75)

    principal = PRINCIPAL.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    entradas_principal = extraer_entradas(
        principal
    )

    print(
        f"  -> Entradas encontradas: "
        f"{len(entradas_principal)}"
    )

    antes = sum(
        len(v)
        for v in vistos_por_grupo.values()
    )

    nuevas_principal = procesar_fuente(
        "IPTV-CHILE-MAESTRA_CORREGIDO.m3u",
        principal,
        grupos,
        vistos_por_grupo,
        canales_por_grupo,
    )

    despues = sum(
        len(v)
        for v in vistos_por_grupo.values()
    )

    print(
        f"URLs agregadas desde principal: "
        f"{despues - antes}"
    )

    # ========================================================
    # FUENTES EXTERNAS
    # ========================================================

    print()
    print("=" * 75)
    print(
        "[2] PROCESANDO FUENTES EXTERNAS"
    )
    print("=" * 75)

    total_nuevas = 0

    for numero, fuente in enumerate(
        FUENTES,
        1,
    ):

        print()
        print(
            f"[FUENTE {numero}/{len(FUENTES)}]"
        )
        print(fuente)
        print("-" * 60)

        lineas = descargar(
            fuente
        )

        if not lineas:

            print(
                "  -> Fuente omitida."
            )

            continue

        antes_total = sum(
            len(v)
            for v in vistos_por_grupo.values()
        )

        nuevas = procesar_fuente(
            fuente,
            lineas,
            grupos,
            vistos_por_grupo,
            canales_por_grupo,
        )

        despues_total = sum(
            len(v)
            for v in vistos_por_grupo.values()
        )

        incremento = (
            despues_total
            - antes_total
        )

        total_nuevas += incremento

        print(
            f"  -> Entradas agregadas: "
            f"{nuevas}"
        )

        print(
            f"  -> URLs fÃ­sicas nuevas en grupos: "
            f"{incremento}"
        )

    # ========================================================
    # CONSTRUIR SALIDA
    # ========================================================

    print()
    print("=" * 75)
    print(
        "[3] GENERANDO NUEVA LISTA"
    )
    print("=" * 75)

    final = [
        "#EXTM3U"
    ]

    grupos_ordenados = ordenar_grupos(
        grupos
    )

    total_entradas = 0
    total_urls = 0
    total_opciones = 0

    # --------------------------------------------------------
    # ESCRIBIR GRUPOS
    # --------------------------------------------------------

    for grupo in grupos_ordenados:

        contenido = grupos[grupo]

        if grupo == "ANIME":

            contenido = ordenar_anime(
                contenido
            )

        final.extend(
            contenido
        )

        cantidad = sum(
            1
            for linea in contenido
            if linea.startswith(
                "#EXTINF"
            )
        )

        total_entradas += cantidad
        total_urls += cantidad

    # --------------------------------------------------------
    # CONTAR OPCIONES
    # --------------------------------------------------------

    for grupo, canales in (
        canales_por_grupo.items()
    ):

        for cantidad in canales.values():

            if cantidad > 1:

                total_opciones += (
                    cantidad - 1
                )

    # ========================================================
    # GUARDAR
    # ========================================================

    SALIDA.write_text(
        "\n".join(final) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # ========================================================
    # RESUMEN
    # ========================================================

    urls_unicas_globales = set()

    for urls in vistos_por_grupo.values():

        urls_unicas_globales.update(
            urls
        )

    print()
    print("=" * 75)
    print(
        "       LISTA GOD V8 TERMINADA"
    )
    print("=" * 75)

    print(
        f"Entradas finales: "
        f"{total_entradas}"
    )

    print(
        f"URLs Ãºnicas globales: "
        f"{len(urls_unicas_globales)}"
    )

    print(
        f"URLs fÃ­sicas finales: "
        f"{total_urls}"
    )

    print(
        f"Alternativas [OPC.X]: "
        f"{total_opciones}"
    )

    print(
        f"Grupos finales: "
        f"{len(grupos_ordenados)}"
    )

    print(
        f"Archivo generado:\n{SALIDA}"
    )

    print(
        f"TamaÃ±o: "
        f"{SALIDA.stat().st_size / 1024 / 1024:.2f} MB"
    )

    # ========================================================
    # REGLAS
    # ========================================================

    print()
    print("=" * 75)
    print(
        "REGLAS APLICADAS"
    )
    print("=" * 75)

    print(
        "1. La lista principal se procesa primero."
    )

    print(
        "2. La URL idÃ©ntica no se repite dentro "
        "de una misma carpeta."
    )

    print(
        "3. Una URL diferente del mismo canal "
        "se conserva como alternativa."
    )

    print(
        "4. [OPC.2], [OPC.3], etc. se calculan "
        "por carpeta."
    )

    print(
        "5. Las listas M3U.CL por paÃ­s van "
        "directamente a su paÃ­s."
    )

    print(
        "6. XXX.m3u se convierte en "
        "XXX.+18.ADULTO."
    )

    print(
        "7. XXX.+18.ADULTO queda SIEMPRE "
        "como Ãºltimo grupo."
    )

    print(
        "8. Pluto ES/MX/CL/AR puede aparecer "
        "en PLUTO TV + paÃ­s + temÃ¡tica."
    )

    print(
        "9. Pluto DE/FR/IT/GB/US/CA/BR/NO/SE/DK "
        "va SOLAMENTE a su paÃ­s."
    )

    print(
        "10. Los Pluto que van solamente a su paÃ­s "
        "NO se agregan a PLUTO TV."
    )

    print(
        "11. Si un Pluto tiene una URL repetida "
        "dentro de ese paÃ­s, se omite."
    )

    print(
        "12. Si un Pluto tiene una URL diferente "
        "para el mismo canal, se conserva como "
        "alternativa [OPC.X]."
    )

    print(
        "13. Una URL puede existir en varias carpetas "
        "cuando las reglas lo permiten."
    )

    print(
        "14. South Park NO se fuerza a ANIME por "
        "el nombre del canal."
    )

    print(
        "15. Si South Park pertenece a una fuente "
        "clasificada como ANIME, queda al final "
        "de ANIME."
    )

    print(
        "16. Popeye y contenido infantil reconocido "
        "van a INFANTIL."
    )

    print(
        "17. Competition/Competencia va a "
        "ENTRETENIMIENTO."
    )

    print(
        "18. No se crea la carpeta general ADULTOS."
    )

    print(
        "19. El contenido de XXX.m3u se mantiene "
        "exclusivamente en XXX.+18.ADULTO."
    )

    print(
        "20. La salida se escribe en UTF-8."
    )

    print(
        "21. El GOD original NO se reemplaza."
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



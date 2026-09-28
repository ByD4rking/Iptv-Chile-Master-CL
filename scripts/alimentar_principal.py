from pathlib import Path
import re
import unicodedata
import requests
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"

# Fuente especial IPTV-SV. NO hereda las reglas de Pluto.
FUENTE_IPTVSV = "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/IPTVSV.m3u"

# ============================================================
# FUENTES NORMALES / COLABORADORAS
# ============================================================
# La principal manda. Estas fuentes SOLO complementan.
# Nunca se reconstruye ni se reordena la principal.
FUENTES = [
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
    FUENTE_IPTVSV,
    "https://m3u.cl/lista/total.m3u",
    "https://m3u.cl/lista/top.m3u",
]

# ============================================================
# PLUTO: SOLO NUESTRAS LISTAS
# Las URLs antiguas de Pluto se sustituyen por las listas propias al actualizar la principal.
# ============================================================
# Estas son las listas Pluto que alimentan la PRINCIPAL.
# US y ALL NO se agregan aquí: pertenecen a la lista GOD.
FUENTES_PLUTO = [
    # LATAM primero: misma prioridad que la auditoría temática de Pluto.
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_latam.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_es.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_cl.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_ar.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_mx.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_br.m3u",
]

# Catálogo adicional SOLO para reemplazar enlaces Pluto de terceros.
# Estas fuentes no se agregan como canales a la principal.
FUENTES_PLUTO_CATALOGO = FUENTES_PLUTO + [
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_us.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_all.m3u",
]

# Fuentes Pluto antiguas. Sus URLs de canales se descargan y se
# eliminan de la principal antes de incorporar nuestras listas.
FUENTES_PLUTO_ANTIGUAS = [
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_all.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_us.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_ca.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_gb.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_fr.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_de.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_es.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_it.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_mx.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_br.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_ar.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_cl.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_no.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_se.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_dk.m3u",
    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.ES.m3u",
    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u",
]

PAIS_POR_FUENTE = {
    "/XXX.m3u": "xxx",
    "/religiosos.m3u": "religiosos",
    "/musica.m3u": "musica",
    "/LATAM.m3u": "latam",
    "/CL.m3u": "chile",
    "/PE.m3u": "peru",
    "/PY.m3u": "paraguay",
    "/MX.m3u": "mexico",
    "/ES.m3u": "espana",
    "/EC.m3u": "ecuador",
    "/CR.m3u": "costa rica",
    "/CO.m3u": "colombia",
    "/BR.m3u": "brasil",
    "/BO.m3u": "bolivia",
    "/AR.m3u": "argentina",
    "/VE.m3u": "venezuela",
    "/DO.m3u": "republica dominicana",
}

CATEGORIAS_PAIS = {
    "peru": "Perú",
    "bolivia": "Bolivia",
    "argentina": "Argentina",
    "brasil": "Brasil",
    "colombia": "Colombia",
    "ecuador": "Ecuador",
    "venezuela": "Venezuela",
    "paraguay": "Paraguay",
    "mexico": "México",
    "espana": "España",
    "costa rica": "Costa Rica",
    "republica dominicana": "República Dominicana",
}

def normalizar(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()

def url_es_valida(url):
    return bool(re.match(r"^https?://", url.strip(), re.I))

def extraer_categoria(linea):
    m = re.search(r'group-title="([^"]*)"', linea, re.I)
    return m.group(1).strip() if m else ""

def extraer_nombre(linea):
    return linea.split(",", 1)[1].strip() if "," in linea else ""

def parsear_m3u(texto):
    resultado = []
    actual = None
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("#EXTINF"):
            actual = {
                "extinf": linea,
                "nombre": extraer_nombre(linea),
                "categoria": extraer_categoria(linea),
                "extras": [],
            }
        elif linea.startswith("#") and actual:
            # Conserva metadatos del canal fuente, por ejemplo
            # #EXTVLCOPT, #KODIPROP, #EXTGRP u otras directivas.
            actual["extras"].append(linea)
        elif not linea.startswith("#") and url_es_valida(linea) and actual:
            actual["url"] = linea
            resultado.append(actual)
            actual = None
    return resultado

def reemplazar_categoria(extinf, destino):
    if re.search(r'group-title="[^"]*"', extinf, re.I):
        return re.sub(
            r'group-title="[^"]*"',
            f'group-title="{destino}"',
            extinf,
            count=1,
            flags=re.I,
        )
    return extinf.replace(
        "#EXTINF:",
        f'#EXTINF:-1 group-title="{destino}"',
        1,
    )

def buscar_categoria_existente(nombre, categorias):
    objetivo = normalizar(nombre)
    if not objetivo:
        return None
    for categoria in categorias:
        if normalizar(categoria) == objetivo:
            return categoria
    return None

def encontrar_categoria_tematica(texto, categorias):
    texto = normalizar(texto)
    reglas = [
        ("ANIME", [r"\banime\b"]),
        ("INFANTILES", [r"\b(infantil|infantiles|kids|kid|teen|nick)\b"]),
        ("DEPORTES", [r"\b(deporte|deportes|sport|sports|futbol|football)\b"]),
        ("MUSICA", [r"\b(musica|music)\b"]),
        ("CINE", [r"\b(cine|peliculas|pelicula|movies|movie|films?)\b"]),
        ("SERIES", [r"\b(series|serie)\b"]),
        ("ENTRETENIMIENTO", [r"\b(entretenimiento|entertainment|reto|reality|realities|concurso|concursos|programa|programas)\b"]),
        ("COMEDIA", [r"\b(comedia|comedy)\b"]),
        ("RELIGIOSOS", [r"\b(religioso|religiosos|religion)\b"]),
        ("DOCUMENTALES", [r"\b(documental|documentales|documentary)\b"]),
        ("INFORMATIVOS", [r"\b(noticias|noticia|informativos|news)\b"]),
        ("GENERAL", [r"\bgeneral\b"]),
    ]
    for candidato, patrones in reglas:
        if any(re.search(p, texto) for p in patrones):
            destino = buscar_categoria_existente(candidato, categorias)
            if destino:
                return destino
    return None

PAISES_GENERICO_IPTVSV = {
    "peru", "bolivia", "argentina", "brasil", "colombia", "ecuador",
    "venezuela", "paraguay", "mexico", "espana", "costa rica",
    "republica dominicana", "chile", "el salvador", "el salvador - tcs", "guatemala", "honduras",
    "nicaragua", "panama", "cuba", "puerto rico", "uruguay"
}


def es_fuente_iptvsv(fuente):
    return fuente == FUENTE_IPTVSV


def es_categoria_pais_generica_iptvsv(categoria):
    c = normalizar(categoria)
    return c in PAISES_GENERICO_IPTVSV or bool(re.match(r"^(el )?(salvador|guatemala|honduras|nicaragua|panama|cuba|puerto rico|uruguay)$", c))


def determinar_destino_iptvsv(categoria, nombre, categorias):
    """IPTV-SV respeta la carpeta declarada, con solo alias canónicos explícitos.

    No reclasifica por nombre, no usa reglas temáticas y no crea carpetas.
    """
    categoria = (categoria or "").strip()
    if not categoria:
        return None

    c_norm = normalizar(categoria)
    aliases = {
        "chile": "CHILE TV",
        "el salvador": "EL Salvador",
        "el salvador - tcs": "EL Salvador",
        "el salvador local": "EL Salvador",
        "documentales": "Documentales y Cultura",
        "infantil": "Infantiles",
        "teen": "Infantiles",
        "noticias": "Informativos",
    }
    categoria_busqueda = aliases.get(c_norm, categoria)

    # La carpeta especial solo se acepta si YA existe.
    if c_norm == "tv mas importantes de cada pais":
        return buscar_categoria_existente(
            "TV MÁS IMPORTANTES DE CADA PAÍS", categorias
        )

    # Coincidencia con una carpeta existente. Nunca inventar una nueva.
    return buscar_categoria_existente(categoria_busqueda, categorias)

def determinar_destino(categoria, nombre, pais_fuente, categorias):
    texto = normalizar(f"{categoria or ''} {nombre or ''}")

    # Reglas fijas de M3U.CL: estas fuentes tienen destino propio.
    if pais_fuente == "xxx":
        return buscar_categoria_existente("XXX+18", categorias) or "XXX+18"

    if pais_fuente == "religiosos":
        return buscar_categoria_existente("RELIGIOSOS", categorias) or "RELIGIOSOS"

    if pais_fuente == "musica":
        return buscar_categoria_existente("MÚSICA", categorias) or "MÚSICA"

    if pais_fuente == "latam":
        return (
            buscar_categoria_existente("LATAM", categorias)
            or buscar_categoria_existente("LATINOAMÉRICA", categorias)
            or "LATAM"
        )

    if pais_fuente == "chile":
        return buscar_categoria_existente("CHILE TV", categorias) or "CHILE TV"

    if pais_fuente in CATEGORIAS_PAIS:
        destino = buscar_categoria_existente(CATEGORIAS_PAIS[pais_fuente], categorias)
        if destino:
            return destino

    aliases = {
        "peru": ["peru"],
        "bolivia": ["bolivia"],
        "argentina": ["argentina"],
        "brasil": ["brasil", "brazil"],
        "colombia": ["colombia"],
        "ecuador": ["ecuador"],
        "venezuela": ["venezuela"],
        "paraguay": ["paraguay"],
        "mexico": ["mexico"],
        "espana": ["espana", "spain"],
        "costa rica": ["costa rica"],
        "republica dominicana": ["republica dominicana", "dominican republic"],
    }
    for pais, nombres in aliases.items():
        if any(normalizar(alias) in texto for alias in nombres):
            destino = buscar_categoria_existente(CATEGORIAS_PAIS[pais], categorias)
            if destino:
                return destino

    return encontrar_categoria_tematica(texto, categorias)

def determinar_destino_pluto(categoria, nombre, categorias):
    """
    Decide dónde va un canal Pluto respetando primero la carpeta declarada
    por Pluto y luego la temática de esa carpeta.

    Excepción fija: Pluto TV Brazil es contenido en portugués y va
    exclusivamente a la carpeta-país Brasil, nunca a una carpeta temática
    de la lista en español.

    Prioridad:
      1) Si la carpeta de Pluto coincide con una carpeta existente, usarla.
      2) Si la carpeta/nombre indica una temática (ANIME, INFANTILES, CINE,
         etc.), usar la carpeta temática existente.
      3) Si no hay coincidencia, el llamador conserva la categoría original
         de Pluto y la agrega al final.

    La deduplicación se hace globalmente por URL, por lo que:
      - tres Pokémon Pluto con tres URLs distintas => entran los 3;
      - la misma URL repetida en otra lista => entra solo 1.
    """
    categoria = (categoria or "").strip()
    nombre = (nombre or "").strip()
    texto = normalizar(f"{categoria} {nombre}")

    # Pluto TV Brazil: exclusivamente carpeta-país Brasil.
    if re.search(r"\b(pluto\s*tv\s*)?(brazil|brasil)\b", texto):
        destino_brasil = buscar_categoria_existente("Brasil", categorias)
        if destino_brasil:
            return destino_brasil
        return "Brasil"

    # NUNCA crear ni respetar una carpeta genérica "Pluto TV".
    # Se clasifica por nombre/tema y, si no hay destino seguro, se omite
    # para evitar que vuelva a aparecer esa carpeta.
    if normalizar(categoria) == "pluto tv":
        destino_especial = destino_especial_total_otros(nombre, categoria, categorias)
        if destino_especial and normalizar(destino_especial) != "pluto tv":
            return destino_especial
        return None

    exacta = buscar_categoria_existente(categoria, categorias)
    if exacta:
        return exacta

    return encontrar_categoria_tematica(
        f"{categoria} {nombre}",
        categorias,
    )

def construir_bloque(canal, destino):
    bloque = [
        reemplazar_categoria(canal["extinf"], destino),
    ]
    bloque.extend(canal.get("extras", []))
    bloque.append(canal["url"].strip())
    return bloque

def encontrar_rango_categoria(lineas, categoria):
    objetivo = normalizar(categoria)
    inicio = fin = None
    for i, linea in enumerate(lineas):
        if not linea.startswith("#EXTINF"):
            continue
        cat = normalizar(extraer_categoria(linea))
        if cat == objetivo:
            if inicio is None:
                inicio = i
            fin = i
        elif inicio is not None:
            break
    return (inicio, fin) if inicio is not None else None

def categorias_de_lineas(lineas):
    categorias = []
    for linea in lineas:
        if linea.startswith("#EXTINF"):
            cat = extraer_categoria(linea)
            if cat and not any(normalizar(cat) == normalizar(x) for x in categorias):
                categorias.append(cat)
    return categorias

def mapa_urls_principal(lineas):
    urls = set()
    for linea in lineas:
        if url_es_valida(linea.strip()):
            urls.add(linea.strip())
    return urls

def identidad_pluto(extinf, url):
    """
    Identidad estable de un canal Pluto:
      1) tvg-id, cuando existe;
      2) channel ID embebido en la URL;
      3) sin ID, no se fuerza deduplicación por nombre.
    Esto permite conservar canales con el mismo nombre pero IDs Pluto
    realmente distintos, y eliminar copias regionales del mismo canal.
    """
    m_id = re.search(r'tvg-id="([^"]+)"', extinf or "", re.I)
    if m_id and m_id.group(1).strip():
        return "id:" + m_id.group(1).strip().lower()
    cid = extraer_pluto_id(url)
    return "id:" + cid if cid else ""

def reclasificar_pluto_existente(lineas, session):
    """
    Revisa TODOS los Pluto que ya están en la principal y sincroniza su
    carpeta con la categoría declarada por nuestras listas Pluto propias.

    Esto corrige el caso en que un canal Pluto ya existía en la principal
    bajo una carpeta genérica (por ejemplo RETRO/COMPETENCIA/otra) pero la
    fuente oficial propia lo declara en una carpeta temática concreta.

    No cambia URL, nombre, logo ni otros metadatos: solo group-title.
    No elimina canales.
    """
    categorias_fuente = {}
    errores = 0

    # Pluto LATAM es la referencia temática principal. Las listas regionales
    # complementan, pero nunca deben sobrescribir una categoría ya declarada
    # por LATAM. Brasil se corrige después con su regla específica.
    fuentes_pluto_ordenadas = sorted(
        FUENTES_PLUTO,
        key=lambda f: (
            0 if f.lower().endswith("pluto_latam.m3u") else 1,
            0 if f.lower().endswith("pluto.m3u") else 1,
            f,
        ),
    )

    for fuente in fuentes_pluto_ordenadas:
        try:
            r = session.get(fuente, timeout=30)
            r.raise_for_status()
            for canal in parsear_m3u(r.text):
                identidad = identidad_pluto(
                    canal.get("extinf", ""),
                    canal.get("url", ""),
                )
                categoria = (canal.get("categoria") or "").strip()
                if identidad and categoria:
                    # La primera fuente que clasifica el ID gana; como
                    # pluto_latam se procesa primero, sus categorías quedan
                    # protegidas frente a clasificaciones regionales distintas.
                    categorias_fuente.setdefault(identidad, categoria)
        except Exception as e:
            errores += 1
            print(f"  -> No se pudo consultar Pluto para sincronizar carpetas: {fuente} :: {e}")

    categorias_actuales = categorias_de_lineas(lineas)
    salida = []
    movidos = 0
    por_categoria = defaultdict(int)
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            salida.append(lineas[i])
            i += 1
            continue

        extinf = lineas[i]
        bloque = [extinf]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            bloque.append(lineas[j])
            j += 1

        if j >= len(lineas) or not url_es_valida(lineas[j].strip()):
            salida.extend(bloque)
            i = j
            continue

        url = lineas[j].strip()
        bloque.append(url)
        j += 1

        if not es_url_pluto(url):
            salida.extend(bloque)
            i = j
            continue

        identidad = identidad_pluto(extinf, url)
        categoria_fuente = categorias_fuente.get(identidad)
        if not categoria_fuente:
            salida.extend(bloque)
            i = j
            continue

        destino = buscar_categoria_existente(categoria_fuente, categorias_actuales)
        if not destino:
            destino = categoria_fuente

        categoria_actual = extraer_categoria(extinf)
        if normalizar(categoria_actual) != normalizar(destino):
            bloque[0] = reemplazar_categoria(extinf, destino)
            movidos += 1
            por_categoria[destino] += 1
            if not any(normalizar(c) == normalizar(destino) for c in categorias_actuales):
                categorias_actuales.append(destino)

        salida.extend(bloque)
        i = j

    return salida, movidos, errores, dict(por_categoria)


def deduplicar_pluto_existente(lineas):
    """
    Elimina solo copias Pluto con el MISMO enlace de acceso.
    No deduplica por channel ID: dos regiones pueden compartir ID pero
    entregar URLs de acceso distintas y ambas deben conservarse.
    """
    salida = []
    urls_vistos = set()
    eliminados = 0
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            salida.append(lineas[i])
            i += 1
            continue

        extinf = lineas[i]
        bloque = [extinf]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            bloque.append(lineas[j])
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            url = lineas[j].strip()
            bloque.append(url)
            j += 1

            if es_url_pluto(url):
                if url in urls_vistos:
                    eliminados += 1
                    i = j
                    continue
                urls_vistos.add(url)

        salida.extend(bloque)
        i = j

    return salida, eliminados

def mover_pluto_brasil_a_brasil(lineas, session):
    """
    Corrige también los canales Pluto Brasil que YA estaban en la principal.

    La regla no se limita a los canales nuevos: identifica los IDs presentes
    en nuestra playlist oficial pluto_br.m3u y mueve esas entradas a Brasil.
    También reconoce URLs Pluto con country=BR o metadatos que indiquen Brasil.
    No cambia URL, nombre, logo ni ningún otro dato del canal; solo group-title.
    """
    fuente_br = "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_br.m3u"
    ids_br = set()
    errores = 0

    try:
        r = session.get(fuente_br, timeout=30)
        r.raise_for_status()
        for canal in parsear_m3u(r.text):
            identidad = identidad_pluto(canal.get("extinf", ""), canal.get("url", ""))
            if identidad:
                ids_br.add(identidad)
    except Exception as e:
        errores += 1
        print(f"  -> No se pudo cargar pluto_br para corregir carpeta Brasil: {e}")

    categorias = categorias_de_lineas(lineas)
    destino_brasil = buscar_categoria_existente("Brasil", categorias) or "Brasil"
    salida = []
    movidos = 0
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            salida.append(lineas[i])
            i += 1
            continue

        extinf = lineas[i]
        bloque = [extinf]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            bloque.append(lineas[j])
            j += 1

        if j >= len(lineas) or not url_es_valida(lineas[j].strip()):
            salida.extend(bloque)
            i = j
            continue

        url = lineas[j].strip()
        bloque.append(url)
        j += 1

        if not es_url_pluto(url):
            salida.extend(bloque)
            i = j
            continue

        identidad = identidad_pluto(extinf, url)
        texto = normalizar(f"{extraer_categoria(extinf) or ''} {extraer_nombre(extinf) or ''} {url}")
        es_br = bool(identidad and identidad in ids_br)
        es_br = es_br or bool(re.search(r"(?:[?&])country=br(?:&|$)", url, re.I))
        es_br = es_br or bool(re.search(r"\\b(brazil|brasil)\\b", texto))

        if es_br and normalizar(extraer_categoria(extinf) or "") != normalizar(destino_brasil):
            bloque[0] = reemplazar_categoria(extinf, destino_brasil)
            movidos += 1

        salida.extend(bloque)
        i = j

    return salida, movidos, errores


def extraer_pluto_id(url):
    """Obtiene el channel ID de una URL Pluto, sin depender del dominio."""
    m = re.search(r"/channel[s]?/([a-f0-9]{20,})", url or "", re.I)
    return m.group(1).lower() if m else ""


def es_url_pluto(url):
    """Detecta URLs de streaming Pluto sin considerar el dominio."""
    u = (url or "").lower()
    return (
        "pluto.tv" in u
        or ("stitcher" in u and "pluto" in u)
        or ("pluto" in u and ("/channel/" in u or "/channels/" in u))
    )


def cargar_catalogo_pluto_propio(session):
    """Carga exclusivamente nuestras playlists Pluto e indexa por ID y nombre."""
    por_id = {}
    por_nombre = {}
    por_region = defaultdict(dict)
    errores = 0

    for fuente in FUENTES_PLUTO_CATALOGO:
        try:
            r = session.get(fuente, timeout=30)
            r.raise_for_status()
            canales = parsear_m3u(r.text)
            m_region = re.search(r"pluto_([a-z]+)\.m3u$", fuente)
            region = m_region.group(1) if m_region else "all"

            for canal in canales:
                url = canal["url"].strip()
                if not url:
                    continue
                cid = extraer_pluto_id(url)
                m_id = re.search(r'tvg-id="([^"]+)"', canal["extinf"], re.I)
                if m_id:
                    cid = m_id.group(1).strip().lower()
                nombre = normalizar(canal.get("nombre", ""))
                if cid:
                    por_id[cid] = canal
                    por_region[region][cid] = canal
                if nombre:
                    por_nombre[nombre] = canal
        except Exception as e:
            errores += 1
            print(f"  -> No se pudo cargar Pluto propio: {fuente} :: {e}")

    return por_id, por_nombre, por_region, errores


def reemplazar_pluto_tercero_por_propio(lineas, session):
    """
    Reemplaza SOLO entradas Pluto que no usan una URL de nuestras playlists.

    Prioridad:
      1) región indicada por country= en la URL antigua;
      2) channel ID en nuestra lista regional;
      3) channel ID en catálogo global;
      4) nombre normalizado como respaldo.

    Si una URL Pluto de terceros no tiene correspondencia propia, se elimina.
    Todo lo que no sea Pluto se conserva exactamente.
    """
    por_id, por_nombre, por_region, errores_catalogo = cargar_catalogo_pluto_propio(session)

    propias = {canal["url"].strip() for canal in por_id.values()}
    salida = []
    reemplazados = 0
    eliminados_sin_reemplazo = 0
    ya_propios = 0
    no_pluto = 0

    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            salida.append(lineas[i])
            i += 1
            continue

        extinf = lineas[i]
        nombre = extraer_nombre(extinf)
        bloque = [extinf]
        j = i + 1

        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            bloque.append(lineas[j])
            j += 1

        if j >= len(lineas) or not url_es_valida(lineas[j].strip()):
            salida.extend(bloque)
            i = j
            continue

        url = lineas[j].strip()
        bloque.append(url)
        j += 1

        if not es_url_pluto(url):
            salida.extend(bloque)
            no_pluto += 1
            i = j
            continue

        if url in propias:
            salida.extend(bloque)
            ya_propios += 1
            i = j
            continue

        cid = extraer_pluto_id(url)
        m_id = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        if m_id:
            cid = m_id.group(1).strip().lower()

        country = re.search(r'(?:[?&])country=([A-Za-z]{2})', url, re.I)
        region = country.group(1).lower() if country else ""

        reemplazo = None
        if cid and region in por_region:
            reemplazo = por_region[region].get(cid)
        if reemplazo is None and cid:
            reemplazo = por_id.get(cid)
        if reemplazo is None:
            reemplazo = por_nombre.get(normalizar(nombre))

        if reemplazo is None:
            # Regla de seguridad: nunca eliminar un canal existente solo
            # porque la fuente propia no respondió o no lo catalogó.
            # Se conserva el bloque y queda contabilizado para auditoría.
            eliminados_sin_reemplazo += 1
            salida.extend(bloque)
            i = j
            continue

        salida.extend(bloque[:-1])
        salida.append(reemplazo["url"].strip())
        reemplazados += 1
        i = j

    return salida, {
        "reemplazados": reemplazados,
        "eliminados_sin_reemplazo": eliminados_sin_reemplazo,
        "ya_propios": ya_propios,
        "no_pluto": no_pluto,
        "errores_catalogo": errores_catalogo,
    }


def limpiar_pluto_antiguo(lineas, session):
    """
    Elimina SOLO entradas de la principal que coincidan con una entrada
    conocida de las fuentes Pluto antiguas.

    La coincidencia usa URL + nombre normalizado. Esto evita borrar por
    accidente un canal no-Pluto que comparta una URL con una fuente antigua.
    Las fuentes propias se cargan después, por lo que sus URLs pueden entrar
    de nuevo como reemplazo estable.
    """
    firmas_antiguas = defaultdict(set)
    errores = 0
    fuentes_ok = 0

    for fuente in FUENTES_PLUTO_ANTIGUAS:
        try:
            r = session.get(fuente, timeout=30)
            r.raise_for_status()
            canales = parsear_m3u(r.text)
            fuentes_ok += 1
            for canal in canales:
                url = canal["url"].strip()
                nombre = normalizar(canal.get("nombre", ""))
                if url and nombre:
                    firmas_antiguas[url].add(nombre)
        except Exception as e:
            errores += 1
            print(f"  -> No se pudo consultar Pluto antiguo: {fuente} :: {e}")

    if not firmas_antiguas:
        print("  -> No se obtuvo ninguna firma de Pluto antiguo; no se elimina nada.")
        return lineas, 0, errores

    salida = []
    eliminados = 0
    i = 0

    while i < len(lineas):
        if lineas[i].startswith("#EXTINF"):
            extinf = lineas[i]
            nombre = normalizar(extraer_nombre(extinf))
            bloque = [extinf]
            j = i + 1

            while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
                bloque.append(lineas[j])
                j += 1

            if j < len(lineas) and url_es_valida(lineas[j].strip()):
                url = lineas[j].strip()
                bloque.append(url)
                j += 1

                if nombre in firmas_antiguas.get(url, set()):
                    eliminados += 1
                    i = j
                    continue

                salida.extend(bloque)
                i = j
                continue

        salida.append(lineas[i])
        i += 1

    print(
        f"  -> Fuentes Pluto antiguas consultadas correctamente: "
        f"{fuentes_ok}/{len(FUENTES_PLUTO_ANTIGUAS)}"
    )
    return salida, eliminados, errores

def destino_especial_total_otros(nombre, categoria, categorias):
    """Clasifica entradas heredadas de TOTAL/OTROS y evita recrear esas carpetas."""
    texto = normalizar(f"{categoria or ''} {nombre or ''}")
    reglas = [
        (r"\b(anime|animacion|anime station|anime zone)\b", "Anime"),
        (r"\b(infantil|kids|kid|junior|nick jr|rugrats|bob esponja|babyfirst|chiquilines|dreiko)\b", "Infantiles"),
        (r"\b(novela|novelas)\b", "Novelas"),
        (r"\b(series?|csi|drama)\b", "Series"),
        (r"\b(cine|pelicula|peliculas|horrorfy|fmtv)\b", "Cine / Películas"),
        (r"\b(reality|masterchef|survivor|hell.?s kitchen)\b", "Reality"),
        (r"\b(deporte|deportes|sport|sports|velocidad|motorvision|futbol)\b", "Deportes"),
        (r"\b(retro|clasica|clasico)\b", "Retro"),
        (r"\b(paranormal|misterio|misterios|extraterrestre)\b", "Zona Paranormal"),
        (r"\b(investiga|investigacion|cops|forense)\b", "Investigación"),
        (r"\b(documental|documentales|cultural|culturales|saber mas|rt doc)\b", "Documentales y Cultura"),
        (r"\b(quiz|curiosidad|curioso|vida real)\b", "Curiosidad"),
        (r"\b(estilo de vida|paisajes|encantador de perros|autos|cocinando|viajes)\b", "Estilo De Vida"),
        (r"\b(musica|music|musical)\b", "Música"),
        (r"\b(comedia|humor)\b", "Comedia"),
        (r"\b(south park)\b", "South Park"),
        (r"\b(religioso|religiosos|supreme master|ad venir)\b", "Religiosos"),
        (r"\b(noticias|noticia|news|aljazeera|dw |france 24|rt |hispantv|palestine|kan 11|tv5 monde|tvge)\b", "Informativos"),
        (r"\b(fashiontv|fashion)\b", "Fashion"),
        (r"\b(platzi|cloudflare)\b", "Tecnología"),
    ]
    for patron, destino in reglas:
        if re.search(patron, texto):
            encontrado = buscar_categoria_existente(destino, categorias)
            if encontrado:
                return encontrado
    # Países explícitos solo si ya existe su carpeta.
    aliases_pais = {
        "bolivia": "Bolivia", "brasil": "Brasil", "brazil": "Brasil",
        "chile": "CHILE TV", "venezuela": "Venezuela", "el salvador": "El Salvador",
        "guatemala": "Guatemala", "honduras": "Honduras", "costa rica": "Costa Rica",
        "mexico": "México", "colombia": "Colombia", "ecuador": "Ecuador",
        "peru": "Perú", "argentina": "Argentina", "paraguay": "Paraguay",
        "republica dominicana": "República Dominicana", "espana": "España",
    }
    for alias, destino in aliases_pais.items():
        if re.search(rf"\b{re.escape(alias)}\b", texto):
            encontrado = buscar_categoria_existente(destino, categorias)
            if encontrado:
                return encontrado
    return buscar_categoria_existente("GENERAL", categorias)


def limpiar_total_otros_y_sin_nombre(lineas):
    """
    Limpia TOTAL/OTROS definitivamente.
    - Si la misma URL existe en otra carpeta, elimina la copia TOTAL/OTROS.
    - Si TOTAL y OTROS contienen la misma URL, conserva una sola y la reclasifica.
    - Los únicos se reclasifican.
    - Nunca deja ni crea TOTAL/OTROS.
    """
    categorias = categorias_de_lineas(lineas)
    bloques = []
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            i += 1
            continue
        inicio = i
        extinf = lineas[i]
        categoria = extraer_categoria(extinf)
        nombre = extraer_nombre(extinf)
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloques.append({"start":inicio,"end":j+1,"extinf":extinf,"categoria":categoria,"nombre":nombre,"url":lineas[j].strip()})
            i=j+1
        else:
            i=j

    categorias_por_url = defaultdict(set)
    for b in bloques:
        if b["categoria"]:
            categorias_por_url[b["url"]].add(normalizar(b["categoria"]))

    eliminar = set()
    reemplazos = {}
    sin_nombre_eliminados = 0
    duplicados_eliminados = 0
    movidos = defaultdict(int)
    especial_vistos = set()

    for idx,b in enumerate(bloques):
        cat=normalizar(b["categoria"])
        if not b["categoria"]:
            eliminar.add(idx); sin_nombre_eliminados += 1; continue
        if cat not in {"total","otros"}:
            continue

        otras={x for x in categorias_por_url[b["url"]] if x not in {"total","otros"}}
        if otras:
            eliminar.add(idx); duplicados_eliminados += 1; continue

        # Si TOTAL y OTROS comparten URL, conservar solo la primera aparición.
        if b["url"] in especial_vistos:
            eliminar.add(idx); duplicados_eliminados += 1; continue
        especial_vistos.add(b["url"])

        destino=destino_especial_total_otros(b["nombre"],b["categoria"],categorias)
        if destino and normalizar(destino) not in {"total","otros"}:
            reemplazos[idx]=destino; movidos[destino]+=1
        else:
            eliminar.add(idx); duplicados_eliminados += 1

    salida=[]; bloque_idx=0; i=0
    while i<len(lineas):
        if bloque_idx<len(bloques) and i==bloques[bloque_idx]["start"]:
            b=bloques[bloque_idx]; idx=bloque_idx; bloque_idx+=1
            if idx in eliminar:
                i=b["end"]; continue
            if idx in reemplazos:
                salida.append(reemplazar_categoria(b["extinf"],reemplazos[idx]))
                i=b["start"]+1; continue
            salida.extend(lineas[b["start"]:b["end"]]); i=b["end"]; continue
        salida.append(lineas[i]); i+=1

    return salida,{
        "sin_nombre_eliminados":sin_nombre_eliminados,
        "total_otros_duplicados_eliminados":duplicados_eliminados,
        "total_otros_movidos":sum(movidos.values()),
        "movidos_por_categoria":dict(movidos),
    }

def agregar_bloque(canal, destino, urls_globales, bloques):
    url = canal["url"].strip()
    if url in urls_globales:
        return False
    bloques.append({
        "categoria": destino,
        "bloque": construir_bloque(canal, destino),
    })
    urls_globales.add(url)
    return True

def insertar_bloques(lineas, bloques):
    if not bloques:
        return lineas
    resultado = list(lineas)
    agrupados = {}
    for item in bloques:
        clave = normalizar(item["categoria"])
        agrupados.setdefault(clave, {
            "categoria": item["categoria"],
            "bloques": [],
        })
        agrupados[clave]["bloques"].append(item["bloque"])

    posiciones = []
    for datos in agrupados.values():
        rango = encontrar_rango_categoria(resultado, datos["categoria"])
        if rango:
            posiciones.append((rango[1] + 1, datos["bloques"]))
        else:
            # Categoría nueva: se crea al final, sin tocar el orden existente.
            posiciones.append((len(resultado), datos["bloques"]))

    for posicion, bloques_cat in sorted(posiciones, key=lambda x: x[0], reverse=True):
        insertar = []
        for bloque in bloques_cat:
            insertar.extend(bloque)
        resultado[posicion:posicion] = insertar
    return resultado


def reubicar_bloques_pluto_sin_reordenar_principal(lineas):
    """
    Consolida físicamente los bloques Pluto en su carpeta destino.

    IMPORTANTE:
      - Solo se mueven bloques cuyo URL es Pluto.
      - Todo bloque no-Pluto conserva su orden relativo exacto.
      - Dentro de cada carpeta, los Pluto conservan su orden relativo.
      - No se aplica ningún orden global de carpetas.
      - No se cambian URLs, nombres, logos ni metadatos.
    """
    prefijo = []
    bloques = []
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            i += 1
            continue

        inicio = i
        extinf = lineas[i]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloque = lineas[inicio:j + 1]
            bloques.append({
                "lineas": bloque,
                "categoria": extraer_categoria(extinf),
                "url": lineas[j].strip(),
                "original": len(bloques),
            })
            i = j + 1
        else:
            prefijo.extend(lineas[inicio:j])
            i = j

    pluto = [b for b in bloques if es_url_pluto(b["url"])]
    if not pluto:
        return lineas, 0, {}

    no_pluto = [b for b in bloques if not es_url_pluto(b["url"])]

    # Pluto por categoría, manteniendo exactamente el orden original.
    por_categoria = defaultdict(list)
    primera_original = {}
    for b in pluto:
        clave = normalizar(b["categoria"])
        por_categoria[clave].append(b)
        primera_original.setdefault(clave, b["original"])

    # Posición de inserción: después del último bloque NO-Pluto de la
    # categoría. Si la categoría solo contiene Pluto, se conserva la
    # posición aproximada del primer Pluto que había en ella.
    inserciones = []
    for clave, pluto_bloques in por_categoria.items():
        indices_no_pluto = [
            idx for idx, b in enumerate(no_pluto)
            if normalizar(b["categoria"]) == clave
        ]

        if indices_no_pluto:
            posicion = indices_no_pluto[-1] + 1
        else:
            posicion = sum(
                1 for b in no_pluto
                if b["original"] < primera_original[clave]
            )

        inserciones.append((
            posicion,
            primera_original[clave],
            pluto_bloques,
        ))

    # Insertar de atrás hacia adelante para no alterar las posiciones
    # calculadas. En una misma posición se conserva el orden original
    # entre categorías Pluto.
    inserciones.sort(key=lambda x: (x[0], x[1]), reverse=True)
    resultado = list(no_pluto)
    movidos = 0
    por_categoria_movidos = defaultdict(int)

    posiciones_originales = {
        id(b): idx for idx, b in enumerate(bloques)
    }

    for posicion, _, pluto_bloques in inserciones:
        for offset, b in enumerate(pluto_bloques):
            resultado.insert(posicion + offset, b)
            if posiciones_originales[id(b)] != posicion + offset:
                movidos += 1
                por_categoria_movidos[b["categoria"]] += 1

    salida = list(prefijo)
    for b in resultado:
        salida.extend(b["lineas"])

    return salida, movidos, dict(por_categoria_movidos)

PAISES_ORDEN_FINAL = {
    "peru", "bolivia", "argentina", "brasil", "brazil", "colombia",
    "ecuador", "venezuela", "paraguay", "mexico", "espana", "spain",
    "costa rica", "republica dominicana", "el salvador", "guatemala",
    "honduras", "nicaragua", "panama", "cuba", "puerto rico", "uruguay",
}

# Alias de países: evita que "Brasil/Brazil" o "España/Spain" terminen
# en bloques físicos separados. La categoría visible queda en español.
PAISES_CANONICOS = {
    "brazil": "brasil",
    "spain": "espana",
}

# Alias físicos que nunca deben volver a generar carpetas separadas.
CATEGORIAS_CANONICAS = {
    "el salvador - tcs": "el salvador",
    "documentales": "documentales y cultura",
}

def limpiar_extinf_huerfanos(lineas):
    """Elimina EXTINF sin URL causado por bloques consecutivos mal formados."""
    salida = []
    i = 0
    eliminados = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            salida.append(lineas[i])
            i += 1
            continue
        inicio = i
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            salida.extend(lineas[inicio:j + 1])
            i = j + 1
        else:
            eliminados += 1
            i = inicio + 1
    return salida, eliminados


def limpiar_duplicados_globales_y_carpetas_especiales(lineas):
    """
    Auditoría final de integridad:
      - elimina URLs exactas repetidas;
      - Telemundo Noticias y Sky Sports tienen prioridad si una misma URL
        aparece también en otra carpeta;
      - NO reclasifica canales por nombre (CNN, Women's Sports Network, etc.).
    """
    bloques = []
    prefijo = []
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            i += 1
            continue

        inicio = i
        extinf = lineas[i]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloques.append({
                "lineas": lineas[inicio:j + 1],
                "extinf": extinf,
                "categoria": extraer_categoria(extinf),
                "nombre": extraer_nombre(extinf),
                "url": lineas[j].strip(),
                "orden": len(bloques),
            })
            i = j + 1
        else:
            prefijo.extend(lineas[inicio:j])
            i = j

    preferidos = {}
    for b in bloques:
        cat = normalizar(b["categoria"])
        if cat in {"telemundo noticias", "sky sports"}:
            preferidos.setdefault(b["url"], b)

    vistos = set()
    duplicados = 0
    salida = list(prefijo)

    for b in bloques:
        if b["url"] in preferidos and preferidos[b["url"]] is not b:
            duplicados += 1
            continue
        if b["url"] in vistos:
            duplicados += 1
            continue
        vistos.add(b["url"])
        salida.extend(b["lineas"])

    return salida, duplicados, {}


def ordenar_y_normalizar_carpetas(lineas):
    """
    Ordena y normaliza las carpetas de la principal sin cambiar URLs.

    Reglas:
      - CHILE TV queda primero.
      - INFANTIL e INFANTILES se unifican en INFANTILES.
      - TEEN se unifica en INFANTILES.
      - NOTICIAS se unifica en INFORMATIVOS.
      - Las carpetas de países, incluido El Salvador - TCS, quedan al final.
      - XXX+18 queda después de todas las carpetas de países, como último.
      - Dentro de cada carpeta se conserva el orden actual de sus canales.
    """
    bloques = []
    prefijo = []
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            i += 1
            continue

        inicio = i
        extinf = lineas[i]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloques.append({
                "extinf": extinf,
                "nombre": extraer_nombre(extinf),
                "categoria": extraer_categoria(extinf),
                "lineas": lineas[inicio:j + 1],
                "orden": len(bloques),
            })
            i = j + 1
        else:
            prefijo.extend(lineas[inicio:j])
            i = j

    categorias = []
    grupos = {}
    cambios = {
        "infantil_a_infantiles": 0,
        "teen_a_infantiles": 0,
        "noticias_a_informativos": 0,
    }

    # Determinar primero las categorías canónicas existentes.
    cat_infantiles = next(
        (b["categoria"] for b in bloques
         if normalizar(b["categoria"]) == "infantiles"),
        "INFANTILES",
    )
    cat_informativos = next(
        (b["categoria"] for b in bloques
         if normalizar(b["categoria"]) == "informativos"),
        "INFORMATIVOS",
    )

    for b in bloques:
        cat_norm = normalizar(b["categoria"])
        destino = b["categoria"]

        if cat_norm in {"infantil", "infantiles", "teen"}:
            destino = cat_infantiles
            if cat_norm == "infantil":
                cambios["infantil_a_infantiles"] += 1
            elif cat_norm == "teen":
                cambios["teen_a_infantiles"] += 1

        elif cat_norm == "noticias":
            destino = cat_informativos
            cambios["noticias_a_informativos"] += 1

        elif cat_norm == "documentales":
            destino = buscar_categoria_existente("Documentales y Cultura", [x["categoria"] for x in bloques]) or "Documentales y Cultura"

        if destino != b["categoria"]:
            b["extinf"] = reemplazar_categoria(b["extinf"], destino)
            b["lineas"][0] = b["extinf"]
            b["categoria"] = destino

        clave = normalizar(destino)
        # Unificar alias de categorías antes de crear el grupo físico.
        clave_canonica = CATEGORIAS_CANONICAS.get(clave, clave)
        clave_canonica = PAISES_CANONICOS.get(clave_canonica, clave_canonica)
        if clave_canonica != clave:
            nombres_canonicos = {
                "el salvador": "El Salvador",
                "documentales y cultura": "Documentales y Cultura",
                "brasil": "Brasil",
                "espana": "España",
            }
            destino_canonico = nombres_canonicos.get(clave_canonica, destino)
            b["extinf"] = reemplazar_categoria(b["extinf"], destino_canonico)
            b["lineas"][0] = b["extinf"]
            b["categoria"] = destino_canonico
            destino = destino_canonico
            clave = clave_canonica

        if clave not in grupos:
            grupos[clave] = {
                "categoria": destino,
                "bloques": [],
                "primera_orden": b["orden"],
            }
            categorias.append(clave)
        grupos[clave]["bloques"].append(b)

    # Orden maestro ACTUAL. Se obtuvo de la última estructura correcta
    # antes de la reorganización accidental. NO usar la lista antigua como
    # plantilla de carpetas: solo sirve para auditar dónde pertenece cada canal.
    ORDEN_MAESTRO_ACTUAL = [
        "chile tv",
        "anime",
        "competencia",
        "infantiles",
        "entretenimiento",
        "doramas / asia",
        "comedia",
        "south park",
        "entretenimiento / cine / series",
        "entretenimiento premium",
        "cine / peliculas premium",
        "cine / peliculas",
        "cine",
        "deportes",
        "musica",
        "retro",
        "reality",
        "series",
        "fashion",
        "general",
        "telemundo noticias",
        "documentales y cultura",
        "informativos",
        "fifa+",
        "sky sports",
        "tigo sports / fox",
        "curiosidad",
        "dsports",
        "fox sports",
        "win sports",
        "movistar deportes",
        "espn",
        "religiosos",
        "tv chichicasteca",
        "canela tv",
        "freetv",
        "sony channels",
        "rakuten tv",
        "lg channels",
        "run:time tv",
        "tecnologia",
        "cultura",
        "zona paranormal",
        "investigacion",
        "novelas",
        "estilo de vida",
    ]
    orden_indice = {cat: i for i, cat in enumerate(ORDEN_MAESTRO_ACTUAL)}

    # Los países NO se ordenan con el orden antiguo: se mandan todos al
    # final conservando entre ellos el orden de primera aparición ACTUAL.
    # XXX+18 queda absolutamente al final.
    el_salvador_orden = min((g["primera_orden"] for g in grupos.values() if normalizar(g["categoria"]).startswith("el salvador")), default=10**9)

    def prioridad(cat_key, primera_orden):
        if cat_key in orden_indice:
            return (10, orden_indice[cat_key])
        if cat_key.startswith("el salvador"):
            return (100, el_salvador_orden)
        if cat_key in PAISES_ORDEN_FINAL:
            return (100, primera_orden)
        if cat_key.startswith("xxx"):
            return (110, 0)
        return (50, primera_orden)

    grupos_ordenados = sorted(
        grupos.values(),
        key=lambda g: prioridad(normalizar(g["categoria"]), g["primera_orden"]),
    )

    salida = list(prefijo)
    for grupo in grupos_ordenados:
        for b in grupo["bloques"]:
            salida.extend(b["lineas"])

    return salida, cambios


def main():
    print("=" * 72)
    print("        ALIMENTADOR / COMPLEMENTADOR DE LA PRINCIPAL")
    print("=" * 72)

    if not PRINCIPAL.exists():
        print(f"ERROR: no existe: {PRINCIPAL}")
        raise SystemExit(1)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    lineas = PRINCIPAL.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    total_inicial = sum(1 for x in lineas if x.startswith("#EXTINF"))

    # 1) Pluto: sustituir automáticamente cualquier enlace de terceros
    # por nuestra URL vigente. Solo se elimina un Pluto tercero cuando no
    # existe reemplazo propio; los canales no-Pluto no se tocan.
    lineas, pluto_reemplazo = reemplazar_pluto_tercero_por_propio(
        lineas,
        session,
    )
    pluto_errores = pluto_reemplazo.get("eliminados_sin_reemplazo", 0)

    # 2) Pluto: sincronizar las carpetas de los canales que YA estaban
    # en la principal con la categoría declarada por nuestras fuentes.
    # Solo cambia group-title; no elimina ni cambia URLs.
    (
        lineas,
        pluto_reubicados,
        pluto_reubicados_errores,
        pluto_reubicados_por_categoria,
    ) = reclasificar_pluto_existente(lineas, session)

    # 3) Pluto Brasil: corregir también las entradas que ya existían.
    # La regla aplica a TODO Pluto Brasil, no solo a los canales nuevos.
    lineas, pluto_brasil_movidos, pluto_brasil_errores = mover_pluto_brasil_a_brasil(
        lineas,
        session,
    )

    # 4) Pluto: una sola entrada por channel ID en toda la principal.
    # Conserva la primera aparición y elimina copias regionales del mismo
    # canal, aunque tengan URLs Pluto distintas.
    lineas, pluto_duplicados_existentes = deduplicar_pluto_existente(lineas)

    # 5) Limpieza de TOTAL, OTROS y categoría vacía.
    lineas, limpieza = limpiar_total_otros_y_sin_nombre(lineas)

    categorias = categorias_de_lineas(lineas)
    urls_globales = mapa_urls_principal(lineas)

    # IMPORTANTE: NO deduplicar Pluto por channel ID.
    # Una misma señal puede tener enlaces regionales distintos (LATAM/ES/CL/AR/MX).
    # La regla del proyecto es no repetir el MISMO enlace de acceso; por eso
    # agregar_bloque() controla únicamente la URL exacta.
    ids_pluto_fuentes = set()
    urls_pluto_fuentes_por_id = defaultdict(set)
    canales_pluto_fuentes_por_id = defaultdict(list)

    bloques_nuevos = []
    agregados_normales = 0
    agregados_pluto = 0
    omitidos_duplicados = 0
    errores = pluto_errores

    # --------------------------------------------------------
    # FUENTES COLABORADORAS
    # --------------------------------------------------------
    for i, fuente in enumerate(FUENTES, 1):
        print(f"\n[FUENTE {i}/{len(FUENTES)}] {fuente}")
        try:
            r = session.get(fuente, timeout=30)
            r.raise_for_status()
            canales = parsear_m3u(r.text)
            pais_fuente = next(
                (pais for clave, pais in PAIS_POR_FUENTE.items()
                 if clave.lower() in fuente.lower()),
                None,
            )
            fuente_es_iptvsv = es_fuente_iptvsv(fuente)

            nuevos = 0
            omitidos_regla_especial = 0
            for canal in canales:
                if fuente_es_iptvsv:
                    destino = determinar_destino_iptvsv(
                        canal.get("categoria", ""),
                        canal.get("nombre", ""),
                        categorias,
                    )
                    if destino is None:
                        omitidos_regla_especial += 1
                        continue
                else:
                    destino = determinar_destino(
                        canal.get("categoria", ""),
                        canal.get("nombre", ""),
                        pais_fuente,
                        categorias,
                    )

                # Nunca crear TOTAL/OTROS. Si una fuente antigua los
                # declara, intentar clasificar por nombre; si no hay destino
                # seguro, se omite para no contaminar la principal.
                if not destino and normalizar(canal.get("categoria", "")) in {"total", "otros"}:
                    destino = destino_especial_total_otros(
                        canal.get("nombre", ""),
                        canal.get("categoria", ""),
                        categorias,
                    )
                if not destino or normalizar(destino) in {"total", "otros"}:
                    continue

                if agregar_bloque(canal, destino, urls_globales, bloques_nuevos):
                    agregados_normales += 1
                    nuevos += 1
                else:
                    omitidos_duplicados += 1
            print(f"  -> nuevos: {nuevos}")
            if fuente_es_iptvsv and omitidos_regla_especial:
                print(f"  -> IPTVSV omitidos por regla especial (país genérico): {omitidos_regla_especial}")
        except Exception as e:
            errores += 1
            print(f"  -> ERROR: {e}")

    # --------------------------------------------------------
    # PLUTO: proceso independiente.
    # --------------------------------------------------------
    print("\n" + "=" * 72)
    print("PLUTO — SOLO FUENTES PROPIAS")
    print("=" * 72)

    for i, fuente in enumerate(FUENTES_PLUTO, 1):
        print(f"\n[PLUTO {i}/{len(FUENTES_PLUTO)}] {fuente}")
        try:
            r = session.get(fuente, timeout=30)
            r.raise_for_status()
            canales = parsear_m3u(r.text)
            nuevos = 0
            sin_categoria = 0

            for canal in canales:
                destino = determinar_destino_pluto(
                    canal.get("categoria", ""),
                    canal.get("nombre", ""),
                    categorias,
                )

                if not destino:
                    # No crear carpetas genéricas Pluto TV ni categorías vacías.
                    sin_categoria += 1
                    continue

                identidad = identidad_pluto(canal.get("extinf", ""), canal.get("url", ""))
                if identidad:
                    ids_pluto_fuentes.add(identidad)
                    urls_pluto_fuentes_por_id[identidad].add(canal.get("url", "").strip())
                    canales_pluto_fuentes_por_id[identidad].append(canal)

                # La deduplicación de Pluto se hace SOLO por URL exacta.
                # No se descartan variantes regionales por compartir channel ID.
                if agregar_bloque(canal, destino, urls_globales, bloques_nuevos):
                    agregados_pluto += 1
                    nuevos += 1
                else:
                    omitidos_duplicados += 1

            print(f"  -> nuevos: {nuevos}")
            if sin_categoria:
                print(f"  -> sin categoría: {sin_categoria}")
        except Exception as e:
            errores += 1
            print(f"  -> ERROR: {e}")

    # 6) Insertar primero los canales nuevos dentro de sus carpetas existentes.
    # Las categorías nuevas se crean al final; nunca se reordena la principal.
    lineas = insertar_bloques(lineas, bloques_nuevos)

    # 7) Consolidar físicamente SOLO Pluto. Esto elimina bloques Pluto
    # intercalados entre categorías ajenas sin mover ningún bloque no-Pluto.
    (
        lineas,
        pluto_movidos_fisicamente,
        pluto_movidos_fisicamente_por_categoria,
    ) = reubicar_bloques_pluto_sin_reordenar_principal(lineas)

    # 8) Limpieza de seguridad: nunca conservar EXTINF sin URL.
    lineas, extinf_huerfanos_eliminados = limpiar_extinf_huerfanos(lineas)

    # 9) Auditoría/normalización FINAL: consolida las carpetas y aplica
    # exclusivamente el orden maestro ACTUAL. La lista antigua no se usa
    # para volver a imponer un orden histórico.
    lineas, cambios_orden = ordenar_y_normalizar_carpetas(lineas)

    # 10) Auditoría final: exact-URL dedupe y limpieza de carpetas especiales.
    (
        lineas,
        duplicados_limpieza_final,
        movimientos_especiales,
    ) = limpiar_duplicados_globales_y_carpetas_especiales(lineas)

    # La limpieza puede vaciar bloques o mover canales, por lo que se vuelve
    # a aplicar el orden maestro una sola vez, sin tocar el orden interno.
    lineas, cambios_orden_final = ordenar_y_normalizar_carpetas(lineas)
    for clave, valor in cambios_orden_final.items():
        if isinstance(valor, int):
            cambios_orden[clave] = cambios_orden.get(clave, 0) + valor

    orden_carpetas = cambios_orden

    # 11) Validación final de URLs duplicadas globales.
    vistos = set()
    duplicados_finales = 0
    for linea in lineas:
        u = linea.strip()
        if url_es_valida(u):
            if u in vistos:
                duplicados_finales += 1
            vistos.add(u)

    # VALIDACIÓN BLOQUEANTE ANTES DE ESCRIBIR LA PRINCIPAL.
    # Si falla, el workflow se detiene y NO publica una lista incompleta.
    categorias_finales = []
    bloques_finales = []
    categoria_actual = None
    for linea_final in lineas:
        if not linea_final.startswith("#EXTINF"):
            continue
        cat_final = extraer_categoria(linea_final)
        if cat_final != categoria_actual:
            bloques_finales.append(cat_final)
            categoria_actual = cat_final
        categorias_finales.append(normalizar(cat_final))

    prohibidas = {"pluto tv", "total", "otros"}
    presentes_prohibidas = sorted(set(categorias_finales) & prohibidas)
    if presentes_prohibidas:
        raise RuntimeError(
            "VALIDACION DE CARPETAS FALLIDA: siguen presentes "
            + ", ".join(presentes_prohibidas)
        )

    repetidas_bloques = [
        cat for cat in set(bloques_finales)
        if bloques_finales.count(cat) > 1
    ]
    if repetidas_bloques:
        raise RuntimeError(
            "VALIDACION DE BLOQUES FALLIDA: categorías físicas repetidas: "
            + ", ".join(sorted(repetidas_bloques))
        )

    if not lineas or not any(x.startswith("#EXTINF") for x in lineas):
        raise RuntimeError("VALIDACION FALLIDA: la principal quedó sin canales.")

    texto_final = "\n".join(lineas)
    if not texto_final.endswith("\n"):
        texto_final += "\n"

    PRINCIPAL.write_text(
        texto_final,
        encoding="utf-8",
        newline="\n",
    )

    total_final = sum(1 for x in lineas if x.startswith("#EXTINF"))

    # BLOQUEO DE SEGURIDAD: ninguna señal Pluto presente en las fuentes propias
    # puede desaparecer silenciosamente por una deduplicación por ID.
    ids_pluto_finales = set()
    for i_final, linea_final in enumerate(lineas):
        if linea_final.startswith("#EXTINF"):
            j_final = i_final + 1
            while j_final < len(lineas) and lineas[j_final].startswith("#"):
                j_final += 1
            if j_final < len(lineas) and url_es_valida(lineas[j_final].strip()):
                identidad_final = identidad_pluto(linea_final, lineas[j_final].strip())
                if identidad_final:
                    ids_pluto_finales.add(identidad_final)

    urls_finales = {
        linea_final.strip()
        for linea_final in lineas
        if url_es_valida(linea_final.strip())
    }

    # AUTORREPARACIÓN PLUTO: si una identidad fuente desapareció durante
    # alguna limpieza posterior, reinsertar una representación válida de la
    # misma fuente antes de declarar la principal incompleta.
    ids_pluto_finales_pre = set()
    for i_pre, linea_pre in enumerate(lineas):
        if linea_pre.startswith("#EXTINF"):
            j_pre = i_pre + 1
            while j_pre < len(lineas) and lineas[j_pre].startswith("#"):
                j_pre += 1
            if j_pre < len(lineas) and url_es_valida(lineas[j_pre].strip()):
                identidad_pre = identidad_pluto(linea_pre, lineas[j_pre].strip())
                if identidad_pre:
                    ids_pluto_finales_pre.add(identidad_pre)

    reparados_pluto = 0
    for identidad, canales_fuente in canales_pluto_fuentes_por_id.items():
        if identidad in ids_pluto_finales_pre:
            continue
        canal_fuente = next(
            (c for c in canales_fuente if c.get("url", "").strip() not in urls_finales),
            None,
        )
        if not canal_fuente:
            continue
        destino_fuente = determinar_destino_pluto(
            canal_fuente.get("categoria", ""),
            canal_fuente.get("nombre", ""),
            categorias_de_lineas(lineas),
        )
        if not destino_fuente:
            continue
        extinf_reparado = reemplazar_categoria(
            canal_fuente.get("extinf", ""),
            destino_fuente,
        )
        bloque_reparado = [extinf_reparado]
        bloque_reparado.extend(canal_fuente.get("extras", []))
        bloque_reparado.append(canal_fuente.get("url", "").strip())
        lineas.extend(bloque_reparado)
        urls_finales.add(canal_fuente.get("url", "").strip())
        reparados_pluto += 1

    if reparados_pluto:
        lineas, _ = deduplicar_pluto_existente(lineas)
        lineas, _ = ordenar_y_normalizar_carpetas(lineas)
        urls_finales = {
            linea_final.strip()
            for linea_final in lineas
            if url_es_valida(linea_final.strip())
        }

    ids_pluto_faltantes = {
        identidad
        for identidad in ids_pluto_fuentes
        if identidad not in ids_pluto_finales
        and not (
            urls_pluto_fuentes_por_id.get(identidad, set()) & urls_finales
        )
    }
    if ids_pluto_faltantes:
        raise RuntimeError(
            "VALIDACION PLUTO FALLIDA: faltan "
            f"{len(ids_pluto_faltantes)} identidades de las fuentes propias "
            "sin una URL equivalente conservada. No se permite publicar "
            "una principal incompleta."
        )

    print("\n" + "=" * 72)
    print("RESUMEN")
    print("=" * 72)
    print(f"Canales iniciales:                 {total_inicial}")
    print(f"Pluto terceros reemplazados:         {pluto_reemplazo["reemplazados"]}")
    print(f"Pluto terceros sin reemplazo:        {pluto_reemplazo["eliminados_sin_reemplazo"]}")
    print(f"Pluto ya propios conservados:        {pluto_reemplazo["ya_propios"]}")
    print(f"Pluto reubicados por categoría:        {pluto_reubicados}")
    print(f"Errores sincronizando carpetas Pluto:   {pluto_reubicados_errores}")
    print(f"Pluto duplicados por URL exacta:       {pluto_duplicados_existentes}")
    print(f"Pluto bloques reubicados físicamente: {pluto_movidos_fisicamente}")
    print(f"Pluto Brasil movidos a carpeta Brasil: {pluto_brasil_movidos}")
    print(f"Errores al revisar Pluto Brasil:       {pluto_brasil_errores}")
    print(f"Sin categoría eliminados:           {limpieza['sin_nombre_eliminados']}")
    print(f"TOTAL/OTROS duplicados eliminados:  {limpieza['total_otros_duplicados_eliminados']}")
    print(f"TOTAL/OTROS reclasificados:          {limpieza['total_otros_movidos']}")
    print(f"Canales colaborador agregados:      {agregados_normales}")
    print(f"Canales Pluto propios agregados:    {agregados_pluto}")
    print(f"Duplicados omitidos al agregar:     {omitidos_duplicados}")
    print(f"Duplicados exactos eliminados en auditoría final: {duplicados_limpieza_final}")
    print(f"Duplicados finales detectados:      {duplicados_finales}")
    print(f"Fuentes con error:                  {errores}")
    print(f"Canales finales:                    {total_final}")
    print(f"Infantil -> INFANTILES:              {orden_carpetas['infantil_a_infantiles']}")
    print(f"Teen -> INFANTILES:                  {orden_carpetas['teen_a_infantiles']}")
    print(f"Noticias -> INFORMATIVOS:             {orden_carpetas['noticias_a_informativos']}")
    if movimientos_especiales:
        print("\nCARPETAS ESPECIALES corregidas:")
        for cat, cantidad in sorted(movimientos_especiales.items()):
            print(f"  - {cat}: {cantidad} canales")

    if pluto_movidos_fisicamente_por_categoria:
        print("\nPLUTO reubicados físicamente por carpeta:")
        for cat, cantidad in sorted(pluto_movidos_fisicamente_por_categoria.items()):
            print(f"  - {cat}: {cantidad} canales")

    if limpieza["movidos_por_categoria"]:
        print("\nTOTAL/OTROS movidos por categoría:")
        for cat, cantidad in sorted(limpieza["movidos_por_categoria"].items()):
            print(f"  - {cat}: {cantidad}")

    print("\nREGLAS ACTIVAS:")
    print("  - La principal conserva su orden existente.")
    print("  - IPTVSV.m3u usa reglas propias y NO hereda ninguna regla de Pluto.")
    print("  - IPTVSV: no crea/alimenta carpetas-país genéricas; se respetan solo excepciones explícitas.")
    print("  - Dedupe global por URL para todas las fuentes; IPTVSV no usa dedupe por channel ID de Pluto.")
    print("  - Auditoría final: una URL exacta solo puede quedar una vez en toda la principal.")
    print("  - Telemundo Noticias y Sky Sports tienen prioridad sobre otras carpetas cuando coincide la misma URL.")
    print("  - Pluto: las carpetas existentes se sincronizan con la categoría de la fuente propia.")
    if pluto_reubicados_por_categoria:
        for cat, cantidad in sorted(pluto_reubicados_por_categoria.items()):
            print(f"      * {cat}: {cantidad} canales reubicados")
    print("  - Pluto: una sola entrada por channel ID global; mismo nombre con ID distinto se conserva.")
    print("  - No se eliminan canales existentes salvo limpieza explícita:")
    print("      * Pluto antiguo")
    print("      * categoría sin nombre")
    print("      * duplicados dentro de TOTAL/OTROS")
    print("  - TOTAL/OTROS únicos se reclasifican cuando es posible.")
    print("  - Categorías nuevas solo se agregan al final.")
    print("  - Pluto antiguo se elimina antes de cargar Pluto propio.")
    print("  - Pluto propio usa exclusivamente FUENTES_PLUTO.")
    print("  - CHILE de fuentes normales -> CHILE TV.")
    print("=" * 72)

if __name__ == "__main__":
    main()
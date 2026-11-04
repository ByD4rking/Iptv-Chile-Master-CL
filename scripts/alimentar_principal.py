from pathlib import Path
import re
import unicodedata
import requests
from collections import defaultdict
from sincronizar_canales import sincronizar_enlaces_existentes as _sincronizar_enlaces_existentes

BASE = Path(__file__).resolve().parent.parent
PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"

# Todas las fuentes editables se administran en config/playlist_sources.json.
# Las reglas de importación y categorización permanecen en este script.
from playlist_sources import load_principal_settings

_SOURCE_SETTINGS = load_principal_settings()
_SPECIAL_SOURCES = _SOURCE_SETTINGS["special_sources"]
FUENTE_IPTVSV = _SPECIAL_SOURCES["iptvsv"]
FUENTE_MAGMA = _SPECIAL_SOURCES["magma"]
FUENTE_PLUTO_ALTERNATIVAS = _SPECIAL_SOURCES["pluto_mx_alternatives"]
FUENTE_FEAR_FACTOR = _SPECIAL_SOURCES.get("fear_factor", "")

# Identidad histórica de Pluto TV Anime España; se mantiene fuera de Anime.
PLUTO_ES_ANIME_IDS_HISTORICOS = {"608035b8d8705f0007260287"}

# La principal conserva su orden: estas fuentes solo complementan.
FUENTES = _SOURCE_SETTINGS["sources"]
FUENTES_PLUTO = _SOURCE_SETTINGS["pluto_sources"]
FUENTE_PLUTO_CANONICA = FUENTES_PLUTO[0]
PLUTO_CATEGORIAS_CANONICAS = {"retro", "zona paranormal", "competencia"}

CATEGORIAS_PAIS_NO_AUTORIZADAS = {
    "qatar", "palestina", "corea del norte", "corea del sur", "israel",
    "alemania", "francia", "iran", "rusia", "guinea ecuatorial",
    "estados unidos",
}

FUENTES_PLUTO_CATALOGO = FUENTES_PLUTO
FUENTES_PLUTO_ANTIGUAS = _SOURCE_SETTINGS["legacy_pluto_sources"]

PAIS_POR_FUENTE = {
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


def normalizar_nombre_canal(value):
    """Clave de nombre estable para preservar orden entre fuentes con etiquetas distintas."""
    value = normalizar(value)
    value = re.sub(
        r"\s*(?:\[\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\]|\(\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\))\s*$",
        "",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\s*(?:\[\s*(?:opc(?:ion)?\.?|option)\s*\d+\s*\]|\(\s*(?:opcion|option)\s*\d+\s*\))\s*$",
        "",
        value,
        flags=re.I,
    )
    if not re.match(r"^cartoonito\s+hd\s*\(\s*opc\.?\s*\d+\s*\)$", value, re.I):
        value = re.sub(r"\s*\(\s*opc\.?\s*\d+\s*\)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s*\|\s*(?:cl|co|chile)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s*(?:\[\s*v2\s*\]|\(\s*v2\s*\)|v2)\s*$", " 2", value, flags=re.I)
    value = re.sub(
        r"\s+(?:magna|magma|pluto\s*(?:latam|mx|es))$",
        "",
        value,
        flags=re.I,
    )
    return re.sub(r"[^a-z0-9]+", "", value)
TVG_IDS_INVALIDOS = {"", "-1", "0", "none", "null", "na", "n/a", "undefined"}


def tvg_id_valido(value):
    value = normalizar(value)
    return value if value and value not in TVG_IDS_INVALIDOS else ""


def seleccionar_canal_fear_factor(canales):
    """Selecciona exclusivamente Fear Factor con URL HTTP(S) reproducible."""
    return next((
        canal for canal in canales
        if normalizar(canal.get("nombre", "")) == "fear factor"
        and url_es_valida(canal.get("url", ""))
    ), None)


def determinar_categoria_fear_factor(categorias):
    """Fear Factor pertenece exclusivamente a la carpeta Competencia."""
    destino = buscar_categoria_existente("Competencia", categorias)
    if not destino:
        raise RuntimeError("La categoría Competencia no existe; Fear Factor no se insertará en otra carpeta.")
    return destino

# Correcciones de resolución respaldadas por coincidencia exacta de URL con la M3U de referencia.
# Solo cambia el nombre de presentación; nunca modifica URL, categoría ni logos.
NOMBRES_RESOLUCION_POR_URL = {
    "https://nosignal1.antenaplay.ro/hls/fightbox-hd/index.m3u8": "FightBox HD",
    "http://181.78.79.131:8000/play/a0tj": "Cartoon Network HD",
    "http://190.108.83.69:8000/play/a08g/index.m3u8": "Cartoon Network HD",
    "http://186.148.182.83:8000/play/a09z/index.m3u8": "Cartoon Network SD",
    "http://186.33.26.18:8000/play/a0sv/index.m3u8": "Cartoonito SD",
    "http://181.224.255.210:8001/play/a0pv/index.m3u8?hls": "Discovery Kids SD",
    "http://186.148.196.100:8000/play/a00s": "Discovery Kids SD",
    "http://181.143.237.211:85/tsfile/live/1066_1.m3u8?key=txiptv&playlive=1&authid=0": "Discovery Kids SD",
    "http://205.235.6.29:8000/play/a0zp/index.m3u8?hls": "Disney Channel HD",
    "http://181.224.255.210:8001/play/a0oe/index.m3u8?hls": "Disney Channel HD",
    "http://181.225.190.242:8000/play/a01e": "Disney Channel HD",
    "http://45.186.254.75:8000/play/a0ck/index.m3u8": "Disney Channel HD",
    "http://181.143.237.211:85/tsfile/live/1063_1.m3u8?key=txiptv&playlive=1&authid=0": "Disney Channel SD",
    "http://181.224.255.210:8001/play/a0ny/index.m3u8?hls": "Disney Jr SD",
    "http://205.235.6.29:8000/play/a0zj/index.m3u8?hls": "Disney Jr SD",
    "http://181.224.255.210:8001/play/a0fm/index.m3u8?hls": "Nickelodeon HD",
    "http://181.224.255.210:8001/play/a0ol/index.m3u8?hls": "Nickelodeon HD",
    "http://181.224.200.5:2277/play/a0bm/index.m3u8": "Nickelodeon HD",
    "http://186.33.26.18:8000/play/a0qv/index.m3u8": "Nickelodeon HD",
    "http://181.143.237.211:85/tsfile/live/1071_1.m3u8?key=txiptv&playlive=1&authid=0": "Nickelodeon SD",
    "http://179.60.224.196:8000/play/a0ey/index.m3u8": "Discovery Home & Health SD",
    "http://45.5.117.99:8000/play/a049/index.m3u8": "Discovery Channel SD",
    "http://181.79.86.130:8000/play/a042/index.m3u8": "Discovery Turbo SD",
    "http://181.119.177.253:8000/play/a04k/index.m3u8": "Discovery Turbo SD",
    "http://186.33.47.113:8000/play/a08d/index.m3u8": "History Channel SD",
    "http://201.174.175.3:8000/play/a0ra/index.m3u8?hls": "History Channel SD",
    "http://45.167.2.101:8000/play/a0ny/index.m3u8": "History Channel SD",
    "http://181.224.200.5:2277/play/5684/index.m3u8": "Nat Geo SD",
    "http://179.60.224.196:8000/play/a0f3/index.m3u8": "TLC SD",
    "http://45.186.106.207:8000/play/a01n/index.m3u8": "A&E SD",
    "http://181.143.237.211:85/tsfile/live/1049_1.m3u8?key=txiptv&playlive=1&authid=0": "A&E SD",
    "http://181.119.177.253:8000/play/a04y/index.m3u8": "ESPN 5 SD",
    "http://186.33.0.57:8000/play/a069/index.m3u8": "FOX ESA HD",
    "http://tv.m3uts.xyz/stream/secure/KtMxQzuk/464.m3u8": "FOX Sports Premium HD",
    "http://190.217.66.92:8000/play/a0fh/index.m3u8u?hls": "Win Sports SD",
    "http://200.59.191.177:8000/play/a0p2/index.m3u8?hls": "ESPN 7 HD",
}

def corregir_resoluciones_por_url(lineas):
    """Aplica HD/SD solo cuando la URL coincide exactamente con la M3U de referencia."""
    salida = list(lineas)
    corregidos = 0
    for i, extinf in enumerate(salida):
        if not extinf.startswith("#EXTINF"):
            continue
        j = i + 1
        while j < len(salida) and not salida[j].startswith("#EXTINF"):
            if url_es_valida(salida[j].strip()):
                break
            j += 1
        if j >= len(salida) or not url_es_valida(salida[j].strip()):
            continue
        nombre_base = NOMBRES_RESOLUCION_POR_URL.get(salida[j].strip())
        if not nombre_base:
            continue
        actual = extraer_nombre(extinf)
        # FightBox HD es una señal distinta, no una alternativa numerada.
        if nombre_base == "FightBox HD":
            nuevo = nombre_base
        else:
            opcion = re.search(
                r"(\\s*(?:\\[\\s*(?:opci[oó]n|opc\\.?)\\s*\\d+\\s*\\]|"
                r"\\(\\s*(?:opci[oó]n|opc\\.?)\\s*\\d+\\s*\\))\\s*$)",
                actual,
                re.I,
            )
            nuevo = nombre_base + (opcion.group(1) if opcion else "")
        if nuevo != actual and "," in extinf:
            salida[i] = extinf.rsplit(",", 1)[0] + "," + nuevo
            corregidos += 1
    return salida, corregidos

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
    # Conserva la duración EXTINF existente e inserta group-title después de ella.
    return re.sub(
        r"^(#EXTINF:\s*[^,\s]+)(.*)$",
        lambda match: f'{match.group(1)} group-title="{destino}"{match.group(2)}',
        extinf,
        count=1,
        flags=re.I,
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
        "tv chichicasteca": "Guatemala",  # excepción explícita: destino existente.
        "documentales": "Documentales y Cultura",
        "infantil": "Infantiles",
        "teen": "Infantiles",
        "noticias": "Informativos",
        # IMPORTANTE: NO mezclar categorías deportivas de IPTVSV.
        # Tigo Sports / Fox, FOX Sports, DSports, Win Sports y Movistar Deportes
        # deben conservar su group-title de origen. Solo las excepciones
        # documentadas arriba pueden normalizarse a una carpeta canónica.
    }
    categoria_busqueda = aliases.get(c_norm, categoria)

    # La carpeta especial solo se acepta si YA existe.
    if c_norm == "tv mas importantes de cada pais":
        return buscar_categoria_existente(
            "TV MÁS IMPORTANTES DE CADA PAÍS", categorias
        )

    # Coincidencia con una carpeta existente. Nunca inventar una nueva.
    return buscar_categoria_existente(categoria_busqueda, categorias)

def validar_integridad_iptvsv(lineas, canales, categorias):
    """Barrera bloqueante para impedir que IPTVSV vuelva a perder categorías.

    Reglas:
      - La URL es la identidad del canal para deduplicación.
      - Si una URL de IPTVSV ya existe, su categoría debe coincidir con la
        categoría de origen, salvo alias canónicos explícitos.
      - Una categoría IPTVSV no-país no puede desaparecer de la principal
        mientras la fuente siga aportando canales de esa categoría.
      - Si la misma URL aparece en IPTVSV con categorías distintas, se detiene
        la actualización en lugar de elegir una categoría arbitrariamente.
      - Las categorías-país genéricas siguen excluidas por regla del proyecto.
    """
    por_url = defaultdict(set)
    for canal in canales:
        url = (canal.get("url") or "").strip()
        categoria = (canal.get("categoria") or "").strip()
        if url and categoria:
            por_url[url].add(categoria)

    conflictos_fuente = {
        url: sorted(cats)
        for url, cats in por_url.items()
        if len({normalizar(c) for c in cats}) > 1
    }
    if conflictos_fuente:
        muestra = list(conflictos_fuente.items())[:10]
        raise RuntimeError(
            "IPTVSV BLOQUEADO: una misma URL trae categorías distintas en la fuente: "
            + "; ".join(f"{u} => {cats}" for u, cats in muestra)
        )

    # Construir mapa URL -> categorías actuales de la principal.
    actual_por_url = defaultdict(set)
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            i += 1
            continue
        extinf = lineas[i]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            actual_por_url[lineas[j].strip()].add(extraer_categoria(extinf))
            i = j + 1
        else:
            i = j

    errores = []
    categorias_faltantes = set()
    for categoria in sorted({c.get("categoria", "").strip() for c in canales if c.get("categoria", "").strip()}):
        if es_categoria_pais_generica_iptvsv(categoria):
            continue
        destino = determinar_destino_iptvsv(categoria, "", categorias)
        if not destino:
            categorias_faltantes.add(categoria)

    if categorias_faltantes:
        raise RuntimeError(
            "IPTVSV BLOQUEADO: faltan en la principal categorías de origen "
            "no-país que la fuente sigue usando: "
            + ", ".join(sorted(categorias_faltantes))
        )

    for canal in canales:
        url = (canal.get("url") or "").strip()
        categoria = (canal.get("categoria") or "").strip()
        if not url or not categoria or es_categoria_pais_generica_iptvsv(categoria):
            continue
        destino = determinar_destino_iptvsv(categoria, canal.get("nombre", ""), categorias)
        if not destino:
            continue
        actuales = actual_por_url.get(url, set())
        if not actuales:
            continue
        if any(normalizar(actual) != normalizar(destino) for actual in actuales):
            errores.append(
                f"{url} :: fuente='{categoria}' :: principal={sorted(actuales)} :: esperado='{destino}'"
            )

    if errores:
        muestra = errores[:20]
        raise RuntimeError(
            "IPTVSV BLOQUEADO: se detectaron canales existentes en una "
            "categoría distinta de la fuente. "
            + " | ".join(muestra)
        )

    return {
        "urls_fuente": len(por_url),
        "categorias_faltantes": len(categorias_faltantes),
        "conflictos_fuente": len(conflictos_fuente),
        "errores_categoria": len(errores),
    }


def reclasificar_iptvsv_existente(lineas, canales, categorias):
    """Hace que la categoría declarada por IPTV-SV mande también para URLs ya existentes.

    No duplica enlaces. Solo cambia group-title de una URL que ya estaba en la
    principal. Telemundo Noticias y Sky Sports permanecen protegidos porque
    esas carpetas fueron definidas como canónicas para sus enlaces.
    """
    destino_por_url = {}
    conflictos = 0

    for canal in canales:
        url = (canal.get("url") or "").strip()
        if not url:
            continue
        destino = determinar_destino_iptvsv(
            canal.get("categoria", ""),
            canal.get("nombre", ""),
            categorias,
        )
        if not destino:
            continue
        anterior = destino_por_url.get(url)
        if anterior and normalizar(anterior) != normalizar(destino):
            conflictos += 1
            continue
        destino_por_url[url] = destino

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

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            url = lineas[j].strip()
            bloque.append(url)
            j += 1

            destino = destino_por_url.get(url)
            actual = extraer_categoria(extinf)
            if destino and normalizar(actual) != normalizar(destino):
                bloque[0] = reemplazar_categoria(extinf, destino)
                movidos += 1

        salida.extend(bloque)
        i = j

    return salida, movidos, conflictos

def determinar_destino(categoria, nombre, pais_fuente, categorias):
    texto = normalizar(f"{categoria or ''} {nombre or ''}")

    if pais_fuente == "religiosos":
        return buscar_categoria_existente("RELIGIOSOS", categorias)

    if pais_fuente == "musica":
        return buscar_categoria_existente("MÚSICA", categorias)

    # LATAM NO tiene carpeta propia. Sus canales se redistribuyen
    # según su categoría/nombre hacia la carpeta existente que corresponda.
    # Si no hay una clasificación segura, se omite el canal.
    if pais_fuente == "chile":
        return buscar_categoria_existente("CHILE TV", categorias)

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
        "chile": ["chile"],
    }
    for pais, nombres in aliases.items():
        if any(normalizar(alias) in texto for alias in nombres):
            destino = buscar_categoria_existente(CATEGORIAS_PAIS[pais], categorias)
            if destino:
                return destino

    return encontrar_categoria_tematica(texto, categorias)

def determinar_destino_magma(categoria, nombre, categorias):
    """Clasifica MAGMA usando exclusivamente carpetas ya existentes."""
    aliases = {
        "chile": "CHILE TV",
        "espn": "ESPN",
        "dsports": "DSports",
        "fox sports": "FOX Sports",
        "deportes": "Deportes",
        "cine / peliculas": "Cine / Películas",
        "infantiles": "Infantiles",
        "anime": "Anime",
        "documentales y cultura": "Documentales y Cultura",
        "entretenimiento / cine / series": "Entretenimiento / Cine / Series",
    }
    destino = aliases.get(normalizar(categoria), categoria)
    existente = buscar_categoria_existente(destino, categorias)
    if existente:
        return existente
    return determinar_destino(categoria, nombre, None, categorias)


def canal_excluido_pluto_es(fuente, canal):
    """Aplica exclusiones regionales explícitas sin borrar versiones LATAM."""
    categoria = normalizar(canal.get("categoria", ""))
    extinf = canal.get("extinf", "")
    tvg_name = re.search(r'tvg-name="([^"]*)"', extinf, re.I)
    nombre = normalizar(
        (tvg_name.group(1) if tvg_name else "") + " " +
        (canal.get("nombre") or extraer_nombre(extinf))
    )
    fuente_es = "pluto_es.m3u" in (fuente or "").lower()
    variante_espana = bool(re.search(r"\b(?:españa|spain)\b", nombre))
    pitufo_es = (
        ("pitufo tv" in nombre or "los pitufos" in nombre)
        and bool(re.search(r"\b(?:es|españa|spain)\b", nombre))
    )
    if categoria == "anime" and variante_espana:
        return True
    if pitufo_es:
        return True
    if fuente_es and (categoria == "anime" or "los pitufos" in nombre):
        return True
    return False


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
        return destino_brasil

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

    destino_tematico = encontrar_categoria_tematica(
        f"{categoria} {nombre}",
        categorias,
    )
    return destino_tematico if destino_tematico else None

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
            salida.extend(bloque)
            i = j
            continue

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

def deduplicar_pluto_por_prioridad(lineas, canales_por_id):
    """
    Deduplica Pluto por identidad y aplica prioridad LATAM > ES > MX.

    Si el mismo channel ID aparece en varias fuentes, conserva la representación
    de la primera fuente en FUENTES_PLUTO (LATAM). Si LATAM no lo tiene, conserva
    ES; si tampoco ES lo tiene, conserva MX. La posición física de la primera
    aparición se mantiene para no reordenar innecesariamente la principal.
    """
    prioridad_url = {}
    for identidad, canales in canales_por_id.items():
        if not canales:
            continue
        for canal in canales:
            url = (canal.get("url") or "").strip()
            if url:
                prioridad_url[identidad] = url
                break

    bloques = []
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            bloques.append((lineas[i:i+1], "", "", False))
            i += 1
            continue

        inicio = i
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            j += 1

        bloque = lineas[inicio:j]
        url = ""
        if j > inicio + 1 and url_es_valida(bloque[-1].strip()):
            url = bloque[-1].strip()
        identidad = identidad_pluto(bloque[0], url) if url and es_url_pluto(url) else ""
        bloques.append((bloque, identidad, url, bool(identidad)))
        i = j

    grupos = defaultdict(list)
    for idx, (_, identidad, url, es_pluto_id) in enumerate(bloques):
        if es_pluto_id:
            grupos[identidad].append((idx, url))

    reemplazar_en = {}
    eliminar = set()
    eliminados = 0

    for identidad, items in grupos.items():
        if len(items) <= 1:
            continue
        preferred = prioridad_url.get(identidad, "")
        elegido = next((idx for idx, url in items if preferred and url == preferred), items[0][0])
        primero = items[0][0]
        reemplazar_en[primero] = elegido
        for idx, _ in items:
            if idx != primero:
                eliminar.add(idx)
                eliminados += 1

    salida = []
    for idx, (bloque, identidad, url, es_pluto_id) in enumerate(bloques):
        if idx in eliminar:
            continue
        elegido = reemplazar_en.get(idx)
        if elegido is not None and elegido != idx:
            bloque = bloques[elegido][0]
        salida.extend(bloque)

    return salida, eliminados

def mover_pluto_brasil_a_brasil(lineas, session):
    """Compatibilidad histórica: ya no consulta ni crea una fuente Pluto BR."""
    return lineas, 0, 0

def extraer_pluto_id(url):
    """Obtiene el channel ID de URLs Pluto directas y jmp2.uk/plu-ID."""
    valor = url or ""
    m = re.search(r"/channel[s]?/([a-f0-9]{20,})", valor, re.I)
    if not m:
        m = re.search(r"/plu-([a-f0-9]{20,})", valor, re.I)
    return m.group(1).lower() if m else ""


def identidades_pluto(extinf, url):
    """Devuelve todas las identidades disponibles, no solo la preferida.

    En algunas M3U el tvg-id es un alias EPG y no coincide con el channel ID
    de la URL Pluto. Ambos identificadores deben poder reconocer la misma
    entrada al comprobar cobertura tras la normalización.
    """
    identidades = set()
    match = re.search(r'tvg-id="([^"]+)"', extinf or "", re.I)
    if match and match.group(1).strip():
        identidades.add("id:" + match.group(1).strip().lower())
    channel_id = extraer_pluto_id(url)
    if channel_id:
        identidades.add("id:" + channel_id)
    return identidades


def calcular_ids_pluto_faltantes(ids_requeridos, aliases_fuente, aliases_finales):
    """Exige que cada ID fuente sobreviva por al menos uno de sus alias."""
    return {
        identidad
        for identidad in ids_requeridos
        if not (aliases_fuente.get(identidad, {identidad}) & aliases_finales)
    }


def es_url_pluto(url):
    """Detecta URLs de streaming Pluto sin considerar el dominio."""
    u = (url or "").lower()
    return (
        "pluto.tv" in u
        or ("stitcher" in u and "pluto" in u)
        or ("pluto" in u and ("/channel/" in u or "/channels/" in u))
        or "jmp2.uk/plu-" in u
    )


def obtener_ids_pluto_existentes(lineas):
    """Identifica todos los IDs Pluto ya presentes para excluirlos del guardia de orden normal.

    El reubicador Pluto mueve deliberadamente los bloques Pluto al final de su
    categoría. Esos movimientos no deben confundirse con una reordenación de
    canales normales; el orden relativo de canales no-Pluto sigue protegido.
    """
    ids = set()
    for index, linea in enumerate(lineas):
        if not linea.startswith("#EXTINF"):
            continue
        j = index + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j >= len(lineas):
            continue
        url = lineas[j].strip()
        if not es_url_pluto(url):
            continue
        # El ID de URL y tvg-id pueden ser distintos en fuentes externas.
        # Excluir ambos evita que una reubicación Pluto parezca reordenar un
        # canal normal cuando su tvg-id no coincide con el channel ID.
        channel_id = extraer_pluto_id(url)
        if channel_id:
            ids.add(channel_id)
        match = re.search(r'tvg-id="([^"]+)"', linea, re.I)
        tvg_id = match.group(1).strip().lower() if match else ""
        if tvg_id:
            ids.add(tvg_id)
    return ids


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
                    # LATAM aparece primero en FUENTES_PLUTO y por tanto
                    # gana frente a ES/MX cuando comparten el mismo canal.
                    por_id.setdefault(cid, canal)
                    por_region[region].setdefault(cid, canal)
                if nombre:
                    por_nombre.setdefault(nombre, canal)
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
            nombre = normalizar_nombre_canal(extraer_nombre(extinf))
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
    # Una marca explícita de país tiene prioridad sobre la temática.
    if re.search(r"\b(españa|espana|spain)\b", texto):
        destino_es = buscar_categoria_existente("España", categorias)
        if destino_es:
            return destino_es
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

def sincronizar_enlaces_existentes(lineas, canales_destinados):
    return _sincronizar_enlaces_existentes(
        lineas,
        canales_destinados,
        normalizar=normalizar,
        extraer_nombre=extraer_nombre,
        extraer_categoria=extraer_categoria,
        reemplazar_categoria=reemplazar_categoria,
        url_es_valida=url_es_valida,
    )


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
            # Regla estricta: las fuentes complementan; nunca crean carpetas.
            # Si la categoría no existe en la principal, se omiten esos bloques.
            continue

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
            url_bloque = lineas[j].strip()
            identidad = extraer_pluto_id(url_bloque)
            if not identidad:
                m_identidad = re.search(r'tvg-id="([a-f0-9]{20,})"', extinf, re.I)
                identidad = m_identidad.group(1).lower() if m_identidad else ""
            bloques.append({
                "lineas": bloque,
                "categoria": extraer_categoria(extinf),
                "url": url_bloque,
                "id": identidad,
                "after": [],
                "original": len(bloques),
            })
            i = j + 1
        else:
            prefijo.extend(lineas[inicio:j])
            i = j

    pluto = [b for b in bloques if es_url_pluto(b["url"])]

    # Algunas alternativas MX usan CDN que no contiene "pluto" en la URL.
    # Si su nombre/ID corresponde a un canal base Pluto, se consideran parte
    # del mismo bloque para que no queden separadas en no_pluto.
    ids_base_pluto = {
        b["id"] for b in pluto if b.get("id")
    }
    nombres_base_pluto = {
        (normalizar(b["categoria"]), normalizar(extraer_nombre(b["lineas"][0])))
        for b in pluto
        if not re.search(r"\(OPCIÓN\s+\d+\)$", extraer_nombre(b["lineas"][0]), re.I)
    }
    for bloque in bloques:
        nombre = extraer_nombre(bloque["lineas"][0])
        m_opcion = re.search(r"\s*\(OPCIÓN\s+\d+\)$", nombre, re.I)
        if not m_opcion or bloque in pluto:
            continue
        nombre_base = re.sub(r"\s*\(OPCIÓN\s+\d+\)$", "", nombre, flags=re.I).strip()
        coincide_base = (
            (bloque.get("id") and bloque["id"] in ids_base_pluto)
            or (normalizar(bloque["categoria"]), normalizar(nombre_base)) in nombres_base_pluto
        )
        if coincide_base:
            pluto.append(bloque)

    if not pluto:
        return lineas, 0, {}

    no_pluto = [b for b in bloques if b not in pluto]

    # Agrupa cada OPCIÓN junto a su canal base usando el ID Pluto compartido.
    # Así el siguiente ciclo de actualización no separa las alternativas.
    pluto_principales = []
    for bloque in pluto:
        nombre = extraer_nombre(bloque["lineas"][0])
        es_opcion = bool(re.search(r"\(OPCIÓN\s+\d+\)$", nombre, re.I))
        if es_opcion:
            nombre_base = re.sub(r"\s*\(OPCIÓN\s+\d+\)$", "", nombre, flags=re.I).strip()
            base = next((
                candidato for candidato in pluto
                if candidato is not bloque
                and not re.search(r"\(OPCIÓN\s+\d+\)$", extraer_nombre(candidato["lineas"][0]), re.I)
                and normalizar(candidato["categoria"]) == normalizar(bloque["categoria"])
                and (
                    (bloque.get("id") and candidato.get("id") == bloque.get("id"))
                    or normalizar(extraer_nombre(candidato["lineas"][0])) == normalizar(nombre_base)
                )
            ), None)
            if base is not None:
                base["after"].append(bloque)
                continue
        pluto_principales.append(bloque)

    # Pluto por categoría, manteniendo exactamente el orden original.
    por_categoria = defaultdict(list)
    primera_original = {}
    for b in pluto_principales:
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
        for alternativa in b.get("after", []):
            salida.extend(alternativa["lineas"])

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


def limpiar_pluto_categorias_canonicas(lineas, session):
    """Alinea Retro/Paranormal/Competencia con Pluto LATAM por channel ID."""
    try:
        r = session.get(FUENTE_PLUTO_CANONICA, timeout=30)
        r.raise_for_status()
        fuente = parsear_m3u(r.text)
    except Exception as e:
        print(f"  -> AVISO: no se pudo consultar Pluto LATAM para la limpieza canónica: {e}")
        return lineas, 0, 0

    canonicos = {}
    for canal in fuente:
        cat = normalizar(canal.get("categoria", ""))
        if cat not in PLUTO_CATEGORIAS_CANONICAS:
            continue
        identidad = identidad_pluto(canal.get("extinf", ""), canal.get("url", ""))
        if identidad:
            canonicos.setdefault(identidad, canal.get("categoria", ""))

    if not canonicos:
        return lineas, 0, 0

    salida = []
    eliminados = 0
    movidos = 0
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            salida.append(lineas[i])
            i += 1
            continue

        extinf = lineas[i]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1

        if j >= len(lineas) or not url_es_valida(lineas[j].strip()):
            salida.extend(lineas[i:j])
            i = j
            continue

        bloque = list(lineas[i:j + 1])
        cat = normalizar(extraer_categoria(extinf))

        if cat in PLUTO_CATEGORIAS_CANONICAS and es_url_pluto(lineas[j].strip()):
            identidad = identidad_pluto(extinf, lineas[j].strip())
            destino = canonicos.get(identidad)
            if not destino:
                eliminados += 1
                i = j + 1
                continue
            if normalizar(extraer_categoria(extinf)) != normalizar(destino):
                bloque[0] = reemplazar_categoria(extinf, destino)
                movidos += 1

        salida.extend(bloque)
        i = j + 1

    return salida, eliminados, movidos



def obtener_ids_pluto_canonicos(session):
    """Obtiene los IDs canónicos de Retro/Paranormal/Competencia desde LATAM."""
    ids = set()
    try:
        r = session.get(FUENTE_PLUTO_CANONICA, timeout=30)
        r.raise_for_status()
        for canal in parsear_m3u(r.text):
            if normalizar(canal.get("categoria", "")) not in PLUTO_CATEGORIAS_CANONICAS:
                continue
            identidad = identidad_pluto(canal.get("extinf", ""), canal.get("url", ""))
            if identidad:
                ids.add(identidad)
    except Exception as e:
        print(f"  -> AVISO: no se pudo cargar el catálogo canónico Pluto LATAM: {e}")
    return ids


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

    # Carpetas especiales: solo conservan sus señales propias.
    bloques_filtrados = []
    for b in bloques:
        cat = normalizar(b["categoria"])
        nombre = normalizar(b["nombre"])

        if cat == "telemundo noticias":
            if not (
                nombre.startswith("telemundo noticias")
                or nombre == "telemundo live stream schedule"
            ):
                continue

        if cat == "sky sports":
            if not nombre.startswith("sky sports"):
                continue

        if cat in CATEGORIAS_PAIS_NO_AUTORIZADAS:
            continue

        bloques_filtrados.append(b)

    bloques = bloques_filtrados

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

    # UNIFICACIÓN FIJA: El Salvador TCS + El Salvador -> EL Salvador.
    # Solo actúa si al menos una variante ya existe; nunca crea una carpeta
    # desde cero.
    el_salvador_variantes = {
        normalizar("el salvador"),
        normalizar("el salvador - tcs"),
        normalizar("el salvador tcs"),
    }
    el_salvador_habilitado = any(
        normalizar(b["categoria"]) in el_salvador_variantes
        for b in bloques
    )
    if el_salvador_habilitado:
        for b in bloques:
            if normalizar(b["categoria"]) in el_salvador_variantes:
                b["categoria"] = "EL Salvador"
                b["extinf"] = reemplazar_categoria(b["extinf"], "EL Salvador")
                b["lineas"][0] = b["extinf"]

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
        None,
    )
    cat_informativos = next(
        (b["categoria"] for b in bloques
         if normalizar(b["categoria"]) == "informativos"),
        None,
    )

    for b in bloques:
        cat_norm = normalizar(b["categoria"])
        destino = b["categoria"]

        if cat_norm in {"infantil", "infantiles", "teen"} and cat_infantiles:
            destino = cat_infantiles
            if cat_norm == "infantil":
                cambios["infantil_a_infantiles"] += 1
            elif cat_norm == "teen":
                cambios["teen_a_infantiles"] += 1

        elif cat_norm == "noticias" and cat_informativos:
            destino = cat_informativos
            cambios["noticias_a_informativos"] += 1

        elif cat_norm == "documentales":
            destino_doc = buscar_categoria_existente("Documentales y Cultura", [x["categoria"] for x in bloques])
            if destino_doc:
                destino = destino_doc

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
            existente_canonico = buscar_categoria_existente(destino_canonico, [x["categoria"] for x in bloques])
            if existente_canonico:
                destino_canonico = existente_canonico
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
        "competencia",
        "infantiles",
        "anime",
        "entretenimiento / cine / series",
        "cine / peliculas",
        "entretenimiento",
        "doramas / asia",
        "comedia",
        "south park",
        "entretenimiento premium",
        "cine / peliculas premium",
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
    el_salvador_orden = min((g["primera_orden"] for g in grupos.values() if normalizar(g["categoria"]).startswith("el salvador")), default=10**9)

    def prioridad(cat_key, primera_orden):
        if cat_key in orden_indice:
            return (10, orden_indice[cat_key])
        if cat_key.startswith("el salvador"):
            return (100, el_salvador_orden)
        if cat_key in PAISES_ORDEN_FINAL:
            return (100, primera_orden)
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


def consolidar_bloques_por_categoria(lineas):
    """Fusión final determinista: una sola sección física por categoría."""
    prefijo = []
    grupos = {}
    orden = []
    i = 0

    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not grupos:
                prefijo.append(lineas[i])
            i += 1
            continue

        inicio = i
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloque = lineas[inicio:j + 1]
            categoria = extraer_categoria(lineas[i])
            clave = normalizar(categoria)
            if clave not in grupos:
                grupos[clave] = {"categoria": categoria, "bloques": []}
                orden.append(clave)
            grupos[clave]["bloques"].append(bloque)
            i = j + 1
        else:
            i = j

    salida = list(prefijo)
    for clave in orden:
        for bloque in grupos[clave]["bloques"]:
            salida.extend(bloque)

    return salida, len(orden)


def extraer_bloques_no_pluto_por_url(lineas):
    """Captura el estado inicial no-Pluto para impedir pérdidas accidentales."""
    resultado = {}
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            i += 1
            continue
        inicio = i
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloque = lineas[inicio:j + 1]
            url = lineas[j].strip()
            if not es_url_pluto(url):
                resultado.setdefault(url, bloque)
        i = j + 1 if j < len(lineas) and url_es_valida(lineas[j].strip()) else j
    return resultado


def restaurar_no_pluto_existente(lineas, iniciales):
    """
    Restaura canales históricos que desaparecieron por una limpieza accidental.

    Una URL antigua no se restaura si la misma identidad sigue publicada con
    una URL nueva. Así la autorrenovación de enlaces no vuelve a introducir
    streams obsoletos como duplicados.
    """
    # Compatibilidad: algunos callers históricos y pruebas entregan la M3U
    # completa; el orquestador nuevo entrega el índice URL -> bloque.
    # Normalizar aquí evita AttributeError y mantiene una sola ruta de restauración.
    if isinstance(iniciales, (list, tuple)):
        iniciales = extraer_bloques_no_pluto_por_url(iniciales)
    elif not isinstance(iniciales, dict):
        raise TypeError(
            "iniciales debe ser una M3U (lista de líneas) o un mapa URL -> bloque"
        )

    urls_actuales = mapa_urls_principal(lineas)
    categorias = categorias_de_lineas(lineas)
    bloques_por_categoria = defaultdict(list)
    ids_actuales = set()
    nombres_actuales = defaultdict(set)

    # Índice de identidades ya presentes en la salida actual.
    for bloque_actual in extraer_bloques_no_pluto_por_url(lineas).values():
        extinf_actual = bloque_actual[0]
        match_actual = re.search(r'tvg-id="([^"]+)"', extinf_actual, re.I)
        id_actual = normalizar(match_actual.group(1)) if match_actual and match_actual.group(1).strip() else ""
        nombre_actual = normalizar_nombre_canal(extraer_nombre(extinf_actual))
        categoria_actual = normalizar(extraer_categoria(extinf_actual))
        if id_actual:
            ids_actuales.add(id_actual)
        if nombre_actual:
            nombres_actuales[(categoria_actual, nombre_actual)].add(id_actual)

    restaurados = 0
    for url, bloque in iniciales.items():
        if url in urls_actuales:
            continue

        extinf = bloque[0]
        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        id_anterior = normalizar(match.group(1)) if match and match.group(1).strip() else ""
        nombre_anterior = normalizar_nombre_canal(extraer_nombre(extinf))
        categoria_anterior = normalizar(extraer_categoria(extinf))

        # Una URL primaria antigua no se resucita si el ID sigue presente.
        # Las alternativas explícitas [Opc.N] sí se conservan como opciones independientes.
        es_alternativa = bool(re.search(
            r"\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]|\(\s*(?:opci[oó]n|option)\s*\d+\s*\)",
            extinf,
            re.I,
        ))
        if id_anterior and id_anterior in ids_actuales and not es_alternativa:
            continue

        # Sin ID estable, solo se acepta una coincidencia inequívoca por
        # nombre+categoría y cuando una de las dos versiones carece de ID.
        candidatos = nombres_actuales.get((categoria_anterior, nombre_anterior), set())
        if nombre_anterior and len(candidatos) == 1:
            id_actual = next(iter(candidatos))
            if not id_anterior or not id_actual:
                continue

        categoria_original = extraer_categoria(extinf)
        categoria_normalizada = normalizar(categoria_original)
        # Estas categorías se eliminan mediante reglas explícitas del proyecto;
        # la protección de no-regresión no debe resucitarlas.
        if (
            not categoria_normalizada
            or categoria_normalizada in {"total", "otros", "telemundo noticias", "sky sports"}
            or categoria_normalizada in CATEGORIAS_PAIS_NO_AUTORIZADAS
        ):
            continue

        destino = buscar_categoria_existente(categoria_original, categorias)

        # Si la carpeta histórica ya no existe, conservar el canal en su
        # categoría original al final de la M3U en vez de eliminarlo.
        if not destino:
            aliases = {
                "chile": "CHILE TV",
                "infantil": "INFANTILES",
                "teen": "INFANTILES",
                "noticias": "INFORMATIVOS",
            }
            destino = buscar_categoria_existente(
                aliases.get(normalizar(categoria_original), categoria_original),
                categorias,
            ) or categoria_original

        if not destino:
            continue

        bloque_restaurado = list(bloque)
        bloque_restaurado[0] = reemplazar_categoria(extinf, destino)
        bloques_por_categoria[destino].append(bloque_restaurado)
        urls_actuales.add(url)
        restaurados += 1

    for categoria, bloques in bloques_por_categoria.items():
        rango = encontrar_rango_categoria(lineas, categoria)
        insertar = []
        for bloque in bloques:
            insertar.extend(bloque)
        if not rango:
            # La carpeta original ya no existe en el catálogo actual: reactivar
            # el group-title histórico al final de la playlist.
            lineas.extend(insertar)
            categorias.add(normalizar(categoria))
            continue
        # rango[1] apunta al último EXTINF, no al final del bloque.
        # Avanzar hasta la URL para no insertar metadatos entre EXTINF y stream.
        posicion = rango[1] + 1
        while posicion < len(lineas) and lineas[posicion].startswith("#") and not lineas[posicion].startswith("#EXTINF"):
            posicion += 1
        if posicion < len(lineas) and url_es_valida(lineas[posicion].strip()):
            posicion += 1
        lineas[posicion:posicion] = insertar

    return lineas, restaurados


def firma_orden_canales(lineas):
    """Orden de primera aparición por tvg-id o por grupo/nombre cuando falta."""
    orden = []
    vistos = set()
    for linea in lineas:
        if not linea.startswith("#EXTINF"):
            continue
        match = re.search(r'tvg-id="([^"]+)"', linea, re.I)
        channel_id = tvg_id_valido(match.group(1)) if match and match.group(1).strip() else ""
        if channel_id:
            clave = "id:" + channel_id
        else:
            clave = "name:" + normalizar(extraer_categoria(linea)) + ":" + normalizar_nombre_canal(extraer_nombre(linea))
        if clave != "name::" and clave not in vistos:
            vistos.add(clave)
            orden.append(clave)
    return orden


def restaurar_orden_original_por_categoria(lineas, lineas_anteriores, categorias_reordenables=None, ids_pluto=None):
    """Restaura el orden previo de canales existentes y deja los nuevos al final.

    La principal puede fusionar carpetas o reubicar canales durante la
    normalización. Este paso conserva el orden relativo de todas las URLs que
    ya estaban publicadas, agrega los canales nuevos después y mantiene Pluto
    al final de cada categoría según su regla específica.
    """
    categorias_especiales = {
        normalizar(x) for x in (categorias_reordenables or set())
    }
    ids_pluto = {str(x).strip().lower().removeprefix("id:") for x in (ids_pluto or set())}

    def extraer_bloques(contenido):
        prefijo = []
        bloques = []
        i = 0
        while i < len(contenido):
            if not contenido[i].startswith("#EXTINF"):
                if not bloques:
                    prefijo.append(contenido[i])
                i += 1
                continue
            inicio = i
            j = i + 1
            while j < len(contenido) and contenido[j].startswith("#") and not contenido[j].startswith("#EXTINF"):
                j += 1
            if j < len(contenido) and url_es_valida(contenido[j].strip()):
                extinf = contenido[inicio]
                bloques.append({
                    "categoria": normalizar(extraer_categoria(extinf)),
                    "url": contenido[j].strip(),
                    "lineas": contenido[inicio:j + 1],
                    "orden_actual": len(bloques),
                    "tvg_id": (
                        tvg_id_valido(re.search(r'tvg-id="([^"]+)"', extinf, re.I).group(1))
                        if re.search(r'tvg-id="([^"]+)"', extinf, re.I)
                        else ""
                    ),
                })
                i = j + 1
            else:
                i = j
        return prefijo, bloques

    _, anteriores = extraer_bloques(lineas_anteriores)
    prefijo, actuales = extraer_bloques(lineas)
    if not actuales:
        return lineas

    def identidad(extinf):
        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        channel_id = tvg_id_valido(match.group(1)) if match and match.group(1).strip() else ""
        nombre = normalizar_nombre_canal(extraer_nombre(extinf))
        return channel_id, nombre

    def categoria_canonica(categoria):
        key = normalizar(categoria)
        key = normalizar(CATEGORIAS_CANONICAS.get(key, key))
        key = normalizar(PAISES_CANONICOS.get(key, key))
        return key

    # Índices separados por ID y nombre. El nombre solo sirve de fallback
    # cuando una de las dos versiones carece de tvg-id; dos IDs distintos
    # nunca heredan el orden por compartir una etiqueta.
    orden_por_categoria_id = defaultdict(list)
    orden_por_categoria_nombre = defaultdict(list)
    orden_por_categoria_url = defaultdict(list)
    identidad_anterior = []
    opciones_sin_base = defaultdict(list)
    categorias_con_base = set()

    def registrar_rango_original(categoria_original, channel_id, nombre, index, item):
        if channel_id:
            orden_por_categoria_id[(categoria_original, channel_id)].append(index)
        if nombre:
            orden_por_categoria_nombre[(categoria_original, nombre)].append(index)
        url_original = (item.get("url") or "").strip()
        if url_original:
            orden_por_categoria_url[(categoria_original, url_original)].append(index)

    for index, item in enumerate(anteriores):
        extinf = item["lineas"][0]
        categoria_original = categoria_canonica(extraer_categoria(extinf))
        channel_id, nombre = identidad(extinf)
        identidad_anterior.append((categoria_original, channel_id, nombre, index))
        nombre_original = extraer_nombre(extinf)
        es_alternativa_original = (
            bool(re.search(
                r"(?:\[\s*(?:opc(?:ion)?\.?|option)\s*\d+\s*\]|"
                r"\(\s*(?:opc(?:ion)?\.?|option)\s*\d+\s*\))$",
                nombre_original,
                re.I,
            ))
            and not bool(re.match(
                r"^cartoonito\s+hd\s*\(\s*opc\.?\s*\d+\s*\)$",
                nombre_original,
                re.I,
            ))
        )
        clave_nombre = (categoria_original, nombre)
        if es_alternativa_original:
            opciones_sin_base[clave_nombre].append((index, channel_id, item))
            continue
        categorias_con_base.add(clave_nombre)
        registrar_rango_original(categoria_original, channel_id, nombre, index, item)

    # Si la maestra histórica solo tenía alternativas y no un canal base,
    # la primera opción actúa como ancla de posición. Si sí existía base, las
    # alternativas nunca adelantan el grupo respecto de ese canal principal.
    for clave_nombre, opciones in opciones_sin_base.items():
        if clave_nombre in categorias_con_base or not opciones:
            continue
        index, channel_id, item = min(opciones, key=lambda value: value[0])
        registrar_rango_original(clave_nombre[0], channel_id, clave_nombre[1], index, item)

    grupos = {}
    orden_grupos = []
    for bloque in actuales:
        categoria = bloque["categoria"]
        if categoria not in grupos:
            grupos[categoria] = []
            orden_grupos.append(categoria)
        grupos[categoria].append(bloque)

    salida = list(prefijo)
    for categoria in orden_grupos:
        bloques = grupos[categoria]
        if categoria in categorias_especiales:
            ordenados = bloques
        else:
            es_bloque_pluto = lambda b: (
                es_url_pluto(b["url"])
                or (b.get("tvg_id") and b["tvg_id"] in ids_pluto)
                or (extraer_pluto_id(b["url"]) in ids_pluto)
            )
            pluto = [b for b in bloques if es_bloque_pluto(b)]
            normales = [b for b in bloques if not es_bloque_pluto(b)]
            for bloque in normales:
                extinf = bloque["lineas"][0]
                categoria_actual = categoria_canonica(extraer_categoria(extinf))
                channel_id, nombre = identidad(extinf)
                # La URL exacta es la identidad más fuerte para conservar posición:
                # el proveedor puede cambiar tvg-id o corregir el nombre visible.
                url_candidates = orden_por_categoria_url.get(
                    (categoria_actual, bloque["url"].strip()),
                    [],
                ) if bloque.get("url") else []
                ranks = url_candidates if len(url_candidates) == 1 else []
                if not ranks:
                    ranks = (
                        list(orden_por_categoria_id.get((categoria_actual, channel_id), []))
                        if channel_id else []
                    )
                if ranks:
                    # Un tvg-id puede ser reasignado por una fuente aunque solo
                    # exista una aparición histórica. El ID por sí solo no basta:
                    # exige que también coincida el nombre normalizado.
                    coincidencias_id_nombre = [
                        idx for idx in ranks
                        if identidad_anterior[idx][2] == nombre
                    ]
                    ranks = (
                        [min(coincidencias_id_nombre)]
                        if coincidencias_id_nombre
                        else []
                    )
                if nombre:
                    candidates = orden_por_categoria_nombre.get((categoria_actual, nombre), [])
                    sin_id = [
                        idx for idx in candidates
                        if not identidad_anterior[idx][1]
                    ]
                    if sin_id:
                        # Si una fuente añadió tvg-id a un canal histórico que
                        # ya existía sin ID, conserva la primera posición por
                        # nombre. El ID puede aparecer más tarde en la maestra
                        # como otra URL del mismo canal.
                        ranks = [min([*ranks, *sin_id])] if ranks else [min(sin_id)]
                    elif not ranks and len(candidates) == 1:
                        # Si el nombre es único, permite conservar orden aunque
                        # la fuente haya cambiado el tvg-id.
                        ranks = candidates
                # Cuando hay homónimos/variantes sin ID (p. ej. Golden HD/SD),
                # la URL exacta es una identidad inequívoca y conserva el orden
                # histórico sin confundir canales que comparten nombre base.
                if not ranks and bloque.get("url"):
                    url_candidates = orden_por_categoria_url.get(
                        (categoria_actual, bloque["url"].strip()),
                        [],
                    )
                    if len(url_candidates) == 1:
                        ranks = url_candidates
                bloque["orden_original"] = min(ranks) if ranks else None
            existentes = [b for b in normales if b["orden_original"] is not None]
            nuevos = [b for b in normales if b["orden_original"] is None]
            existentes.sort(key=lambda b: b["orden_original"])
            # Mantener el orden actual entre los canales nuevos y entre los Pluto.
            ordenados = existentes + nuevos + pluto
        for bloque in ordenados:
            salida.extend(bloque["lineas"])

    return salida


def validar_orden_canales(
    lineas_anteriores,
    lineas_nuevas,
    categorias_reordenables=None,
    ids_pluto_omitidos=None,
):
    """Protege el orden relativo de canales normales dentro de cada categoría."""
    categorias_omitidas = {
        normalizar(categoria) for categoria in (categorias_reordenables or set())
    }
    ids_pluto_omitidos = {str(x).strip().lower().removeprefix("id:") for x in (ids_pluto_omitidos or set())}
    avatar_id = "id:6759ee82bd523200083b4f0f"

    # Alias de identidad compartidos entre ambas versiones: si una versión
    # carece de tvg-id y la otra lo añade, el nombre puede mantener la identidad.
    ids_por_nombre = defaultdict(set)
    nombres_por_id = defaultdict(set)
    for contenido in (lineas_anteriores, lineas_nuevas):
        for extinf in contenido:
            if not extinf.startswith("#EXTINF"):
                continue
            match_id = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
            channel_id = tvg_id_valido(match_id.group(1)) if match_id else ""
            nombre = normalizar_nombre_canal(extraer_nombre(extinf))
            if channel_id and nombre:
                ids_por_nombre[nombre].add(channel_id)
                nombres_por_id[channel_id].add(nombre)

    def firmas_por_categoria(lineas):
        resultado = {}
        vistos = {}
        index = 0
        while index < len(lineas):
            linea = lineas[index]
            if not linea.startswith("#EXTINF"):
                index += 1
                continue

            extinf = linea
            j = index + 1
            while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
                j += 1
            url = lineas[j].strip() if j < len(lineas) and url_es_valida(lineas[j].strip()) else ""

            # La restauración coloca Pluto al final de cada categoría por regla
            # propia. No comparar su posición con canales normales, incluso si
            # el ID de la variante externa no quedó incluido en la lista de IDs
            # Pluto protegidos.
            if url and es_url_pluto(url):
                index = j + 1
                continue

            categoria = normalizar(extraer_categoria(extinf))
            nombre_raw = extraer_nombre(extinf)
            nombre = normalizar_nombre_canal(nombre_raw)
            # Avatar cambia deliberadamente desde Anime a Infantiles; hay dos variantes.
            if nombre.startswith("avatar: la leyenda de aang"):
                index = j + 1 if url else index + 1
                continue
            # Detectar la marca de opción sobre el nombre original: la clave
            # normalizada ya elimina [Opc.N], por lo que comprobarla después
            # hacía que la primera alternativa se tomara como canal principal.
            if (
                re.search(
                    r"(?:\[\s*(?:opc(?:ion)?\.?|option)\s*\d+\s*\]|"
                    r"\(\s*(?:opc(?:ion)?\.?|option)\s*\d+\s*\))$",
                    nombre_raw,
                    re.I,
                )
                and not re.match(
                    r"^cartoonito\s+hd\s*\(\s*opc\.?\s*\d+\s*\)$",
                    nombre_raw,
                    re.I,
                )
            ):
                index = j + 1 if url else index + 1
                continue
            match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
            channel_id = tvg_id_valido(match.group(1)) if match and match.group(1).strip() else ""
            if (
                (channel_id and channel_id in ids_pluto_omitidos)
                or (not channel_id and not nombre)
                or (channel_id == avatar_id.removeprefix("id:"))
            ):
                index = j + 1 if url else index + 1
                continue
            if nombre and len(ids_por_nombre.get(nombre, set())) == 1:
                unique_id = next(iter(ids_por_nombre[nombre]))
                # Un ID reutilizado por nombres distintos no es identidad segura.
                key = ("id", unique_id) if nombres_por_id.get(unique_id, set()) == {nombre} else ("name", nombre)
            elif channel_id and nombre:
                key = ("id_name", channel_id, nombre)
            elif channel_id:
                key = ("id", channel_id)
            else:
                key = ("name", nombre)
            vistos_categoria = vistos.setdefault(categoria, set())
            if key not in vistos_categoria:
                vistos_categoria.add(key)
                if key[0] == "id":
                    key_label = "id:" + key[1]
                elif key[0] == "id_name":
                    key_label = "id:" + key[1] + ":name:" + key[2]
                else:
                    key_label = "name:" + categoria + ":" + key[1]
                resultado.setdefault(categoria, []).append({
                    "id": channel_id,
                    "name": nombre,
                    "key": key_label,
                })
            index = j + 1 if url else index + 1
        return resultado

    anterior = firmas_por_categoria(lineas_anteriores)
    actual = firmas_por_categoria(lineas_nuevas)
    for categoria in set(anterior) | set(actual):
        if categoria in categorias_omitidas:
            continue
        old_items = anterior.get(categoria, [])
        new_items = actual.get(categoria, [])
        pairs = []
        used_old = set()
        used_new = set()

        # Primera pasada: coincidencia exacta por tvg-id.
        old_by_id = defaultdict(list)
        new_by_id = defaultdict(list)
        for i, item in enumerate(old_items):
            if item["id"]:
                old_by_id[item["id"]].append(i)
        for i, item in enumerate(new_items):
            if item["id"]:
                new_by_id[item["id"]].append(i)
        for channel_id in set(old_by_id) & set(new_by_id):
            if len(old_by_id[channel_id]) == 1 and len(new_by_id[channel_id]) == 1:
                oi, ni = old_by_id[channel_id][0], new_by_id[channel_id][0]
                # Un tvg-id puede ser reasignado a otro canal. La identidad
                # exacta exige que también coincida el nombre normalizado;
                # si no coincide, la entrada nueva no hereda el orden anterior.
                if old_items[oi]["name"] != new_items[ni]["name"]:
                    continue
                pairs.append((oi, ni))
                used_old.add(oi)
                used_new.add(ni)

        # Fallback por nombre solo si es inequívoco y al menos una versión
        # carece de ID. Dos IDs distintos con el mismo nombre no se mezclan.
        old_by_name = defaultdict(list)
        new_by_name = defaultdict(list)
        for i, item in enumerate(old_items):
            if i not in used_old and item["name"]:
                old_by_name[item["name"]].append(i)
        for i, item in enumerate(new_items):
            if i not in used_new and item["name"]:
                new_by_name[item["name"]].append(i)
        for name in set(old_by_name) & set(new_by_name):
            old_candidates = old_by_name[name]
            new_candidates = new_by_name[name]
            if len(old_candidates) != 1 or len(new_candidates) != 1:
                continue
            oi, ni = old_candidates[0], new_candidates[0]
            if old_items[oi]["id"] and new_items[ni]["id"]:
                continue
            pairs.append((oi, ni))
            used_old.add(oi)
            used_new.add(ni)

        old_order = [oi for oi, _ in sorted(pairs, key=lambda pair: pair[0])]
        new_order = [oi for oi, _ in sorted(pairs, key=lambda pair: pair[1])]
        if old_order != new_order:
            position = next(
                (
                    index for index, (before_index, after_index)
                    in enumerate(zip(old_order, new_order))
                    if before_index != after_index
                ),
                min(len(old_order), len(new_order)),
            )
            before_keys = [old_items[i]["key"] for i in old_order[position:position + 4]]
            after_keys = [old_items[i]["key"] for i in new_order[position:position + 4]]
            raise RuntimeError(
                "ORDEN BLOQUEADO: la actualización reordenó canales dentro de "
                f"la categoría '{categoria}'. Primera diferencia en posición {position}: "
                f"antes={before_keys}; después={after_keys}."
            )


def aplicar_reconexion_por_canal(lineas):
    """Añade directivas opcionales de reconexión a cada entrada no-Pluto.

    Son comentarios M3U/EXTVLCOPT: reproductores compatibles pueden usarlos
    para reabrir la conexión ante cortes transitorios. No cambia URLs, no
    mezcla canales y no se aplica a Pluto porque Pluto ya tiene su proxy propio.
    """
    salida = []
    agregados = 0
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if not linea.startswith("#EXTINF"):
            salida.append(linea)
            i += 1
            continue
        salida.append(linea)
        bloque = []
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            bloque.append(lineas[j])
            j += 1
        es_pluto = any(es_url_pluto(x.strip()) for x in bloque if url_es_valida(x.strip()))
        if not es_pluto:
            tiene_reconexion = False
            tiene_cache = False
            bloque_normalizado = []
            cache_pattern = re.compile(r"^#EXTVLCOPT:network-caching=\d+$", re.I)
            for opcion in bloque:
                valor = opcion.strip()
                if valor.lower() == "#extvlcopt:http-reconnect=true":
                    if not tiene_reconexion:
                        bloque_normalizado.append("#EXTVLCOPT:http-reconnect=true")
                        tiene_reconexion = True
                    continue
                if cache_pattern.fullmatch(valor):
                    if not tiene_cache:
                        bloque_normalizado.append("#EXTVLCOPT:network-caching=5000")
                        tiene_cache = True
                    continue
                bloque_normalizado.append(opcion)
            bloque = bloque_normalizado
            if not tiene_reconexion:
                salida.append("#EXTVLCOPT:http-reconnect=true")
                agregados += 1
            if not tiene_cache:
                salida.append("#EXTVLCOPT:network-caching=5000")
        salida.extend(bloque)
        i = j
    return salida, agregados




def integrar_pluto_mx(lineas, session):
    """Integra Pluto MX como alternativas sin borrar ni reordenar canales existentes."""
    try:
        respuesta_mx = session.get(FUENTE_PLUTO_ALTERNATIVAS, timeout=30)
        respuesta_mx.raise_for_status()
        contenido_mx = respuesta_mx.text or ""
        if not contenido_mx.lstrip().startswith("#EXTM3U"):
            raise ValueError("Pluto MX no devolvió una cabecera M3U válida")
        canales_mx = parsear_m3u(contenido_mx)
        if not canales_mx:
            raise ValueError("Pluto MX devolvió una lista vacía, sin canales")
        respuesta_latam = session.get(FUENTE_PLUTO_CANONICA, timeout=30)
        respuesta_latam.raise_for_status()
        canales_latam = parsear_m3u(respuesta_latam.text or "")
    except Exception as exc:
        # No escribir una M3U sin alternativas MX verificadas.
        # La deduplicación anterior puede haber retirado opciones previas;
        # si la fuente falla, se cancela la actualización completa.
        raise RuntimeError(
            f"No se pudo verificar Pluto MX/LATAM; se cancela la actualización "
            f"para conservar las alternativas existentes: {exc}"
        ) from exc

    def canal_id(canal):
        cid = extraer_pluto_id(canal.get("url", ""))
        if not cid:
            match = re.search(r'tvg-id="([a-f0-9]{20,})"', canal.get("extinf", ""), re.I)
            cid = match.group(1).lower() if match else ""
        return cid

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
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            j += 1
        raw = lineas[inicio:j]
        extinf = raw[0]
        url = next((x.strip() for x in raw[1:] if url_es_valida(x.strip())), "")
        bloques.append({
            "lineas": raw,
            "extinf": extinf,
            "url": url,
            "categoria": extraer_categoria(extinf),
            "nombre": extraer_nombre(extinf),
            "id": canal_id({"extinf": extinf, "url": url}),
            "after": [],
        })
        i = j

    urls = {b["url"] for b in bloques if b["url"]}
    categorias = categorias_de_lineas(lineas)
    latam_por_id = {canal_id(c): c for c in canales_latam if canal_id(c)}
    agregadas = 0
    sin_coincidencia = 0
    bases_nuevas = 0

    def agregar_base(canal, destino):
        nonlocal bases_nuevas
        destino_existente = buscar_categoria_existente(destino, categorias)
        if not destino_existente:
            return None
        extinf = canal.get("extinf", "")
        if re.search(r'group-title="[^"]*"', extinf, re.I):
            extinf = re.sub(
                r'group-title="[^"]*"',
                f'group-title="{destino_existente}"',
                extinf,
                count=1,
                flags=re.I,
            )
        else:
            extinf = extinf.replace(",", f' group-title="{destino_existente}",', 1)
        cid = canal_id(canal)
        if cid:
            if re.search(r'tvg-id="[^"]*"', extinf, re.I):
                extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{cid}"', extinf, count=1, flags=re.I)
            else:
                extinf = re.sub(
                    r"^(#EXTINF:\s*[^,\s]+)(.*)$",
                    lambda match: f'{match.group(1)} tvg-id="{cid}"{match.group(2)}',
                    extinf,
                    count=1,
                    flags=re.I,
                )
        bloque = [extinf]
        bloque.extend(canal.get("extras", []))
        bloque.append(canal.get("url", "").strip())
        nuevo = {
            "lineas": bloque,
            "extinf": extinf,
            "url": canal.get("url", "").strip(),
            "categoria": destino_existente,
            "nombre": extraer_nombre(extinf),
            "id": cid,
            "after": [],
        }
        indices = [
            idx for idx, b in enumerate(bloques)
            if normalizar(b["categoria"]) == normalizar(destino_existente)
        ]
        if not indices:
            return None
        bloques.insert(indices[-1] + 1, nuevo)
        urls.add(nuevo["url"])
        bases_nuevas += 1
        return nuevo

    def agregar_alternativa(base, canal, numero):
        nonlocal agregadas
        cid = canal_id(canal)
        nombre_base = re.sub(
            r"\s*(?:\[\s*opc(?:ión)?\s*\d+\s*\]|\(\s*opci[oó]n\s*\d+\s*\))\s*$",
            "",
            base["nombre"],
            flags=re.I,
        ).strip()
        extinf = re.sub(r",(.*)$", f",{nombre_base} (OPCIÓN {numero})", base["extinf"], count=1)
        if cid:
            if re.search(r'tvg-id="[^"]*"', extinf, re.I):
                extinf = re.sub(r'tvg-id="[^"]*"', f'tvg-id="{cid}"', extinf, count=1, flags=re.I)
            else:
                extinf = re.sub(
                    r"^(#EXTINF:\s*[^,\s]+)(.*)$",
                    lambda match: f'{match.group(1)} tvg-id="{cid}"{match.group(2)}',
                    extinf,
                    count=1,
                    flags=re.I,
                )
        bloque = [extinf]
        bloque.extend(canal.get("extras", []))
        bloque.append(canal.get("url", "").strip())
        base["after"].append(bloque)
        urls.add(canal.get("url", "").strip())
        agregadas += 1

    for canal in canales_mx:
        url = (canal.get("url") or "").strip()
        if not url or url in urls:
            continue
        cid = canal_id(canal)
        nombre = normalizar(canal.get("nombre", ""))
        base = next((b for b in bloques if cid and b["id"] == cid), None)

        if base is None and cid and cid in latam_por_id:
            canonico = latam_por_id[cid]
            categoria = canonico.get("categoria", "")
            if normalizar(categoria) == "documentales":
                categoria = "Documentales y Cultura"
            base = agregar_base(canonico, categoria)

        if base is None and "cazador de homicidas" in nombre:
            base = next((b for b in bloques if normalizar(b["nombre"]) == "cazador de homicidas"), None)
        if base is None and "claro sports" in nombre:
            base = next((b for b in bloques if "claro sports" in normalizar(b["nombre"])), None)

        if base is not None:
            existentes = sum(1 for b in bloques if cid and b["id"] == cid)
            numero = max(2, existentes + len(base["after"]) + 1)
            agregar_alternativa(base, canal, numero)
            continue

        if "mi obsesion favorita" in nombre:
            destino = "Estilo De Vida"
        elif "cazador de homicidas" in nombre:
            destino = "Investigación"
        elif "claro sports" in nombre:
            destino = "Deportes"
        else:
            sin_coincidencia += 1
            continue

        nuevo = agregar_base(canal, destino)
        if nuevo is None:
            sin_coincidencia += 1
            continue
        if "mi obsesion favorita" not in nombre:
            nuevo["nombre"] = nuevo["nombre"] + " (OPCIÓN 2)"
            nuevo["lineas"][0] = re.sub(r",(.*)$", f",{nuevo['nombre']}", nuevo["extinf"], count=1)
            nuevo["extinf"] = nuevo["lineas"][0]

    salida = list(prefijo)
    for bloque in bloques:
        salida.extend(bloque["lineas"])
        for alternativa in bloque["after"]:
            salida.extend(alternativa)
    return salida, {
        "fuente_ok": True,
        "agregadas": agregadas,
        "bases_nuevas": bases_nuevas,
        "sin_coincidencia": sin_coincidencia,
    }


def cargar_ids_pluto_es_anime(session):
    """Carga identidades Pluto ES de Anime; si la fuente falla, aborta antes de publicar."""
    ids_pluto_es_anime = set(PLUTO_ES_ANIME_IDS_HISTORICOS)
    try:
        respuesta_es = session.get(FUENTES_PLUTO[1], timeout=30)
        respuesta_es.raise_for_status()
        contenido_es = respuesta_es.text or ""
        if "#EXTM3U" not in contenido_es:
            raise ValueError("la respuesta no contiene una cabecera M3U válida")

        canales_es = parsear_m3u(contenido_es)
        canales_anime = [
            canal for canal in canales_es
            if normalizar(canal.get("categoria", "")) == "anime"
        ]
        if not canales_anime:
            raise ValueError("el catálogo Pluto ES no contiene canales de Anime verificables")

        ids_obtenidos_fuente = set()
        canales_sin_identidad = []
        for canal_es in canales_anime:
            identidad_es = extraer_pluto_id(canal_es.get("url", ""))
            if not identidad_es:
                m_es = re.search(
                    r'tvg-id="([a-f0-9]{20,})"',
                    canal_es.get("extinf", ""),
                    re.I,
                )
                identidad_es = m_es.group(1).lower() if m_es else ""
            if identidad_es:
                ids_obtenidos_fuente.add(identidad_es)
            else:
                canales_sin_identidad.append(canal_es.get("nombre") or extraer_nombre(canal_es.get("extinf", "")))

        if canales_sin_identidad:
            muestra = ", ".join(canales_sin_identidad[:5])
            raise ValueError(
                f"el catálogo Pluto ES contiene canales Anime sin identidad verificable: {muestra}"
            )
        ids_pluto_es_anime.update(ids_obtenidos_fuente)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo validar la identidad de Pluto ES; se cancela la actualización "
            "para evitar publicar Anime sin aplicar la exclusión."
        ) from exc

    return ids_pluto_es_anime


def aplicar_ajustes_referencia(lineas, ids_pluto_es_anime=None):
    """Aplica reglas explícitas de Anime, Infantiles y canales de referencia."""
    ids_pluto_es_anime = {str(x).lower() for x in (ids_pluto_es_anime or set())}
    prefijo, bloques, avatar = [], [], []
    prioritarios = {"popeye": [], "los pitufos": [], "heidi": []}
    eliminados_pluto_es_anime = eliminados_pitufos_es = 0
    categorias_existentes = categorias_de_lineas(lineas)
    movidos_espana_desde_anime = 0
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            i += 1
            continue
        inicio = i
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            j += 1
        bloque = list(lineas[inicio:j])
        categoria = normalizar(extraer_categoria(bloque[0]))
        nombre = extraer_nombre(bloque[0])
        url_bloque = next((x.strip() for x in bloque[1:] if url_es_valida(x.strip())), "")
        identidad = extraer_pluto_id(url_bloque)
        if not identidad:
            match_id = re.search(r'tvg-id="([a-f0-9]{20,})"', bloque[0], re.I)
            identidad = match_id.group(1).lower() if match_id else ""
        tvg_name_match = re.search(r'tvg-name="([^"]*)"', bloque[0], re.I)
        nombre_completo = normalizar((tvg_name_match.group(1) if tvg_name_match else "") + " " + nombre)
        url_es = any(marker in url_bloque.lower() for marker in (
            "country=es", "marketingregion=es", "preferredlanguage=es-es"
        ))

        es_pitufos = "los pitufos" in nombre_completo
        if es_pitufos and (
            url_es or bool(re.search(r"\b(?:pluto\s*es|espanol|espana)\b", nombre_completo))
        ):
            eliminados_pitufos_es += 1
            i = j
            continue

        # "Español" en el título no basta para clasificar una entrada como
        # Pluto ES: LATAM/MX también puede publicar audio o títulos en español.
        # Exigir región ES para esos marcadores evita borrar la variante válida
        # cuando comparte identidad con el catálogo español.
        etiqueta_pluto_es = (
            "[pluto es]" in nombre_completo or "pluto es" in nombre_completo
        )
        etiqueta_espanola = "espanol" in nombre_completo or "espana" in nombre_completo
        es_pluto_es = (
            etiqueta_pluto_es
            or (etiqueta_espanola and url_es)
            or bool(identidad and identidad in ids_pluto_es_anime and url_es)
        )
        if categoria == "anime" and es_pluto_es:
            eliminados_pluto_es_anime += 1
            i = j
            continue

        country_match = re.search(r'tvg-country="([^"]*)"', bloque[0], re.I)
        country_value = normalizar(country_match.group(1)) if country_match else ""
        es_canal_de_espana = (
            bool(re.search(r"\b(?:espana|españa|spain)\b", nombre_completo))
            or country_value in {"es", "espana", "spain"}
        )
        if categoria == "anime" and es_canal_de_espana:
            destino_espana = buscar_categoria_existente("España", categorias_existentes)
            if destino_espana:
                bloque[0] = reemplazar_categoria(bloque[0], destino_espana)
                categoria = normalizar(destino_espana)
                movidos_espana_desde_anime += 1

        if "delmi" in nombre_completo and (
            "v2" in nombre_completo or "version 2" in nombre_completo or nombre_completo.endswith(" 2")
        ):
            bloque[0] = reemplazar_categoria(bloque[0], "Anime")
            bloque[0] = re.sub(r",.*$", ",Delmi TV 2", bloque[0])
            bloques.append(bloque)
            i = j
            continue

        nombre_sin_opcion = re.sub(
            r"\s*(?:\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]|\(\s*(?:opci[oó]n|option)\s*\d+\s*\))\s*$",
            "",
            nombre,
            flags=re.I,
        ).strip()
        nombre_kid = normalizar(nombre_sin_opcion)
        kid_key = next((key for key in prioritarios if nombre_kid.startswith(key)), None)
        if kid_key:
            bloque[0] = reemplazar_categoria(bloque[0], "Infantiles")
            prioritarios[kid_key].append(bloque)
        elif normalizar(nombre).startswith("avatar: la leyenda de aang"):
            if categoria != "infantiles":
                bloque[0] = reemplazar_categoria(bloque[0], "Infantiles")
            avatar.append(bloque)
        else:
            bloques.append(bloque)
        i = j

    if avatar:
        posicion = next((
            idx for idx, bloque in enumerate(bloques)
            if bloque[0].startswith("#EXTINF")
            and normalizar(extraer_categoria(bloque[0])) == "infantiles"
            and "baby shark" in normalizar(extraer_nombre(bloque[0]))
        ), None)
        if posicion is None:
            posiciones = [
                idx for idx, bloque in enumerate(bloques)
                if bloque[0].startswith("#EXTINF")
                and normalizar(extraer_categoria(bloque[0])) == "infantiles"
            ]
            if not posiciones:
                raise RuntimeError("No existe Infantiles para ubicar Avatar.")
            posicion = posiciones[-1] + 1
        bloques[posicion:posicion] = avatar

    grupos_prioritarios = [
        bloque for clave in ("popeye", "los pitufos", "heidi") for bloque in prioritarios[clave]
    ]
    if grupos_prioritarios:
        primera_infantil = next((
            idx for idx, bloque in enumerate(bloques)
            if bloque and bloque[0].startswith("#EXTINF")
            and normalizar(extraer_categoria(bloque[0])) in {"infantil", "infantiles"}
        ), len(bloques))
        bloques[primera_infantil:primera_infantil] = grupos_prioritarios

    xumo_url = "https://d4whmvwm0rdvi.cloudfront.net/10007/99951318/hls/master.m3u8?ads.xumo_channelId=99951318&ads.asnw=169843&ads.afid=405342864&ads.sfid=19647852&ads.csid=xumo_web_NBCUAmericanNinjaWarrior_ssai_cro&ads._fw_is_lat=0&ads._fw_us_privacy=&ads._fw_coppa=0&ads._fw_did=a5090924-15b1-4b7f-b6cd-2f06e2ba51e1&ads._fw_vcid2=512116:a5090924-15b1-4b7f-b6cd-2f06e2ba51e1&ads._fw_app_bundle=web.xumo.com&ads._fw_app_store_url=&ads._fw_content_category=&ads._fw_content_genre=&ads._fw_content_language=en&ads._fw_content_rating=&ads._fw_deviceMake=GitHubAction&ads._fw_device_model=PythonScript&ads._fw_deviceType=3-Connected_TV&ads.appVersion=1.0.0&ads.appName=XumoPlay&ads.xumo_contentId=4063&ads.xumo_contentName=NBCUAmericanNinjaWarrior&ads.xumo_providerId=4063&ads.xumo_providerName=NBCUAmericanNinjaWarrior&ads.channelId=99951318"
    xumo_logo = "https://raw.githubusercontent.com/RoqueDJ/iptv-svg/main/1792421696158.png"
    xumo_presente = any(any(linea.strip() == xumo_url for linea in bloque) for bloque in bloques)
    xumo_agregado = 0
    if not xumo_presente:
        posiciones = [
            idx for idx, bloque in enumerate(bloques)
            if bloque[0].startswith("#EXTINF")
            and normalizar(extraer_categoria(bloque[0])) == "competencia"
        ]
        if not posiciones:
            print("  -> AVISO: no existe Competencia en esta M3U de prueba; American Ninja Warrior se omite sin crear categoría.")
        else:
            nuevo = [
                f'#EXTINF:-1 tvg-logo="{xumo_logo}" group-title="Competencia",American Ninja Warrior',
                "#EXTVLCOPT:http-reconnect=true",
                "#EXTVLCOPT:network-caching=5000",
                xumo_url,
            ]
            bloques.insert(posiciones[-1] + 1, nuevo)
            xumo_agregado = 1

    salida = list(prefijo)
    for bloque in bloques:
        salida.extend(bloque)
    print(
        f"Ajustes referencia: Pluto ES Anime retirados={eliminados_pluto_es_anime}; "
        f"Los Pitufos ES retirados={eliminados_pitufos_es}; Avatar movidos={len(avatar)}; "
        f"American Ninja Warrior agregado={xumo_agregado}."
    )
    return salida



def agrupar_alternativas_por_identidad(lineas):
    """Agrupa URLs del mismo canal en la misma categoría y conserva todas las opciones."""
    bloques, prefijo = [], []
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            else:
                bloques[-1]["lineas"].append(lineas[i])
            i += 1
            continue
        inicio = i
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            j += 1
        raw = list(lineas[inicio:j])
        extinf = raw[0]
        url = next((x.strip() for x in raw[1:] if url_es_valida(x.strip())), "")
        display = extraer_nombre(extinf)
        display_base = re.sub(
            r"\s*(?:\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]|\(\s*(?:opci[oó]n|option)\s*\d+\s*\))\s*$",
            "", display, flags=re.I,
        ).strip()
        display_base = re.sub(
            r"\s*(?:\[\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\]|\(\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\))\s*$",
            "", display_base, flags=re.I,
        ).strip()
        # HD/SD/FHD/UHD son variantes distintas y no deben fusionarse.
        canonical_base = display_base
        id_match = re.search(r'tvg-id="([^"]*)"', extinf, re.I)
        tvg_name_match = re.search(r'tvg-name="([^"]*)"', extinf, re.I)
        logo_match = re.search(r'tvg-logo="([^"]*)"', extinf, re.I)
        bloques.append({
            "lineas": raw, "url": url,
            "categoria": normalizar(extraer_categoria(extinf)),
            "nombre": normalizar_nombre_canal(canonical_base), "display": display_base,
            "id": id_match.group(1).strip() if id_match else "",
            "tvg_name": tvg_name_match.group(1).strip() if tvg_name_match else "",
            "logo": logo_match.group(1).strip() if logo_match else "",
        })
        i = j

    grupos = defaultdict(list)
    for indice, bloque in enumerate(bloques):
        if bloque["url"] and bloque["nombre"] and bloque["categoria"]:
            grupos[(bloque["categoria"], bloque["nombre"])].append(indice)

    reemplazos, omitidos = {}, set()
    for indices in grupos.values():
        if len(indices) < 2:
            continue
        ids = {bloques[idx]["id"] for idx in indices if bloques[idx]["id"]}
        if len(ids) > 1:
            continue
        grupo = [bloques[idx] for idx in indices]
        base = next((item["display"] for item in grupo if item["display"]), "")
        canonical_id = next((item["id"] for item in grupo if item["id"]), "")
        canonical_tvg = next((item["tvg_name"] for item in grupo if item["tvg_name"]), base)
        normalizados, seen_urls = [], set()
        for item in grupo:
            if item["url"] in seen_urls:
                continue
            seen_urls.add(item["url"])
            raw = list(item["lineas"])
            extinf = raw[0]
            def set_attr(texto, key, value):
                if not value:
                    return texto
                pattern = r'(?<![\w-])' + re.escape(key) + r'="[^"]*"'
                replacement = f'{key}="{value}"'
                if re.search(pattern, texto, re.I):
                    return re.sub(pattern, lambda _: replacement, texto, count=1, flags=re.I)
                comma = texto.find(",")
                return texto[:comma].rstrip() + " " + replacement + texto[comma:] if comma >= 0 else texto
            # No propagar un ID nuevo a una entrada histórica que no lo tenía:
            # el guardia de orden debe poder reconocerla por nombre.
            extinf = set_attr(extinf, "tvg-id", item["id"])
            extinf = set_attr(extinf, "tvg-name", canonical_tvg)
            # Los logos son independientes por URL/opción: nunca copiarlos ni sobrescribirlos.
            current_logo = re.search(r'tvg-logo="([^"]*)"', extinf, re.I)
            legacy_logo = re.search(r'(?<![\\w-])logo="([^"]*)"', extinf, re.I)
            if (not current_logo or not current_logo.group(1).strip()) and legacy_logo and legacy_logo.group(1).strip():
                extinf = set_attr(extinf, "tvg-logo", legacy_logo.group(1).strip())
            label = base if not normalizados else f"{base} [Opción {len(normalizados) + 1}]"
            raw[0] = re.sub(r",.*$", "," + label, extinf)
            normalizados.append(raw)
        if len(normalizados) > 1:
            reemplazos[indices[0]] = normalizados
            omitidos.update(indices[1:])

    salida = list(prefijo)
    for indice, bloque in enumerate(bloques):
        if indice in omitidos:
            continue
        if indice in reemplazos:
            for item in reemplazos[indice]:
                salida.extend(item)
        else:
            salida.extend(bloque["lineas"])
    return salida




def restaurar_logos_historicos(lineas, referencia, pluto_por_id=None, pluto_por_nombre=None):
    """Restaura solo logos ausentes desde la M3U anterior y el catálogo Pluto."""
    pluto_por_id = pluto_por_id or {}
    pluto_por_nombre = pluto_por_nombre or {}

    def bloques(datos):
        resultado = []
        i = 0
        while i < len(datos):
            if not datos[i].startswith("#EXTINF"):
                i += 1
                continue
            j = i + 1
            while j < len(datos) and not datos[j].startswith("#EXTINF"):
                j += 1
            extinf = datos[i]
            url = next((x.strip() for x in datos[i + 1:j] if url_es_valida(x.strip())), "")
            m_id = re.search(r'tvg-id="([^"]*)"', extinf, re.I)
            m_logo = re.search(r'tvg-logo="([^"]*)"', extinf, re.I)
            m_legacy = re.search(r'(?<![\w-])logo="([^"]*)"', extinf, re.I)
            logo = (m_logo.group(1).strip() if m_logo else "") or (
                m_legacy.group(1).strip() if m_legacy else ""
            )
            resultado.append({
                "index": i,
                "url": url,
                "id": m_id.group(1).strip().lower() if m_id else "",
                "category": normalizar(extraer_categoria(extinf)),
                "name": normalizar_nombre_canal(extraer_nombre(extinf)),
                "logo": logo,
            })
            i = j
        return resultado

    def poner_logo(extinf, logo):
        if not logo or not url_es_valida(logo):
            return extinf
        patron = r'(?<![\w-])tvg-logo="[^"]*"'
        reemplazo = f'tvg-logo="{logo}"'
        if re.search(patron, extinf, re.I):
            return re.sub(patron, lambda _: reemplazo, extinf, count=1, flags=re.I)
        coma = extinf.find(",")
        return extinf[:coma].rstrip() + " " + reemplazo + extinf[coma:] if coma >= 0 else extinf

    anteriores = bloques(referencia)
    por_id, por_url, por_nombre, por_nombre_global = (
        defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(set)
    )
    pluto_nombre_normalizado = {
        normalizar_nombre_canal(canal.get("nombre") or clave): canal
        for clave, canal in pluto_por_nombre.items()
    }
    for item in anteriores:
        if not item["logo"] or not url_es_valida(item["logo"]):
            continue
        if item["id"]:
            por_id[item["id"]].add(item["logo"])
        if item["url"]:
            por_url[item["url"]].add(item["logo"])
        if item["category"] and item["name"]:
            por_nombre[(item["category"], item["name"])].add(item["logo"])
        if item["name"]:
            por_nombre_global[item["name"]].add(item["logo"])

    restaurados_anteriores = 0
    restaurados_pluto = 0
    pendientes = 0
    salida = list(lineas)
    for item in bloques(salida):
        extinf = salida[item["index"]]
        actual = re.search(r'tvg-logo="([^"]*)"', extinf, re.I)
        if actual and actual.group(1).strip() and url_es_valida(actual.group(1).strip()):
            continue

        legado = re.search(r'(?<![\w-])logo="([^"]*)"', extinf, re.I)
        logo = legado.group(1).strip() if legado else ""
        if not logo and item["url"] and len(por_url.get(item["url"], set())) == 1:
            logo = next(iter(por_url[item["url"]]))
        if not logo and item["id"] and len(por_id.get(item["id"], set())) == 1:
            logo = next(iter(por_id[item["id"]]))
        if not logo and item["category"] and item["name"]:
            candidatos = por_nombre.get((item["category"], item["name"]), set())
            if len(candidatos) == 1:
                logo = next(iter(candidatos))
        if not logo and item["name"]:
            candidatos = por_nombre_global.get(item["name"], set())
            if len(candidatos) == 1:
                logo = next(iter(candidatos))
        if logo:
            restaurados_anteriores += 1
        else:
            canal = pluto_por_id.get(item["id"]) if item["id"] else None
            if canal is None and item["name"]:
                canal = pluto_nombre_normalizado.get(item["name"])
            if canal:
                m_logo = re.search(r'tvg-logo="([^"]+)"', canal.get("extinf", ""), re.I)
                if m_logo and url_es_valida(m_logo.group(1).strip()):
                    logo = m_logo.group(1).strip()
                    restaurados_pluto += 1
        if logo:
            salida[item["index"]] = poner_logo(extinf, logo)
        else:
            pendientes += 1

    print(
        "  -> Logos restaurados: "
        f"lista anterior={restaurados_anteriores}; Pluto={restaurados_pluto}; "
        f"sin referencia verificable={pendientes}."
    )
    return salida, {
        "lista_anterior": restaurados_anteriores,
        "pluto": restaurados_pluto,
        "sin_referencia": pendientes,
    }

def ordenar_anime_alfabeticamente(lineas):
    """Ordena Anime por franquicia y saga; mantiene opciones contiguas."""
    prefijo, bloques = [], []
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            elif bloques:
                bloques[-1]["lineas"].append(lineas[i])
            i += 1
            continue
        inicio = i
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            j += 1
        raw = list(lineas[inicio:j])
        nombre = extraer_nombre(raw[0])
        match = re.search(
            r"\s*(?:\[\s*(?:opci[oó]n|opc)\s*\.?\s*(\d+)\s*\]|"
            r"\(\s*(?:opci[oó]n|opc)\s*\.?\s*(\d+)\s*\))$",
            nombre,
            re.I,
        )
        opcion = int(match.group(1) or match.group(2)) if match else 1
        base = nombre[:match.start()].strip() if match else nombre
        canon = normalizar(base)
        familia, saga, alias = canon, 0, 0

        if canon.startswith("dragon ball"):
            familia = "dragon ball"
            if "pelicul" in canon or "movie" in canon:
                saga = 4
            elif "dragon ball / dragon ball z" in canon:
                saga = 0.5
            elif re.search(r"\bgt\b", canon):
                saga = 3
            elif re.search(r"\bsuper\b", canon):
                saga = 2
            elif re.search(r"\bz\b", canon):
                saga = 1
        elif canon.startswith("naruto") or canon.startswith("boruto"):
            familia = "naruto"
            if "pelicul" in canon or "movie" in canon:
                saga = 3
            elif canon.startswith("boruto"):
                saga = 2
            elif "shippuden" in canon:
                saga = 1
        elif "super campeones" in canon or "captain tsubasa" in canon:
            familia = "super campeones"
            alias = 0 if "super campeones" in canon else 1
        elif "caballeros del zodiaco" in canon or "saint seiya" in canon:
            familia = "caballeros del zodiaco"

        bloques.append({
            "lineas": raw,
            "anime": normalizar(extraer_categoria(raw[0])) == "anime",
            "clave": (familia, saga, alias, opcion, canon, len(bloques)),
        })
        i = j

    anime = sorted(
        (bloque for bloque in bloques if bloque["anime"]),
        key=lambda bloque: bloque["clave"],
    )
    siguiente = iter(anime)
    salida = list(prefijo)
    for bloque in bloques:
        elegido = next(siguiente) if bloque["anime"] else bloque
        salida.extend(elegido["lineas"])
    return salida


def mover_paises_al_final(lineas):
    """Mueve las categorías-país al final sin alterar sus canales ni su orden interno."""
    prefijo, bloques = [], []
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            if not bloques:
                prefijo.append(lineas[i])
            i += 1
            continue
        inicio = i
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            j += 1
        raw = lineas[inicio:j]
        categoria = normalizar(extraer_categoria(raw[0]))
        es_pais = categoria in PAISES_ORDEN_FINAL or categoria.startswith("el salvador")
        bloques.append({"lineas": raw, "pais": es_pais})
        i = j

    normales = [b for b in bloques if not b["pais"]]
    paises = [b for b in bloques if b["pais"]]
    salida = list(prefijo)
    for bloque in normales + paises:
        salida.extend(bloque["lineas"])
    return salida

def ordenar_bloques_magma_y_originales(lineas, session):
    """
    Ordena exclusivamente Entretenimiento / Cine / Series en tres bloques:
      1) Los cinco canales fijos solicitados.
      2) Canales de la fuente MAGMA, alfabéticamente.
      3) Canales originales, alfabéticamente.
    Las alternativas permanecen junto a su canal base.
    """
    respuesta = session.get(FUENTE_MAGMA, timeout=30)
    respuesta.raise_for_status()
    canales_magma = parsear_m3u(respuesta.text)
    categoria_objetivo = normalizar("Entretenimiento / Cine / Series")
    urls_magma = {
        (canal.get("url") or "").strip()
        for canal in canales_magma
        if normalizar(canal.get("categoria", "")) == categoria_objetivo
        and (canal.get("url") or "").strip()
    }
    if not urls_magma:
        raise RuntimeError("La fuente MAGMA no entregó canales de Entretenimiento / Cine / Series.")

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
        j = i + 1
        while j < len(lineas) and not lineas[j].startswith("#EXTINF"):
            j += 1
        raw = lineas[inicio:j]
        url = next((x.strip() for x in raw[1:] if url_es_valida(x.strip())), "")
        bloques.append({
            "lineas": raw,
            "categoria": extraer_categoria(raw[0]),
            "nombre": extraer_nombre(raw[0]),
            "url": url,
            "orden": len(bloques),
        })
        i = j

    objetivo = [
        b for b in bloques
        if normalizar(b["categoria"]) == categoria_objetivo
    ]
    if not objetivo:
        raise RuntimeError("No existe la categoría Entretenimiento / Cine / Series en la principal.")

    fijos = [
        "Los Simpson Latino",
        "Los Simpson Latino Opc. 2",
        "El Chavo TV",
        "Chespirito TV",
        "Retro TV",
    ]
    claves_fijas = {normalizar(x) for x in fijos}
    fijos_por_nombre = {}
    for bloque in objetivo:
        clave = normalizar(bloque["nombre"])
        if clave in claves_fijas:
            fijos_por_nombre.setdefault(clave, []).append(bloque)

    faltantes_fijos = [
        nombre for nombre in fijos
        if normalizar(nombre) not in fijos_por_nombre
    ]
    if faltantes_fijos:
        raise RuntimeError(
            "Faltan canales del bloque fijo de entretenimiento: "
            + ", ".join(faltantes_fijos)
        )

    fijos_ordenados = [
        fijos_por_nombre[normalizar(nombre)][0]
        for nombre in fijos
    ]
    fijos_ids = {id(b) for b in fijos_ordenados}

    magma = [b for b in objetivo if b["url"] in urls_magma and id(b) not in fijos_ids]
    urls_presentes_magma = {b["url"] for b in magma}
    faltantes_magma = urls_magma - urls_presentes_magma
    if faltantes_magma:
        raise RuntimeError(
            f"Faltan {len(faltantes_magma)} canales MAGMA en la categoría objetivo; "
            "se cancela el ordenamiento para no publicar una lista incompleta."
        )

    magma_ids = {id(b) for b in magma}
    originales = [
        b for b in objetivo
        if id(b) not in fijos_ids and id(b) not in magma_ids
    ]

    def clave_alfabetica(bloque):
        nombre = re.sub(r"\s*\[MAGMA\]$", "", bloque["nombre"], flags=re.I).strip()
        version = re.search(r"\[V(\d+)\]", nombre, flags=re.I)
        if version:
            numero_variante = int(version.group(1))
            base = (nombre[:version.start()] + nombre[version.end():]).strip()
        else:
            opcion = re.search(
                r"\s*(?:\((?:OPCIÓN|OPC)\s*\.?\s*(\d+)\)|\[(?:OPCIÓN|OPC)\s*\.?\s*(\d+)\])$",
                nombre,
                flags=re.I,
            )
            numero_variante = int(opcion.group(1) or opcion.group(2)) if opcion else 0
            base = nombre[:opcion.start()].strip() if opcion else nombre
        return (normalizar(base), numero_variante, normalizar(nombre), bloque["orden"])

    magma_ordenado = sorted(magma, key=clave_alfabetica)
    originales_ordenados = sorted(originales, key=clave_alfabetica)
    ordenados = fijos_ordenados + magma_ordenado + originales_ordenados

    primer_indice = min(b["orden"] for b in objetivo)
    objetivo_ids = {id(b) for b in objetivo}
    resultado = [b for b in bloques if id(b) not in objetivo_ids]
    resultado[primer_indice:primer_indice] = ordenados

    salida = list(prefijo)
    for bloque in resultado:
        salida.extend(bloque["lineas"])

    auditoria = {
        "fijos": len(fijos_ordenados),
        "magma": len(magma_ordenado),
        "originales": len(originales_ordenados),
        "urls_magma": len(urls_magma),
    }
    return salida, auditoria


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
    lineas_iniciales = list(lineas)

    total_inicial = sum(1 for x in lineas if x.startswith("#EXTINF"))

    bloques_no_pluto_iniciales = extraer_bloques_no_pluto_por_url(lineas)

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

    # 3) Pluto: las fuentes permitidas son LATAM, ES y MX.
    # No se consulta ninguna playlist regional Pluto eliminada.
    pluto_brasil_movidos = 0
    pluto_brasil_errores = 0

    # 4) Pluto: una sola entrada por channel ID en toda la principal.
    # Conserva la primera aparición y elimina copias regionales del mismo
    # canal, aunque tengan URLs Pluto distintas.
    lineas, pluto_duplicados_existentes = deduplicar_pluto_existente(lineas)

    # 5) Pluto: Retro/Paranormal/Competencia usan la referencia LATAM.
    (
        lineas,
        pluto_canonicos_eliminados,
        pluto_canonicos_movidos,
    ) = limpiar_pluto_categorias_canonicas(lineas, session)

    # 6) Limpieza de TOTAL, OTROS y categoría vacía.
    lineas, limpieza = limpiar_total_otros_y_sin_nombre(lineas)

    categorias = categorias_de_lineas(lineas)
    categorias_iniciales_normalizadas = {normalizar(x) for x in categorias}
    urls_globales = mapa_urls_principal(lineas)

    # Pluto sí se deduplica por identidad/channel ID entre nuestras fuentes:
    # LATAM tiene prioridad; ES y MX solo complementan IDs que aún no existen.
    # Para fuentes normales, agregar_bloque() evita repetir la URL exacta.
    pluto_ids_canonicos = obtener_ids_pluto_canonicos(session)

    ids_pluto_fuentes = set()
    aliases_pluto_fuentes = defaultdict(set)
    urls_pluto_fuentes_por_id = defaultdict(set)
    canales_pluto_fuentes_por_id = defaultdict(list)
    urls_pluto_fuentes = set()

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
            if fuente_es_iptvsv := es_fuente_iptvsv(fuente):
                # Primero sincronizar group-title de las URLs que ya existen.
                # Validar antes de esta reconciliación bloqueaba toda la fuente
                # precisamente cuando IPTV-SV traía una categoría actualizada.
                lineas, iptvsv_reclasificados, iptvsv_conflictos = reclasificar_iptvsv_existente(
                    lineas,
                    canales,
                    categorias,
                )
                if iptvsv_reclasificados:
                    print(f"  -> IPTVSV URLs existentes reclasificadas: {iptvsv_reclasificados}")
                if iptvsv_conflictos:
                    print(f"  -> IPTVSV conflictos de categoría por URL: {iptvsv_conflictos}")
                iptvsv_auditoria = validar_integridad_iptvsv(
                    lineas,
                    canales,
                    categorias,
                )
                print(
                    "  -> IPTVSV integridad: "
                    f"{iptvsv_auditoria['urls_fuente']} URLs fuente, "
                    f"{iptvsv_auditoria['conflictos_fuente']} conflictos de URL, "
                    f"{iptvsv_auditoria['errores_categoria']} categorías incorrectas."
                )
            pais_fuente = next(
                (pais for clave, pais in PAIS_POR_FUENTE.items()
                 if clave.lower() in fuente.lower()),
                None,
            )
            nuevos = 0
            omitidos_regla_especial = 0
            canales_destinados = []
            for canal in canales:
                if canal_excluido_pluto_es(fuente, canal):
                    omitidos_regla_especial += 1
                    continue
                if fuente_es_iptvsv:
                    destino = determinar_destino_iptvsv(
                        canal.get("categoria", ""),
                        canal.get("nombre", ""),
                        categorias,
                    )
                    if destino is None:
                        omitidos_regla_especial += 1
                        continue
                elif fuente == FUENTE_MAGMA:
                    destino = determinar_destino_magma(
                        canal.get("categoria", ""),
                        canal.get("nombre", ""),
                        categorias,
                    )
                else:
                    destino = determinar_destino(
                        canal.get("categoria", ""),
                        canal.get("nombre", ""),
                        pais_fuente,
                        categorias,
                    )

                if not destino and normalizar(canal.get("categoria", "")) in {"total", "otros"}:
                    destino = destino_especial_total_otros(
                        canal.get("nombre", ""),
                        canal.get("categoria", ""),
                        categorias,
                    )
                if not destino or normalizar(destino) in {"total", "otros"}:
                    continue
                canales_destinados.append((canal, destino))

            lineas, sincronizacion = sincronizar_enlaces_existentes(lineas, canales_destinados)
            urls_globales = mapa_urls_principal(lineas)
            # Las fuentes previas del mismo ciclo aún pueden tener bloques
            # pendientes de insertar; no perder sus URLs al recalcular el mapa.
            urls_globales.update(
                item["bloque"][-1].strip()
                for item in bloques_nuevos
                if item.get("bloque") and url_es_valida(item["bloque"][-1].strip())
            )
            if any(sincronizacion.values()):
                print(
                    "  -> sincronización de canales existentes: "
                    f"{sincronizacion['urls_actualizadas']} URLs, "
                    f"{sincronizacion['nombres_actualizados']} nombres, "
                    f"{sincronizacion['categorias_actualizadas']} categorías."
                )

            for canal, destino in canales_destinados:
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
    # FUENTE COMPLEMENTARIA DE UN SOLO CANAL: FEAR FACTOR (no importar el resto del catálogo).
    if FUENTE_FEAR_FACTOR:
        print(f"\n[CANAL ÚNICO] Fear Factor <- {FUENTE_FEAR_FACTOR}")
        try:
            respuesta = session.get(FUENTE_FEAR_FACTOR, timeout=30)
            respuesta.raise_for_status()
            canal = seleccionar_canal_fear_factor(parsear_m3u(respuesta.text))
            if not canal:
                raise RuntimeError("No existe bloque reproducible con nombre exacto Fear Factor.")
            logo = re.search(r'tvg-logo="([^"]+)"', canal.get("extinf", ""), re.I)
            if not logo or not url_es_valida(logo.group(1)):
                raise RuntimeError("Fear Factor no trae logo HTTP(S) válido.")
            destino = determinar_categoria_fear_factor(categorias)
            url_fear = canal["url"].strip()
            logo_fear = logo.group(1).strip()
            existente = False
            for indice_url, linea_url in enumerate(lineas):
                if linea_url.strip() != url_fear:
                    continue
                indice_extinf = indice_url - 1
                while indice_extinf >= 0 and not lineas[indice_extinf].startswith("#EXTINF"):
                    indice_extinf -= 1
                if indice_extinf < 0:
                    continue
                extinf = lineas[indice_extinf]
                if re.search("tvg-logo=\"[^\"]*\"", extinf, re.I):
                    extinf = re.sub("tvg-logo=\"[^\"]*\"", "tvg-logo=\"" + logo_fear + "\"", extinf, count=1, flags=re.I)
                else:
                    coma = extinf.find(",")
                    extinf = extinf[:coma].rstrip() + " tvg-logo=\"" + logo_fear + "\"" + extinf[coma:]
                extinf = reemplazar_categoria(extinf, destino)
                if "," in extinf:
                    extinf = extinf.rsplit(",", 1)[0] + ",Fear Factor"
                lineas[indice_extinf] = extinf
                existente = True
            if existente:
                print("  -> Fear Factor existente actualizado: Competencia + logo oficial de la fuente.")
            else:
                urls = mapa_urls_principal(lineas)
                urls.update(item["bloque"][-1].strip() for item in bloques_nuevos
                            if item.get("bloque") and url_es_valida(item["bloque"][-1].strip()))
                if agregar_bloque(canal, destino, urls, bloques_nuevos):
                    agregados_normales += 1
                    print("  -> Fear Factor agregado a Competencia con URL y logo fuente.")
                else:
                    print("  -> Fear Factor omitido: URL ya presente en un bloque pendiente.")
        except Exception as error_fear:
            errores += 1
            print(f"  -> ERROR Fear Factor: {error_fear}")
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
                # Pluto ES no debe reinsertar Anime ni la variante regional
                # no funcional de Los Pitufos, ni siquiera en la reparación final.
                if canal_excluido_pluto_es(fuente, canal):
                    continue

                destino = determinar_destino_pluto(
                    canal.get("categoria", ""),
                    canal.get("nombre", ""),
                    categorias,
                )

                if not destino:
                    # No crear carpetas genéricas Pluto TV ni categorías vacías.
                    sin_categoria += 1
                    continue

                url_pluto_fuente = canal.get("url", "").strip()
                if url_pluto_fuente:
                    urls_pluto_fuentes.add(url_pluto_fuente)

                identidad = identidad_pluto(canal.get("extinf", ""), url_pluto_fuente)
                if identidad:
                    urls_pluto_fuentes_por_id[identidad].add(canal.get("url", "").strip())
                    canales_pluto_fuentes_por_id[identidad].append(canal)

                            # Pluto se deduplica por channel ID global: LATAM gana y
                # ES/MX solo aportan IDs todavía ausentes.
                if (
                    identidad
                    and normalizar(destino) in PLUTO_CATEGORIAS_CANONICAS
                    and pluto_ids_canonicos
                    and identidad not in pluto_ids_canonicos
                ):
                    omitidos_duplicados += 1
                    continue

                if identidad and identidad in ids_pluto_fuentes:
                    omitidos_duplicados += 1
                    continue

                # Solo los IDs que realmente aceptamos entran en la cobertura
                # obligatoria. Copias regionales/JWT del mismo ID no se exigen.
                if identidad:
                    ids_pluto_fuentes.add(identidad)
                    aliases_pluto_fuentes[identidad].update(
                        identidades_pluto(canal.get("extinf", ""), url_pluto_fuente)
                    )

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
    # Regla estricta: las fuentes nunca crean categorías nuevas.
    lineas = insertar_bloques(lineas, bloques_nuevos)

    # 7) Consolidar Pluto por identidad aplicando LATAM > ES > MX.
    lineas, pluto_prioridad_eliminados = deduplicar_pluto_por_prioridad(
        lineas,
        canales_pluto_fuentes_por_id,
    )

    # 8) Consolidar físicamente SOLO Pluto. Esto elimina bloques Pluto
    # intercalados entre categorías ajenas sin mover ningún bloque no-Pluto.
    (
        lineas,
        pluto_movidos_fisicamente,
        pluto_movidos_fisicamente_por_categoria,
    ) = reubicar_bloques_pluto_sin_reordenar_principal(lineas)

    # 9) Limpieza de seguridad: nunca conservar EXTINF sin URL.
    lineas, extinf_huerfanos_eliminados = limpiar_extinf_huerfanos(lineas)

    # 10) Auditoría/normalización FINAL: consolida las carpetas y aplica
    # exclusivamente el orden maestro ACTUAL. La lista antigua no se usa
    # para volver a imponer un orden histórico.
    lineas, cambios_orden = ordenar_y_normalizar_carpetas(lineas)

    # 11) Auditoría final: exact-URL dedupe y limpieza de carpetas especiales.
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

    # 12) Validación final de URLs duplicadas globales.
    vistos = set()
    duplicados_finales = 0
    for linea in lineas:
        u = linea.strip()
        if url_es_valida(u):
            if u in vistos:
                duplicados_finales += 1
            vistos.add(u)

    # Consolidar de nuevo las categorías después de los ajustes previos.
    # La restauración de canales no-Pluto se ejecuta más abajo, al final.
    lineas, cambios_orden_post_restauracion = ordenar_y_normalizar_carpetas(lineas)
    if cambios_orden_post_restauracion:
        print("Orden final tras autorreparación aplicado.")

    # 14) Consolidación física definitiva: una sola sección por categoría.
    lineas, categorias_fisicas = consolidar_bloques_por_categoria(lineas)
    print(f"Consolidación física final: {categorias_fisicas} categorías.")

    # 15) VALIDACIÓN BLOQUEANTE ANTES DE ESCRIBIR LA PRINCIPAL.
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
    categorias_finales_normalizadas = {normalizar(x) for x in categorias_finales}
    alias_permitidos = {
        "el salvador": "el salvador - tcs",
        "documentales y cultura": "documentales",
    }
    categorias_nuevas = {
        cat for cat in categorias_finales_normalizadas
        if cat not in categorias_iniciales_normalizadas
        and alias_permitidos.get(cat) not in categorias_iniciales_normalizadas
        and cat != normalizar("el salvador")
    }
    if categorias_nuevas:
        raise RuntimeError(
            "VALIDACION DE CATEGORIAS FALLIDA: se crearon carpetas nuevas: "
            + ", ".join(sorted(categorias_nuevas))
        )
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

    total_final = sum(1 for x in lineas if x.startswith("#EXTINF"))

    # 17) BLOQUEO DE SEGURIDAD: ninguna señal Pluto presente en las fuentes propias
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

    # Repetir validación física después del autorreparo.
    categorias_finales_post = []
    bloques_finales_post = []
    categoria_actual_post = None
    for linea_post in lineas:
        if not linea_post.startswith("#EXTINF"):
            continue
        cat_post = extraer_categoria(linea_post)
        if cat_post != categoria_actual_post:
            bloques_finales_post.append(cat_post)
            categoria_actual_post = cat_post
        categorias_finales_post.append(normalizar(cat_post))

    repetidas_post = [
        cat for cat in set(bloques_finales_post)
        if bloques_finales_post.count(cat) > 1
    ]
    if repetidas_post:
        raise RuntimeError(
            "VALIDACION FINAL DE BLOQUES FALLIDA: categorías físicas repetidas: "
            + ", ".join(sorted(repetidas_post))
        )

    # Integrar Pluto MX externo después de las limpiezas para conservar alternativas.
    lineas, pluto_mx_auditoria = integrar_pluto_mx(lineas, session)
    print(
        "Pluto MX externo: "
        f"{pluto_mx_auditoria['agregadas']} agregadas; "
        f"{pluto_mx_auditoria['bases_nuevas']} bases nuevas; "
        f"{pluto_mx_auditoria['sin_coincidencia']} sin coincidencia."
    )

    # La identidad de Pluto ES es obligatoria para esta limpieza. Si no se puede
    # verificar el catálogo, se aborta antes de escribir la lista principal.
    ids_pluto_es_anime = cargar_ids_pluto_es_anime(session)

    # Las reglas de referencia y el orden MAGNA se aplican después de restaurar
    # los canales existentes, para que ninguna reconciliación posterior los deshaga.

    # Restaurar al FINAL de todas las limpiezas y ajustes. Antes se hacía
    # demasiado pronto: las correcciones de referencia y otras normalizaciones
    # posteriores podían volver a retirar los canales recién recuperados.
    # Las categorías eliminadas explícitamente se excluyen dentro del restaurador.
    lineas, no_pluto_restaurados = restaurar_no_pluto_existente(
        lineas,
        bloques_no_pluto_iniciales,
    )
    if no_pluto_restaurados:
        print(f"Autorreparación final: {no_pluto_restaurados} canales no-Pluto restaurados.")

    # Restaurar primero el orden de los canales que ya estaban publicados.
    # Los nuevos se anexan; las carpetas especiales y Pluto conservan sus reglas.
    ids_pluto_orden_protegidos = (
        set(ids_pluto_fuentes)
        | set(pluto_ids_canonicos)
        | obtener_ids_pluto_existentes(lineas_iniciales)
    )
    lineas = restaurar_orden_original_por_categoria(
        lineas,
        lineas_iniciales,
        categorias_reordenables={"Entretenimiento / Cine / Series"},
        ids_pluto=ids_pluto_orden_protegidos,
    )

    # Aplicar al FINAL las reglas solicitadas: la restauración histórica puede
    # volver a colocar canales infantiles en su categoría/posición anterior.
    lineas = aplicar_ajustes_referencia(lineas, ids_pluto_es_anime)

    # Fijar el bloque MAGNA y reagrupar alternativas después de toda restauración.
    lineas, orden_entretenimiento = ordenar_bloques_magma_y_originales(lineas, session)
    lineas = agrupar_alternativas_por_identidad(lineas)
    print(
        "Orden entretenimiento: "
        f"{orden_entretenimiento['fijos']} fijos; "
        f"{orden_entretenimiento['magma']} MAGMA; "
        f"{orden_entretenimiento['originales']} originales."
    )
    total_final = sum(1 for x in lineas if x.startswith("#EXTINF"))

    # ÚLTIMA barrera Pluto: las correcciones posteriores pueden retirar una
    # entrada ya reparada. Restaurar después de TODAS las transformaciones.
    aliases_pluto_salida = set()
    for i_final, extinf_final in enumerate(lineas):
        if not extinf_final.startswith("#EXTINF"):
            continue
        j_final = i_final + 1
        while j_final < len(lineas) and lineas[j_final].startswith("#"):
            j_final += 1
        if j_final < len(lineas) and url_es_valida(lineas[j_final].strip()):
            aliases_pluto_salida.update(
                identidades_pluto(extinf_final, lineas[j_final].strip())
            )

    pluto_reinsertados_finales = []
    for identidad in sorted(ids_pluto_fuentes):
        aliases_fuente = aliases_pluto_fuentes.get(identidad, {identidad})
        if aliases_fuente & aliases_pluto_salida:
            continue
        candidatos = canales_pluto_fuentes_por_id.get(identidad, [])
        canal_fuente = next(
            (c for c in candidatos if (c.get("url") or "").strip()),
            None,
        )
        if not canal_fuente:
            raise RuntimeError(
                f"PLUTO BLOQUEADO: no existe bloque fuente para restaurar {identidad}."
            )
        destino = determinar_destino_pluto(
            canal_fuente.get("categoria", ""),
            canal_fuente.get("nombre", ""),
            categorias_de_lineas(lineas),
        )
        if not destino:
            raise RuntimeError(
                f"PLUTO BLOQUEADO: {identidad} no tiene una categoría existente válida "
                f"(fuente: {canal_fuente.get('categoria', '')!r})."
            )
        pluto_reinsertados_finales.append({
            "categoria": destino,
            "bloque": construir_bloque(canal_fuente, destino),
        })
        aliases_pluto_salida.update(identidades_pluto(
            canal_fuente.get("extinf", ""),
            canal_fuente.get("url", ""),
        ))

    if pluto_reinsertados_finales:
        # Insertar después del ÚLTIMO bloque completo de cada categoría.
        # encontrar_rango_categoria devuelve índices EXTINF; insertar justo
        # después de ese índice partiría el bloque anterior y corrompería la M3U.
        posiciones_por_categoria = {}
        i_pos = 0
        while i_pos < len(lineas):
            if not lineas[i_pos].startswith("#EXTINF"):
                i_pos += 1
                continue
            j_pos = i_pos + 1
            while j_pos < len(lineas) and lineas[j_pos].startswith("#") and not lineas[j_pos].startswith("#EXTINF"):
                j_pos += 1
            if j_pos < len(lineas) and url_es_valida(lineas[j_pos].strip()):
                clave_categoria = normalizar(extraer_categoria(lineas[i_pos]))
                posiciones_por_categoria[clave_categoria] = j_pos + 1
                i_pos = j_pos + 1
            else:
                i_pos = j_pos

        agrupados_pluto = defaultdict(list)
        for item in pluto_reinsertados_finales:
            agrupados_pluto.setdefault(normalizar(item["categoria"]), []).append(item["bloque"])

        inserciones = []
        for clave_categoria, bloques_categoria in agrupados_pluto.items():
            posicion = posiciones_por_categoria.get(clave_categoria)
            if posicion is None:
                raise RuntimeError(
                    f"PLUTO BLOQUEADO: no se encontró el cierre de la categoría {clave_categoria!r}."
                )
            bloque_conjunto = []
            for bloque in bloques_categoria:
                bloque_conjunto.extend(bloque)
            inserciones.append((posicion, bloque_conjunto))

        for posicion, contenido_insertar in sorted(inserciones, reverse=True):
            lineas[posicion:posicion] = contenido_insertar

        print(
            "Autorreparación Pluto final: "
            f"{len(pluto_reinsertados_finales)} canales reinsertados tras la última normalización."
        )

    # Consolidar alternativas ANTES de la restauración definitiva.
    # El agrupador conserva la primera aparición del bloque y podía adelantar
    # una identidad reasignada después de haber restaurado el orden histórico.
    lineas = agrupar_alternativas_por_identidad(lineas)

    # La última operación estructural debe ser restaurar el orden histórico:
    # así ninguna consolidación posterior puede mover un canal existente.
    lineas = restaurar_orden_original_por_categoria(
        lineas,
        lineas_iniciales,
        categorias_reordenables={
            "Entretenimiento / Cine / Series",
            "Infantiles",
        },
        ids_pluto=ids_pluto_orden_protegidos,
    )

    # Las variantes no-Pluto pueden compartir tvg-id con una URL Pluto.
    # Añadir los IDs observados en la salida final al conjunto protegido para
    # que una alternativa regional no se confunda con un canal normal reordenado.
    ids_pluto_orden_protegidos.update(obtener_ids_pluto_existentes(lineas))

    # Aplicar las directivas de reconexión a la representación final.
    lineas, reconexiones_agregadas = aplicar_reconexion_por_canal(lineas)
    lineas, resoluciones_corregidas = corregir_resoluciones_por_url(lineas)
    print(f"Resoluciones SD/HD corregidas por URL exacta: {resoluciones_corregidas}")
    validar_orden_canales(
        lineas_iniciales,
        lineas,
        # Anime puede recibir altas nuevas desde las fuentes. Su orden final
        # se restaura contra la maestra en el orquestador, después de sincronizar.
        categorias_reordenables={
            "Entretenimiento / Cine / Series",
            "Infantiles",
            "Anime",
            # España recibe canales reclasificados desde Anime; la restauración
            # conserva el orden de URLs, pero su validación por nombre es ambigua.
            "España",
        },
        ids_pluto_omitidos=ids_pluto_orden_protegidos,
    )
    print(f"Reconexión/caché aplicados en salida final: {reconexiones_agregadas}")

    texto_final = "\n".join(lineas)
    if not texto_final.endswith("\n"):
        texto_final += "\n"

    # Validación final después del autorreparo: una representación por ID
    # aceptado es suficiente; no se exige conservar cada JWT regional.
    aliases_pluto_finales_actualizados = set()
    for i_post, linea_post in enumerate(lineas):
        if not linea_post.startswith("#EXTINF"):
            continue
        j_post = i_post + 1
        while j_post < len(lineas) and lineas[j_post].startswith("#"):
            j_post += 1
        if j_post < len(lineas) and url_es_valida(lineas[j_post].strip()):
            aliases_pluto_finales_actualizados.update(
                identidades_pluto(linea_post, lineas[j_post].strip())
            )

    ids_pluto_ausentes = calcular_ids_pluto_faltantes(
        ids_pluto_fuentes,
        aliases_pluto_fuentes,
        aliases_pluto_finales_actualizados,
    )
    if ids_pluto_ausentes:
        detalle_ids = {
            identidad: sorted(aliases_pluto_fuentes.get(identidad, {identidad}))
            for identidad in sorted(ids_pluto_ausentes)
        }
        raise RuntimeError(
            "VALIDACION PLUTO FALLIDA: faltan "
            f"{len(ids_pluto_ausentes)} IDs de las fuentes propias "
            "después del autorreparo. "
            f"Identidades no encontradas y aliases: {detalle_ids}"
        )

    # Escritura segura: solo publicar en disco después de superar todas las
    # validaciones bloqueantes, evitando dejar una principal parcial al fallar.
    PRINCIPAL.write_text(
        texto_final,
        encoding="utf-8",
        newline="\n",
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
    print(f"Pluto canónicos eliminados (no LATAM):  {pluto_canonicos_eliminados}")
    print(f"Pluto canónicos movidos de carpeta:     {pluto_canonicos_movidos}")
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
    print(f"Duplicados Pluto por prioridad LATAM>ES>MX eliminados: {pluto_prioridad_eliminados}")
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
    print("  - Dedupe global por URL para fuentes normales.")
    print("  - Pluto: dedupe global por channel ID; JWT/región distintos no crean copias.")
    print("  - Auditoría final: una URL exacta solo puede quedar una vez en toda la principal.")
    print("  - Telemundo Noticias conserva solo señales Telemundo; Sky Sports solo señales Sky Sports.")
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
    print("  - Ninguna fuente puede crear categorías nuevas.")
    print("  - Pluto antiguo se elimina antes de cargar Pluto propio.")
    print("  - Pluto propio usa exclusivamente FUENTES_PLUTO.")
    print("  - CHILE de fuentes normales -> CHILE TV.")
    print("  - LATAM.m3u NO crea carpeta LATAM: sus canales se redistribuyen por país/temática; los no clasificables se omiten.")
    print("=" * 72)

if __name__ == "__main__":
    main()
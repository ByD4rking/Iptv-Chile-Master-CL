from pathlib import Path
import re
import unicodedata
import requests
from collections import defaultdict

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

    # Reglas fijas de M3U.CL: estas fuentes tienen destino propio.
    if pais_fuente == "xxx":
        return buscar_categoria_existente("XXX+18", categorias)

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
    Restaura URLs no-Pluto que ya existían antes de la actualización.
    Las fuentes solo pueden sumar canales; no pueden hacer desaparecer
    una señal existente por una limpieza accidental.
    """
    actuales = mapa_urls_principal(lineas)
    categorias = categorias_de_lineas(lineas)
    bloques_por_categoria = defaultdict(list)
    restaurados = 0

    for url, bloque in iniciales.items():
        if url in actuales:
            continue
        extinf = bloque[0]
        categoria = extraer_categoria(extinf)
        destino = buscar_categoria_existente(categoria, categorias)

        # Si la categoría fue normalizada, reutilizar su carpeta canónica.
        if not destino:
            aliases = {
                "chile": "CHILE TV",
                "infantil": "INFANTILES",
                "teen": "INFANTILES",
                "noticias": "INFORMATIVOS",
            }
            destino = buscar_categoria_existente(
                aliases.get(normalizar(categoria), categoria),
                categorias,
            )

        if not destino:
            # No crear carpetas nuevas durante la autorreparación.
            continue

        bloque_restaurado = list(bloque)
        bloque_restaurado[0] = reemplazar_categoria(extinf, destino)
        bloques_por_categoria[destino].append(bloque_restaurado)
        actuales.add(url)
        restaurados += 1

    for categoria, bloques in bloques_por_categoria.items():
        rango = encontrar_rango_categoria(lineas, categoria)
        if not rango:
            continue
        posicion = rango[1] + 1
        insertar = []
        for bloque in bloques:
            insertar.extend(bloque)
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
        if match and match.group(1).strip():
            clave = "id:" + normalizar(match.group(1))
        else:
            clave = "name:" + normalizar(extraer_categoria(linea)) + ":" + normalizar(extraer_nombre(linea))
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
                        re.search(r'tvg-id="([^"]+)"', extinf, re.I).group(1).strip().lower()
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

    def identidades(extinf):
        keys = []
        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        if match and match.group(1).strip():
            keys.append("id:" + normalizar(match.group(1)))
        nombre = normalizar(extraer_nombre(extinf))
        if nombre:
            keys.append("name:" + nombre)
        return keys

    orden_original = {}
    for index, item in enumerate(anteriores):
        for key in identidades(item["lineas"][0]):
            orden_original.setdefault(key, index)
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
                ranks = [
                    orden_original[key]
                    for key in identidades(bloque["lineas"][0])
                    if key in orden_original
                ]
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

    def firmas_por_categoria(lineas):
        resultado = {}
        vistos = {}
        for linea in lineas:
            if not linea.startswith("#EXTINF"):
                continue
            categoria = normalizar(extraer_categoria(linea))
            nombre = normalizar(extraer_nombre(linea))
            # Avatar cambia deliberadamente desde Anime a Infantiles; hay dos variantes.
            if nombre.startswith("avatar: la leyenda de aang"):
                continue
            match = re.search(r'tvg-id="([^"]+)"', linea, re.I)
            if match and match.group(1).strip():
                clave = "id:" + normalizar(match.group(1))
            else:
                clave = "name:" + categoria + ":" + normalizar(extraer_nombre(linea))
            if (
                clave in {"name::", avatar_id}
                or (clave.startswith("id:") and clave[3:] in ids_pluto_omitidos)
            ):
                continue
            vistos_categoria = vistos.setdefault(categoria, set())
            if clave not in vistos_categoria:
                vistos_categoria.add(clave)
                resultado.setdefault(categoria, []).append(clave)
        return resultado

    anterior = firmas_por_categoria(lineas_anteriores)
    actual = firmas_por_categoria(lineas_nuevas)
    for categoria in set(anterior) | set(actual):
        if categoria in categorias_omitidas:
            continue
        orden_anterior = anterior.get(categoria, [])
        orden_actual = actual.get(categoria, [])
        conjunto_anterior = set(orden_anterior)
        conjunto_actual = set(orden_actual)
        anterior_vigente = [clave for clave in orden_anterior if clave in conjunto_actual]
        actual_anterior = [clave for clave in orden_actual if clave in conjunto_anterior]
        if anterior_vigente != actual_anterior:
            posicion = next(
                (
                    indice for indice, (antes, despues)
                    in enumerate(zip(anterior_vigente, actual_anterior))
                    if antes != despues
                ),
                min(len(anterior_vigente), len(actual_anterior)),
            )
            antes = anterior_vigente[posicion:posicion + 4]
            despues = actual_anterior[posicion:posicion + 4]
            raise RuntimeError(
                "ORDEN BLOQUEADO: la actualización reordenó canales dentro de "
                f"la categoría '{categoria}'. Primera diferencia en posición {posicion}: "
                f"antes={antes}; después={despues}."
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
    """Retira Pluto ES solo de Anime por nombre o identidad de fuente, ubica Avatar y añade American Ninja Warrior."""
    ids_pluto_es_anime = {str(x).lower() for x in (ids_pluto_es_anime or set())}
    prefijo = []
    bloques = []
    avatar = []
    eliminados_pluto_es_anime = 0
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
        bloque = lineas[inicio:j]
        categoria = normalizar(extraer_categoria(bloque[0]))
        nombre = extraer_nombre(bloque[0])
        url_bloque = next((x.strip() for x in bloque[1:] if url_es_valida(x.strip())), "")
        identidad = extraer_pluto_id(url_bloque)
        if not identidad:
            m_identidad = re.search(r'tvg-id="([a-f0-9]{20,})"', bloque[0], re.I)
            identidad = m_identidad.group(1).lower() if m_identidad else ""
        es_pluto_es = "[pluto es]" in normalizar(nombre) or bool(identidad and identidad in ids_pluto_es_anime)
        if categoria == "anime" and es_pluto_es:
            eliminados_pluto_es_anime += 1
            i = j
            continue
        if normalizar(nombre).startswith("avatar: la leyenda de aang"):
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
            raise RuntimeError("No existe Competencia para agregar American Ninja Warrior.")
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
        f"Avatar movidos={len(avatar)}; American Ninja Warrior agregado={xumo_agregado}."
    )
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
                lineas, iptvsv_reclasificados, iptvsv_conflictos = reclasificar_iptvsv_existente(
                    lineas,
                    canales,
                    categorias,
                )
                if iptvsv_reclasificados:
                    print(f"  -> IPTVSV URLs existentes reclasificadas: {iptvsv_reclasificados}")
                if iptvsv_conflictos:
                    print(f"  -> IPTVSV conflictos de categoría por URL: {iptvsv_conflictos}")
            pais_fuente = next(
                (pais for clave, pais in PAIS_POR_FUENTE.items()
                 if clave.lower() in fuente.lower()),
                None,
            )
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
                # La referencia excluye Pluto España únicamente dentro de Anime.
                if (
                    "pluto_es.m3u" in fuente.lower()
                    and normalizar(canal.get("categoria", "")) == "anime"
                ):
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

    # 13) Protección de no-regresión: ningún canal no-Pluto que ya existía
    # puede desaparecer por una limpieza interna accidental.
    lineas, no_pluto_restaurados = restaurar_no_pluto_existente(
        lineas,
        bloques_no_pluto_iniciales,
    )
    if no_pluto_restaurados:
        print(f"Autorreparación: {no_pluto_restaurados} canales no-Pluto restaurados.")

    # 14) Última barrera: deduplicación exacta después de cualquier autorreparación.
    # Así una restauración nunca puede volver a introducir una URL duplicada.
    lineas, duplicados_post_restauracion, _ = limpiar_duplicados_globales_y_carpetas_especiales(lineas)
    if duplicados_post_restauracion:
        print(f"Deduplicación final tras autorreparación: {duplicados_post_restauracion} duplicados eliminados.")

    # Consolidar de nuevo las categorías después de la autorreparación.
    # Esto evita que un canal restaurado genere un bloque físico separado.
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

    # Aplicar las correcciones fijas de la referencia antes de publicar.
    lineas = aplicar_ajustes_referencia(lineas, ids_pluto_es_anime)

    # Orden fijo de entretenimiento: bloque inicial, MAGMA alfabético y
    # canales originales alfabéticos. Se valida la cobertura MAGMA antes de escribir.
    lineas, orden_entretenimiento = ordenar_bloques_magma_y_originales(lineas, session)
    print(
        "Orden entretenimiento: "
        f"{orden_entretenimiento['fijos']} fijos; "
        f"{orden_entretenimiento['magma']} MAGMA; "
        f"{orden_entretenimiento['originales']} originales."
    )
    total_final = sum(1 for x in lineas if x.startswith("#EXTINF"))

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

    # SOLO AHORA se publica la principal: aplicar las directivas sobre la
    # representación final, para que ninguna transformación posterior las
    # elimine. Pluto queda excluido por diseño.
    lineas, reconexiones_agregadas = aplicar_reconexion_por_canal(lineas)
    validar_orden_canales(
        lineas_iniciales,
        lineas,
        categorias_reordenables={"Entretenimiento / Cine / Series"},
        ids_pluto_omitidos=ids_pluto_orden_protegidos,
    )
    print(f"Reconexión/caché aplicados en salida final: {reconexiones_agregadas}")

    texto_final = "\n".join(lineas)
    if not texto_final.endswith("\n"):
        texto_final += "\n"

    PRINCIPAL.write_text(
        texto_final,
        encoding="utf-8",
        newline="\n",
    )

    # Validación final después del autorreparo: una representación por ID
    # aceptado es suficiente; no se exige conservar cada JWT regional.
    ids_pluto_finales_actualizados = set()
    for i_post, linea_post in enumerate(lineas):
        if not linea_post.startswith("#EXTINF"):
            continue
        j_post = i_post + 1
        while j_post < len(lineas) and lineas[j_post].startswith("#"):
            j_post += 1
        if j_post < len(lineas) and url_es_valida(lineas[j_post].strip()):
            identidad_post = identidad_pluto(linea_post, lineas[j_post].strip())
            if identidad_post:
                ids_pluto_finales_actualizados.add(identidad_post)

    ids_pluto_faltantes = {
        identidad
        for identidad in ids_pluto_fuentes
        if identidad not in ids_pluto_finales_actualizados
    }
    if ids_pluto_faltantes:
        raise RuntimeError(
            "VALIDACION PLUTO FALLIDA: faltan "
            f"{len(ids_pluto_faltantes)} IDs de las fuentes propias "
            "después del autorreparo."
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
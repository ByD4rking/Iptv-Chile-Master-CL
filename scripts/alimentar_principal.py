from pathlib import Path
import re
import unicodedata
import requests
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent
PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"

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
    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/IPTVSV.m3u",
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
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_ar.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_cl.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_es.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_mx.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_latam.m3u",
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

    # Si Pluto ya declara exactamente una carpeta que existe en la
    # principal (por ejemplo "PLUTO TV"), respetamos esa carpeta.
    exacta = buscar_categoria_existente(categoria, categorias)
    if exacta:
        return exacta

    # Si declara una temática (por ejemplo "Anime" o "Pluto TV - Anime"),
    # continúa la misma lógica temática de la principal.
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

def deduplicar_pluto_existente(lineas):
    """
    Después de reemplazar terceros por nuestras URLs, elimina copias
    repetidas del mismo canal Pluto por ID. La primera aparición se conserva
    para respetar el orden de la principal.
    """
    salida = []
    ids_vistos = set()
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
        while j < len(lineas) and lineas[j].startswith("#"):
            bloque.append(lineas[j])
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            url = lineas[j].strip()
            bloque.append(url)
            j += 1

            if es_url_pluto(url):
                identidad = identidad_pluto(extinf, url)
                if identidad:
                    if identidad in ids_vistos:
                        eliminados += 1
                        i = j
                        continue
                    ids_vistos.add(identidad)

        salida.extend(bloque)
        i = j

    return salida, eliminados

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

        while j < len(lineas) and lineas[j].startswith("#"):
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
            eliminados_sin_reemplazo += 1
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

            while j < len(lineas) and lineas[j].startswith("#"):
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

def limpiar_total_otros_y_sin_nombre(lineas):
    """
    Revisa TOTAL, OTROS y entradas sin group-title sin destruir
    cabeceras ni metadatos M3U.
    - Entradas sin categoría: se eliminan.
    - TOTAL/OTROS duplicados por URL en otra categoría: se eliminan.
    - Únicos: se reclasifican cuando existe una categoría clara.
    - Si no se puede clasificar, se conserva en OTROS.
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
        while j < len(lineas) and lineas[j].startswith("#"):
            j += 1

        if j < len(lineas) and url_es_valida(lineas[j].strip()):
            bloques.append({
                "start": inicio,
                "end": j + 1,
                "extinf": extinf,
                "categoria": categoria,
                "nombre": nombre,
                "url": lineas[j].strip(),
            })
            i = j + 1
        else:
            i += 1

    categorias_por_url = defaultdict(set)
    for b in bloques:
        if b["categoria"]:
            categorias_por_url[b["url"]].add(normalizar(b["categoria"]))

    eliminar_urls = set()
    reemplazos = {}
    sin_nombre_eliminados = 0
    duplicados_eliminados = 0
    movidos = defaultdict(int)

    for idx, b in enumerate(bloques):
        cat = normalizar(b["categoria"])

        if not b["categoria"]:
            eliminar_urls.add(idx)
            sin_nombre_eliminados += 1
            continue

        if cat not in {"total", "otros"}:
            continue

        otras = {
            x for x in categorias_por_url[b["url"]]
            if x not in {"total", "otros"}
        }

        if otras:
            eliminar_urls.add(idx)
            duplicados_eliminados += 1
            continue

        destino = determinar_destino(
            b["categoria"],
            b["nombre"],
            None,
            categorias,
        )

        if destino and normalizar(destino) not in {"total", "otros"}:
            reemplazos[idx] = destino
            movidos[destino] += 1

    salida = []
    bloque_idx = 0
    i = 0

    while i < len(lineas):
        if (
            bloque_idx < len(bloques)
            and i == bloques[bloque_idx]["start"]
        ):
            b = bloques[bloque_idx]
            idx = bloque_idx
            bloque_idx += 1

            if idx in eliminar_urls:
                i = b["end"]
                continue

            if idx in reemplazos:
                salida.append(
                    reemplazar_categoria(
                        b["extinf"],
                        reemplazos[idx],
                    )
                )
                i = b["start"] + 1
                continue

            # Bloque sin cambios: copiarlo exactamente.
            salida.extend(lineas[b["start"]:b["end"]])
            i = b["end"]
            continue

        salida.append(lineas[i])
        i += 1

    return salida, {
        "sin_nombre_eliminados": sin_nombre_eliminados,
        "total_otros_duplicados_eliminados": duplicados_eliminados,
        "total_otros_movidos": sum(movidos.values()),
        "movidos_por_categoria": dict(movidos),
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

    # 2) Pluto: una sola entrada por channel ID en toda la principal.
    # Conserva la primera aparición y elimina copias regionales del mismo
    # canal, aunque tengan URLs Pluto distintas.
    lineas, pluto_duplicados_existentes = deduplicar_pluto_existente(lineas)

    # 3) Limpieza de TOTAL, OTROS y categoría vacía.
    lineas, limpieza = limpiar_total_otros_y_sin_nombre(lineas)

    categorias = categorias_de_lineas(lineas)
    urls_globales = mapa_urls_principal(lineas)

    # IDs Pluto ya presentes en la principal. Se usan además de la URL para
    # impedir que una misma señal Pluto entre varias veces con URLs regionales
    # distintas.
    ids_pluto_globales = set()
    i_pluto = 0
    while i_pluto < len(lineas):
        if lineas[i_pluto].startswith("#EXTINF"):
            extinf_pluto = lineas[i_pluto]
            j_pluto = i_pluto + 1
            while j_pluto < len(lineas) and lineas[j_pluto].startswith("#"):
                j_pluto += 1
            if j_pluto < len(lineas) and url_es_valida(lineas[j_pluto].strip()):
                url_pluto = lineas[j_pluto].strip()
                if es_url_pluto(url_pluto):
                    identidad = identidad_pluto(extinf_pluto, url_pluto)
                    if identidad:
                        ids_pluto_globales.add(identidad)
                i_pluto = j_pluto + 1
                continue
        i_pluto += 1

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

            nuevos = 0
            for canal in canales:
                destino = determinar_destino(
                    canal.get("categoria", ""),
                    canal.get("nombre", ""),
                    pais_fuente,
                    categorias,
                )

                # Si no existe una categoría equivalente, se permite
                # crearla usando la categoría declarada por la fuente.
                if not destino:
                    destino = canal.get("categoria", "").strip()
                if not destino or normalizar(destino) in {"total", "otros"}:
                    destino = "OTROS"

                if agregar_bloque(canal, destino, urls_globales, bloques_nuevos):
                    agregados_normales += 1
                    nuevos += 1
                else:
                    omitidos_duplicados += 1
            print(f"  -> nuevos: {nuevos}")
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
                    # Pluto puede crear una categoría temática nueva
                    # si la fuente declara una categoría útil.
                    destino = canal.get("categoria", "").strip()

                if not destino:
                    sin_categoria += 1
                    continue

                identidad = identidad_pluto(canal.get("extinf", ""), canal.get("url", ""))
                if identidad and identidad in ids_pluto_globales:
                    omitidos_duplicados += 1
                    continue

                if agregar_bloque(canal, destino, urls_globales, bloques_nuevos):
                    if identidad:
                        ids_pluto_globales.add(identidad)
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

    # 3) Insertar nuevos canales sin mover los existentes.
    if bloques_nuevos:
        lineas = insertar_bloques(lineas, bloques_nuevos)

    # 4) Validación final de URLs duplicadas globales.
    vistos = set()
    duplicados_finales = 0
    for linea in lineas:
        u = linea.strip()
        if url_es_valida(u):
            if u in vistos:
                duplicados_finales += 1
            vistos.add(u)

    texto_final = "\n".join(lineas)
    if not texto_final.endswith("\n"):
        texto_final += "\n"

    PRINCIPAL.write_text(
        texto_final,
        encoding="utf-8",
        newline="\n",
    )

    total_final = sum(1 for x in lineas if x.startswith("#EXTINF"))

    print("\n" + "=" * 72)
    print("RESUMEN")
    print("=" * 72)
    print(f"Canales iniciales:                 {total_inicial}")
    print(f"Pluto terceros reemplazados:         {pluto_reemplazo["reemplazados"]}")
    print(f"Pluto terceros sin reemplazo:        {pluto_reemplazo["eliminados_sin_reemplazo"]}")
    print(f"Pluto ya propios conservados:        {pluto_reemplazo["ya_propios"]}")
    print(f"Pluto duplicados por channel ID:      {pluto_duplicados_existentes}")
    print(f"Sin categoría eliminados:           {limpieza['sin_nombre_eliminados']}")
    print(f"TOTAL/OTROS duplicados eliminados:  {limpieza['total_otros_duplicados_eliminados']}")
    print(f"TOTAL/OTROS reclasificados:          {limpieza['total_otros_movidos']}")
    print(f"Canales colaborador agregados:      {agregados_normales}")
    print(f"Canales Pluto propios agregados:    {agregados_pluto}")
    print(f"Duplicados omitidos al agregar:     {omitidos_duplicados}")
    print(f"Duplicados finales detectados:      {duplicados_finales}")
    print(f"Fuentes con error:                  {errores}")
    print(f"Canales finales:                    {total_final}")

    if limpieza["movidos_por_categoria"]:
        print("\nTOTAL/OTROS movidos por categoría:")
        for cat, cantidad in sorted(limpieza["movidos_por_categoria"].items()):
            print(f"  - {cat}: {cantidad}")

    print("\nREGLAS ACTIVAS:")
    print("  - La principal conserva su orden existente.")
    print("  - IPTVSV.m3u y demás fuentes son complementarias.")
    print("  - Dedupe global por URL.")
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

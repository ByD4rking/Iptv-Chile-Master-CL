
from pathlib import Path
import re
import unicodedata
import requests

BASE = Path(__file__).resolve().parent.parent

PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"

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

PAIS_POR_FUENTE = {
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

def normalizar(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()

def pais_de_fuente(url):
    for clave, pais in PAIS_POR_FUENTE.items():
        if clave.lower() in url.lower():
            return pais
    return None

def extraer_categoria(linea):
    patrones = [
        r'group-title="([^"]+)"',
        r'group-title="([^"]*)"',
    ]

    for patron in patrones:
        m = re.search(patron, linea, re.I)
        if m:
            return m.group(1).strip()

    return ""

def extraer_nombre(linea):
    if "," in linea:
        return linea.split(",", 1)[1].strip()
    return ""

def url_es_valida(url):
    return bool(re.match(r"^https?://", url.strip(), re.I))

def determinar_destino(categoria, nombre, pais_fuente, categorias):
    texto = normalizar((categoria or "") + " " + (nombre or ""))

    # ========================================================
    # CHILE: SIEMPRE CHILE
    # ========================================================
    if pais_fuente == "chile":`r`n        return "CHILE"


    # ========================================================
    # PAÍS EXPLÍCITO
    # ========================================================
    paises = {
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

    pais = pais_fuente

    if not pais:
        for posible, aliases in paises.items():
            if any(normalizar(a) in texto for a in aliases):
                pais = posible
                break

    if pais:
        for cat in categorias:
            ncat = normalizar(cat)

            if pais == "peru":
                if "peru" in ncat and "radio" not in ncat:
                    return cat

            elif pais == "brasil":
                if "brasil" in ncat or "brazil" in ncat:
                    return cat

            elif pais == "espana":
                if "espana" in ncat or "spain" in ncat:
                    return cat

            elif pais == "costa rica":
                if "costa" in ncat and "rica" in ncat:
                    return cat

            elif pais == "republica dominicana":
                if "republicana" in ncat or (
                    "republica" in ncat and "dominicana" in ncat
                ):
                    return cat

            elif pais in ncat:
                return cat

    # ========================================================
    # CATEGORÍAS TEMÁTICAS EXISTENTES
    # ========================================================
    palabras = [
        "anime",
        "comedia",
        "general",
        "deportes",
        "sport",
        "musica",
        "music",
        "religioso",
        "religiosos",
        "peliculas",
        "peliculas",
        "series",
        "infantil",
        "noticias",
        "documentales",
    ]

    for palabra in palabras:
        if palabra in texto:
            for cat in categorias:
                if palabra in normalizar(cat):
                    return cat

    return None

def parsear_m3u(texto):
    lineas = texto.splitlines()
    resultado = []

    actual = None

    for linea in lineas:
        linea = linea.strip()

        if not linea:
            continue

        if linea.startswith("#EXTINF"):
            actual = {
                "extinf": linea,
                "nombre": extraer_nombre(linea),
                "categoria": extraer_categoria(linea),
            }

        elif not linea.startswith("#") and url_es_valida(linea):
            if actual:
                actual["url"] = linea
                resultado.append(actual)
                actual = None

    return resultado

print("=" * 70)
print("       ALIMENTADOR DE LISTA PRINCIPAL")
print("=" * 70)

if not PRINCIPAL.exists():
    print("ERROR: no existe:")
    print(PRINCIPAL)
    raise SystemExit(1)

# ------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------
BACKUP.write_bytes(PRINCIPAL.read_bytes())
print()
print("Backup creado:")
print(BACKUP)

texto_principal = PRINCIPAL.read_text(
    encoding="utf-8",
    errors="replace"
)

lineas_principal = texto_principal.splitlines()

# ------------------------------------------------------------
# CATEGORÍAS EXISTENTES EN LA PRINCIPAL
# ------------------------------------------------------------
categorias = []

for linea in lineas_principal:
    if linea.startswith("#EXTINF"):
        cat = extraer_categoria(linea)

        if cat and cat not in categorias:
            categorias.append(cat)

print()
print("Categorías detectadas:", len(categorias))

# ------------------------------------------------------------
# URLs EXISTENTES
# ------------------------------------------------------------
urls_existentes = set()

for linea in lineas_principal:
    linea = linea.strip()

    if url_es_valida(linea):
        urls_existentes.add(linea)

print("URLs existentes:", len(urls_existentes))

agregados = 0
omitidos = 0
errores = 0

bloques_nuevos = []

# ------------------------------------------------------------
# PROCESAR FUENTES
# ------------------------------------------------------------
for i, fuente in enumerate(FUENTES, 1):

    print()
    print(f"[FUENTE {i}/{len(FUENTES)}]")
    print("-" * 60)
    print(fuente)

    try:
        r = requests.get(
            fuente,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        r.raise_for_status()

        canales = parsear_m3u(r.text)

        if not canales:
            print("  -> Sin canales #EXTINF.")
            continue

        pais_fuente = pais_de_fuente(fuente)

        nuevos_fuente = 0

        for canal in canales:

            url = canal["url"].strip()

            if url in urls_existentes:
                omitidos += 1
                continue

            destino = determinar_destino(
                canal.get("categoria", ""),
                canal.get("nombre", ""),
                pais_fuente,
                categorias,
            )

            # Si no encontramos carpeta compatible,
            # NO inventamos una carpeta nueva.
            if not destino:
                destino = canal.get("categoria", "").strip()

            if not destino:
                destino = "OTROS"

            # ------------------------------------------------
            # Crear EXTINF conservando los datos originales
            # pero cambiando group-title al destino.
            # ------------------------------------------------
            extinf = canal["extinf"]

            if re.search(r'group-title="[^"]*"', extinf, re.I):
                extinf = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{destino}"',
                    extinf,
                    count=1,
                    flags=re.I
                )
            else:
                extinf = extinf.replace(
                    "#EXTINF:",
                    f'#EXTINF:-1 group-title="{destino}"',
                    1
                )

            bloques_nuevos.append(
                extinf + "\n" + url
            )

            urls_existentes.add(url)
            agregados += 1
            nuevos_fuente += 1

        print(f"  -> URLs nuevas agregadas: {nuevos_fuente}")

    except Exception as e:
        errores += 1
        print(f"  -> ERROR: {e}")

# ------------------------------------------------------------
# GUARDAR
# ------------------------------------------------------------
if bloques_nuevos:
# ------------------------------------------------------------
# PROCESAR LISTAS LOCALES DE LA CARPETA CHILE
# ------------------------------------------------------------
CARPETA_CHILE = BASE / "CHILE"

if CARPETA_CHILE.exists():
    listas_chile = sorted(
        CARPETA_CHILE.glob("*.m3u")
    )

    print()
    print("=" * 70)
    print("LISTAS LOCALES DE CHILE")
    print("=" * 70)

    print(f"Carpeta: {CARPETA_CHILE}")
    print(f"Listas encontradas: {len(listas_chile)}")

    for lista_chile in listas_chile:

        print()
        print(f"[CHILE] {lista_chile.name}")

        try:
            texto_chile = lista_chile.read_text(
                encoding="utf-8",
                errors="replace"
            )

            canales_chile = parsear_m3u(texto_chile)

            nuevos_chile = 0

            for canal in canales_chile:

                url = canal["url"].strip()

                if url in urls_existentes:
                    omitidos += 1
                    continue

                extinf = canal["extinf"]

                if re.search(
                    r'group-title="[^"]*"',
                    extinf,
                    re.I
                ):
                    extinf = re.sub(
                        r'group-title="[^"]*"',
                        'group-title="CHILE"',
                        extinf,
                        count=1,
                        flags=re.I
                    )
                else:
                    extinf = extinf.replace(
                        "#EXTINF:",
                        '#EXTINF:-1 group-title="CHILE"',
                        1
                    )

                bloques_nuevos.append(
                    extinf + "\n" + url
                )

                urls_existentes.add(url)

                agregados += 1
                nuevos_chile += 1

            print(
                f"  -> URLs nuevas agregadas: {nuevos_chile}"
            )

        except Exception as e:
            errores += 1
            print(f"  -> ERROR: {e}")

else:
    print()
    print("No existe la carpeta CHILE.")


# ------------------------------------------------------------
# GUARDAR
# ------------------------------------------------------------
if bloques_nuevos:

    if not texto_principal.endswith("\n"):
        texto_principal += "\n"

    texto_principal += "\n".join(bloques_nuevos) + "\n"

    PRINCIPAL.write_text(
        texto_principal,
        encoding="utf-8",
        newline="\n"
    )

    
if not texto_principal.endswith("\n"):
        texto_principal += "\n"

    texto_principal += "\n".join(bloques_nuevos) + "\n"

    PRINCIPAL.write_text(
        texto_principal,
        encoding="utf-8",
        newline="\n"
    )

print()
print("=" * 70)
print("       ALIMENTACIÓN TERMINADA")
print("=" * 70)
print(f"URLs nuevas agregadas: {agregados}")
print(f"URLs ya existentes:    {omitidos}")
print(f"Fuentes con error:     {errores}")
print()
print("Archivo actualizado:")
print(PRINCIPAL)
print()
print("Backup:")
print(BACKUP)
print()
print("REGLAS:")
print("  - No duplica URLs.")
print("  - Respeta las categorías existentes.")
print("  - Chile -> CHILE.")
print("  - Perú -> carpeta Perú existente.")
print("  - Bolivia -> carpeta Bolivia existente.")
print("  - Argentina -> carpeta Argentina existente.")
print("  - Brasil -> carpeta Brasil existente.")
print("  - Colombia -> carpeta Colombia existente.")
print("  - Ecuador -> carpeta Ecuador existente.")
print("  - Venezuela -> carpeta Venezuela existente.")
print("  - Paraguay -> carpeta Paraguay existente.")
print("  - México -> carpeta México existente.")
print("  - España -> carpeta España existente.")
print("  - No crea una carpeta por cada fuente.")
print("=" * 70)


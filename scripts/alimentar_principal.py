from pathlib import Path
import re
import unicodedata
import requests


BASE = Path(__file__).resolve().parent.parent

PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"


# ============================================================
# FUENTES NORMALES
# ============================================================

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
# FUENTES PLUTO
# ============================================================

FUENTES_PLUTO = [
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_es.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_ar.m3u",
    "https://raw.githubusercontent.com/BuddyChewChew/pluto/main/pluto_mx.m3u",
    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.ES.m3u",
    "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u",
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


# ============================================================
# NORMALIZAR
# ============================================================

def normalizar(s):
    s = unicodedata.normalize("NFD", s or "")

    s = "".join(
        c for c in s
        if unicodedata.category(c) != "Mn"
    )

    return re.sub(r"\s+", " ", s.lower()).strip()


# ============================================================
# PAIS DE FUENTE
# ============================================================

def pais_de_fuente(url):
    url_normalizada = url.lower()

    for clave, pais in PAIS_POR_FUENTE.items():

        if clave.lower() in url_normalizada:
            return pais

    return None


# ============================================================
# EXTRAER CATEGORIA
# ============================================================

def extraer_categoria(linea):

    m = re.search(
        r'group-title="([^"]*)"',
        linea,
        re.I
    )

    if m:
        return m.group(1).strip()

    return ""


# ============================================================
# EXTRAER NOMBRE
# ============================================================

def extraer_nombre(linea):

    if "," in linea:
        return linea.split(",", 1)[1].strip()

    return ""


# ============================================================
# URL VALIDA
# ============================================================

def url_es_valida(url):

    return bool(
        re.match(
            r"^https?://",
            url.strip(),
            re.I
        )
    )


# ============================================================
# PARSEAR M3U
# ============================================================

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
            }

        elif (
            not linea.startswith("#")
            and url_es_valida(linea)
        ):

            if actual:

                actual["url"] = linea

                resultado.append(actual)

                actual = None

    return resultado


# ============================================================
# REEMPLAZAR CATEGORIA
# ============================================================

def reemplazar_categoria(extinf, destino):

    if re.search(
        r'group-title="[^"]*"',
        extinf,
        re.I
    ):

        return re.sub(
            r'group-title="[^"]*"',
            f'group-title="{destino}"',
            extinf,
            count=1,
            flags=re.I
        )

    return extinf.replace(
        "#EXTINF:",
        f'#EXTINF:-1 group-title="{destino}"',
        1
    )


# ============================================================
# BUSCAR CATEGORIA EXISTENTE
#
# IMPORTANTE:
# Se conserva el nombre EXACTO de la principal.
#
# Ejemplo:
# Principal: "Perú"
# Pluto/fuente: "PERU"
#
# Resultado: "Perú"
# ============================================================

def buscar_categoria_existente(nombre, categorias):

    objetivo = normalizar(nombre)

    if not objetivo:
        return None

    for categoria in categorias:

        if normalizar(categoria) == objetivo:
            return categoria

    return None


# ============================================================
# DETERMINAR DESTINO FUENTES NORMALES
#
# ESTA ES LA LOGICA ORIGINAL.
# ============================================================

def determinar_destino(
    categoria,
    nombre,
    pais_fuente,
    categorias
):

    texto = normalizar(
        f"{categoria or ''} {nombre or ''}"
    )

    # --------------------------------------------------------
    # CHILE
    # --------------------------------------------------------

    if pais_fuente == "chile":

        categoria_chile = buscar_categoria_existente(
            "CHILE",
            categorias
        )

        if categoria_chile:
            return categoria_chile

        return "CHILE"

    # --------------------------------------------------------
    # PAIS DETERMINADO POR LA FUENTE
    # --------------------------------------------------------

    if pais_fuente in CATEGORIAS_PAIS:

        categoria_pais = CATEGORIAS_PAIS[pais_fuente]

        encontrada = buscar_categoria_existente(
            categoria_pais,
            categorias
        )

        if encontrada:
            return encontrada

    # --------------------------------------------------------
    # PAIS DETECTADO POR NOMBRE/CATEGORIA
    # --------------------------------------------------------

    aliases = {

        "peru": ["peru"],

        "bolivia": ["bolivia"],

        "argentina": ["argentina"],

        "brasil": [
            "brasil",
            "brazil",
        ],

        "colombia": ["colombia"],

        "ecuador": ["ecuador"],

        "venezuela": ["venezuela"],

        "paraguay": ["paraguay"],

        "mexico": ["mexico"],

        "espana": [
            "espana",
            "spain",
        ],

        "costa rica": [
            "costa rica",
        ],

        "republica dominicana": [
            "republica dominicana",
            "dominican republic",
        ],
    }

    for pais, nombres in aliases.items():

        if any(
            normalizar(alias) in texto
            for alias in nombres
        ):

            categoria_pais = CATEGORIAS_PAIS[pais]

            encontrada = buscar_categoria_existente(
                categoria_pais,
                categorias
            )

            if encontrada:
                return encontrada

    # --------------------------------------------------------
    # CATEGORIAS TEMATICAS EXISTENTES
    # --------------------------------------------------------

    equivalencias = [

        ("anime", [
            "anime",
        ]),

        ("comedia", [
            "comedia",
        ]),

        ("general", [
            "general",
        ]),

        ("deportes", [
            "deportes",
            "sport",
        ]),

        ("musica", [
            "musica",
            "music",
        ]),

        ("religiosos", [
            "religioso",
            "religiosos",
        ]),

        ("cine", [
            "cine",
            "peliculas",
        ]),

        ("series", [
            "series",
        ]),

        ("infantiles", [
            "infantil",
            "infantiles",
        ]),

        ("informativos", [
            "noticias",
            "informativos",
        ]),

        ("documentales", [
            "documentales",
        ]),
    ]

    for palabra, aliases_categoria in equivalencias:

        if any(
            alias in texto
            for alias in aliases_categoria
        ):

            for categoria_existente in categorias:

                categoria_normalizada = normalizar(
                    categoria_existente
                )

                if any(
                    alias in categoria_normalizada
                    for alias in aliases_categoria
                ):

                    return categoria_existente

    return None


# ============================================================
# DETERMINAR DESTINO PLUTO
#
# Pluto NO utiliza el pais de la fuente.
#
# Se analiza categoria + nombre.
# ============================================================

def determinar_destino_pluto(
    categoria,
    nombre,
    categorias
):

    texto = normalizar(
        f"{categoria or ''} {nombre or ''}"
    )

    # --------------------------------------------------------
    # ANIME
    # --------------------------------------------------------

    if re.search(r"\banime\b", texto):

        destino = buscar_categoria_existente(
            "ANIME",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # INFANTIL
    #
    # Teen / Kids / Infantil
    # --------------------------------------------------------

    if re.search(
        r"\b(teen|kids|kid|infantil|infantiles)\b",
        texto
    ):

        for candidato in [
            "INFANTILES",
            "INFANTIL",
        ]:

            destino = buscar_categoria_existente(
                candidato,
                categorias
            )

            if destino:
                return destino

    # --------------------------------------------------------
    # DEPORTES
    # --------------------------------------------------------

    if re.search(
        r"\b(deporte|deportes|sport|sports)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "DEPORTES",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # MUSICA
    # --------------------------------------------------------

    if re.search(
        r"\b(musica|music)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "MUSICA",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # CINE
    # --------------------------------------------------------

    if re.search(
        r"\b(cine|peliculas|pelicula|movies|movie)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "CINE",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # SERIES
    # --------------------------------------------------------

    if re.search(
        r"\b(series|serie)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "SERIES",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # ENTRETENIMIENTO
    #
    # Reto incluido explícitamente.
    # --------------------------------------------------------

    if re.search(
        r"\b(entretenimiento|entertainment|reto)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "ENTRETENIMIENTO",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # COMEDIA
    # --------------------------------------------------------

    if re.search(
        r"\b(comedia|comedy)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "COMEDIA",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # RELIGIOSOS
    # --------------------------------------------------------

    if re.search(
        r"\b(religioso|religiosos|religion)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "RELIGIOSOS",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # DOCUMENTALES
    # --------------------------------------------------------

    if re.search(
        r"\b(documental|documentales|documentary)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "DOCUMENTALES",
            categorias
        )

        if destino:
            return destino

    # --------------------------------------------------------
    # INFORMATIVOS
    # --------------------------------------------------------

    if re.search(
        r"\b(noticias|noticia|informativos|news)\b",
        texto
    ):

        destino = buscar_categoria_existente(
            "INFORMATIVOS",
            categorias
        )

        if destino:
            return destino

    return None


# ============================================================
# OBTENER BLOQUES DE CATEGORIAS
#
# Se utiliza para insertar Pluto dentro de la categoría
# correspondiente sin mover los canales existentes.
# ============================================================

def encontrar_rango_categoria(lineas, categoria):

    categoria_normalizada = normalizar(categoria)

    inicio = None
    fin = None

    for i, linea in enumerate(lineas):

        if not linea.startswith("#EXTINF"):
            continue

        categoria_linea = extraer_categoria(linea)

        if normalizar(categoria_linea) == categoria_normalizada:

            if inicio is None:
                inicio = i

            fin = i

        elif inicio is not None:
            break

    if inicio is None:
        return None

    return inicio, fin


# ============================================================
# CONSTRUIR BLOQUE
# ============================================================

def construir_bloque(canal, destino):

    extinf = reemplazar_categoria(
        canal["extinf"],
        destino
    )

    return [
        extinf,
        canal["url"].strip(),
    ]


# ============================================================
# AGREGAR FUENTE NORMAL
#
# Para las fuentes normales:
#
# - país -> carpeta
# - duplicado dentro de la categoría destino
# - se permite la misma URL en otra categoría
# ============================================================

def agregar_canal_normal(
    canal,
    destino,
    urls_por_categoria,
    bloques_nuevos
):

    url = canal["url"].strip()

    categoria_key = normalizar(destino)

    if url in urls_por_categoria.get(
        categoria_key,
        set()
    ):

        return False

    bloque = construir_bloque(
        canal,
        destino
    )

    bloques_nuevos.append({
        "tipo": "normal",
        "categoria": destino,
        "bloque": bloque,
    })

    urls_por_categoria.setdefault(
        categoria_key,
        set()
    ).add(url)

    return True


# ============================================================
# AGREGAR PLUTO
# ============================================================

def agregar_canal_pluto(
    canal,
    destino,
    urls_por_categoria,
    bloques_pluto
):

    url = canal["url"].strip()

    categoria_key = normalizar(destino)

    if url in urls_por_categoria.get(
        categoria_key,
        set()
    ):

        return False

    bloque = construir_bloque(
        canal,
        destino
    )

    bloques_pluto.append({
        "categoria": destino,
        "bloque": bloque,
    })

    urls_por_categoria.setdefault(
        categoria_key,
        set()
    ).add(url)

    return True


# ============================================================
# INSERTAR BLOQUES EN LA PRINCIPAL
#
# Los canales existentes NO se modifican.
#
# Los nuevos se insertan dentro de su categoría.
# ============================================================

def insertar_bloques_en_principal(
    lineas,
    bloques_nuevos,
    categorias
):

    if not bloques_nuevos:
        return lineas

    resultado = list(lineas)

    # --------------------------------------------------------
    # Agrupar por categoría manteniendo el orden de llegada
    # --------------------------------------------------------

    agrupados = {}

    for item in bloques_nuevos:

        categoria = item["categoria"]

        clave = normalizar(categoria)

        agrupados.setdefault(
            clave,
            {
                "categoria": categoria,
                "bloques": [],
            }
        )

        agrupados[clave]["bloques"].append(
            item["bloque"]
        )

    # --------------------------------------------------------
    # Insertar de atrás hacia adelante.
    #
    # Esto evita que las posiciones cambien mientras
    # recorremos la lista.
    # --------------------------------------------------------

    posiciones = []

    for clave, datos in agrupados.items():

        rango = encontrar_rango_categoria(
            resultado,
            datos["categoria"]
        )

        if rango:

            inicio, fin = rango

            posiciones.append(
                (
                    fin + 1,
                    datos["bloques"]
                )
            )

    posiciones.sort(
        key=lambda x: x[0],
        reverse=True
    )

    for posicion, bloques in posiciones:

        insertar = []

        for bloque in bloques:

            insertar.extend(bloque)

        resultado[
            posicion:posicion
        ] = insertar

    return resultado


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("       ALIMENTADOR DE LISTA PRINCIPAL")
    print("=" * 70)

    if not PRINCIPAL.exists():

        print("ERROR: no existe:")
        print(PRINCIPAL)

        raise SystemExit(1)

    # --------------------------------------------------------
    # LEER PRINCIPAL
    # --------------------------------------------------------

    texto_principal = PRINCIPAL.read_text(
        encoding="utf-8",
        errors="replace"
    )

    lineas_principal = texto_principal.splitlines()

    # --------------------------------------------------------
    # CATEGORIAS EXISTENTES
    # --------------------------------------------------------

    categorias = []

    for linea in lineas_principal:

        if linea.startswith("#EXTINF"):

            categoria = extraer_categoria(linea)

            if categoria:

                if not any(
                    normalizar(categoria)
                    == normalizar(c)
                    for c in categorias
                ):

                    categorias.append(categoria)

    print()
    print(
        f"Categorías detectadas: {len(categorias)}"
    )

    # --------------------------------------------------------
    # URLS POR CATEGORIA
    #
    # IMPORTANTE:
    # La misma URL puede existir en diferentes categorías.
    # --------------------------------------------------------

    urls_por_categoria = {}

    categoria_actual = None

    for linea in lineas_principal:

        linea_limpia = linea.strip()

        if linea_limpia.startswith("#EXTINF"):

            categoria_actual = extraer_categoria(
                linea_limpia
            )

        elif url_es_valida(linea_limpia):

            if categoria_actual:

                clave = normalizar(
                    categoria_actual
                )

                urls_por_categoria.setdefault(
                    clave,
                    set()
                ).add(
                    linea_limpia
                )

    # --------------------------------------------------------
    # BLOQUES NUEVOS
    # --------------------------------------------------------

    bloques_normales = []

    bloques_pluto = []

    agregados = 0
    omitidos = 0
    errores = 0

    # --------------------------------------------------------
    # SESSION HTTP
    # --------------------------------------------------------

    session = requests.Session()

    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    # ========================================================
    # FUENTES NORMALES
    # ========================================================

    for i, fuente in enumerate(
        FUENTES,
        1
    ):

        print()
        print(
            f"[FUENTE {i}/{len(FUENTES)}]"
        )

        print("-" * 60)
        print(fuente)

        try:

            respuesta = session.get(
                fuente,
                timeout=30
            )

            respuesta.raise_for_status()

            canales = parsear_m3u(
                respuesta.text
            )

            if not canales:

                print(
                    "  -> Sin canales #EXTINF."
                )

                continue

            pais_fuente = pais_de_fuente(
                fuente
            )

            nuevos_fuente = 0

            for canal in canales:

                destino = determinar_destino(
                    canal.get("categoria", ""),
                    canal.get("nombre", ""),
                    pais_fuente,
                    categorias,
                )

                # ------------------------------------------------
                # Si no se pudo determinar una categoría,
                # conservar la lógica original.
                # ------------------------------------------------

                if not destino:

                    destino = canal.get(
                        "categoria",
                        ""
                    ).strip()

                if not destino:

                    destino = "OTROS"

                if agregar_canal_normal(
                    canal,
                    destino,
                    urls_por_categoria,
                    bloques_normales
                ):

                    agregados += 1
                    nuevos_fuente += 1

                else:

                    omitidos += 1

            print(
                f"  -> URLs nuevas agregadas: "
                f"{nuevos_fuente}"
            )

        except Exception as e:

            errores += 1

            print(
                f"  -> ERROR: {e}"
            )

    # ========================================================
    # LISTAS LOCALES DE CHILE
    # ========================================================

    CARPETA_CHILE = BASE / "CHILE"

    if CARPETA_CHILE.exists():

        listas_chile = sorted(
            CARPETA_CHILE.glob("*.m3u")
        )

        print()
        print("=" * 70)
        print("LISTAS LOCALES DE CHILE")
        print("=" * 70)

        print(
            f"Carpeta: {CARPETA_CHILE}"
        )

        print(
            f"Listas encontradas: "
            f"{len(listas_chile)}"
        )

        for lista_chile in listas_chile:

            print()
            print(
                f"[CHILE] "
                f"{lista_chile.name}"
            )

            try:

                texto_chile = lista_chile.read_text(
                    encoding="utf-8",
                    errors="replace"
                )

                canales_chile = parsear_m3u(
                    texto_chile
                )

                nuevos_chile = 0

                for canal in canales_chile:

                    destino = determinar_destino(
                        canal.get("categoria", ""),
                        canal.get("nombre", ""),
                        "chile",
                        categorias,
                    )

                    if not destino:

                        destino = "CHILE"

                    if agregar_canal_normal(
                        canal,
                        destino,
                        urls_por_categoria,
                        bloques_normales
                    ):

                        agregados += 1
                        nuevos_chile += 1

                    else:

                        omitidos += 1

                print(
                    f"  -> URLs nuevas agregadas: "
                    f"{nuevos_chile}"
                )

            except Exception as e:

                errores += 1

                print(
                    f"  -> ERROR: {e}"
                )

    else:

        print()
        print(
            "No existe la carpeta CHILE."
        )

    # ========================================================
    # PROCESAR PLUTO
    # ========================================================

    print()
    print("=" * 70)
    print("LISTAS PLUTO")
    print("=" * 70)

    for i, fuente in enumerate(
        FUENTES_PLUTO,
        1
    ):

        print()
        print(
            f"[PLUTO {i}/{len(FUENTES_PLUTO)}]"
        )

        print("-" * 60)
        print(fuente)

        try:

            respuesta = session.get(
                fuente,
                timeout=30
            )

            respuesta.raise_for_status()

            canales = parsear_m3u(
                respuesta.text
            )

            if not canales:

                print(
                    "  -> Sin canales #EXTINF."
                )

                continue

            nuevos_pluto = 0
            sin_categoria = 0

            for canal in canales:

                destino = determinar_destino_pluto(
                    canal.get("categoria", ""),
                    canal.get("nombre", ""),
                    categorias
                )

                # ------------------------------------------------
                # Pluto SOLO entra si encontramos una categoría
                # existente en la principal.
                #
                # NO crear OTROS para Pluto.
                # ------------------------------------------------

                if not destino:

                    sin_categoria += 1

                    print(
                        "  -> Pluto sin categoría: "
                        f"{canal.get('nombre', '')}"
                    )

                    continue

                if agregar_canal_pluto(
                    canal,
                    destino,
                    urls_por_categoria,
                    bloques_pluto
                ):

                    agregados += 1
                    nuevos_pluto += 1

                else:

                    omitidos += 1

            print(
                f"  -> Pluto nuevos: "
                f"{nuevos_pluto}"
            )

            if sin_categoria:

                print(
                    f"  -> Pluto sin clasificar: "
                    f"{sin_categoria}"
                )

        except Exception as e:

            errores += 1

            print(
                f"  -> ERROR: {e}"
            )

    # ========================================================
    # INSERTAR TODO EN LAS CATEGORIAS
    # ========================================================

    todos_los_bloques = (
        bloques_normales
        + bloques_pluto
    )

    if todos_los_bloques:

        lineas_finales = (
            insertar_bloques_en_principal(
                lineas_principal,
                todos_los_bloques,
                categorias
            )
        )

        texto_final = (
            "\n".join(lineas_finales)
        )

        if not texto_final.endswith("\n"):

            texto_final += "\n"

        PRINCIPAL.write_text(
            texto_final,
            encoding="utf-8",
            newline="\n"
        )

    # ========================================================
    # RESUMEN
    # ========================================================

    print()
    print("=" * 70)
    print("       ALIMENTACIÓN TERMINADA")
    print("=" * 70)

    print(
        f"URLs nuevas agregadas: {agregados}"
    )

    print(
        f"URLs ya existentes:    {omitidos}"
    )

    print(
        f"Fuentes con error:     {errores}"
    )

    print()
    print(
        "Archivo actualizado:"
    )

    print(PRINCIPAL)

    print()
    print("REGLAS:")

    print(
        "  - No duplica URLs dentro de la categoría."
    )

    print(
        "  - La misma URL puede existir en otra categoría."
    )

    print(
        "  - Respeta las categorías existentes."
    )

    print(
        "  - CL.m3u -> CHILE."
    )

    print(
        "  - AR.m3u -> ARGENTINA."
    )

    print(
        "  - MX.m3u -> MÉXICO."
    )

    print(
        "  - PE.m3u -> PERÚ."
    )

    print(
        "  - Etc. según la fuente."
    )

    print(
        "  - Listas locales de CHILE -> CHILE."
    )

    print(
        "  - Pluto se clasifica por categoría/nombre."
    )

    print(
        "  - Pluto NO crea categorías."
    )

    print(
        "  - Pluto se inserta dentro de su categoría."
    )

    print(
        "  - Teen/Kids -> INFANTILES."
    )

    print(
        "  - Reto -> ENTRETENIMIENTO."
    )

    print(
        "  - Anime -> ANIME."
    )

    print(
        "  - Música -> MUSICA."
    )

    print(
        "  - Deportes -> DEPORTES."
    )

    print(
        "  - Cine -> CINE."
    )

    print(
        "  - Series -> SERIES."
    )

    print(
        "  - No crea carpetas."
    )

    print(
        "  - No mueve canales existentes."
    )

    print(
        "  - No escribe dos veces."
    )

    print(
        "  - No crea backups automáticos."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()

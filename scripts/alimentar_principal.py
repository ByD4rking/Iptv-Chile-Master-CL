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
    s = "".join(
        c for c in s
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", s.lower()).strip()


def pais_de_fuente(url):
    url_normalizada = url.lower()

    for clave, pais in PAIS_POR_FUENTE.items():
        if clave.lower() in url_normalizada:
            return pais

    return None


def extraer_categoria(linea):
    m = re.search(
        r'group-title="([^"]*)"',
        linea,
        re.I
    )

    if m:
        return m.group(1).strip()

    return ""


def extraer_nombre(linea):
    if "," in linea:
        return linea.split(",", 1)[1].strip()

    return ""


def url_es_valida(url):
    return bool(
        re.match(
            r"^https?://",
            url.strip(),
            re.I
        )
    )


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
        return "CHILE"

    # --------------------------------------------------------
    # PAIS DETERMINADO POR LA FUENTE
    # --------------------------------------------------------
    if pais_fuente in CATEGORIAS_PAIS:
        categoria_pais = CATEGORIAS_PAIS[pais_fuente]

        if categoria_pais in categorias:
            return categoria_pais

    # --------------------------------------------------------
    # PAIS DETECTADO POR NOMBRE/CATEGORIA
    # --------------------------------------------------------
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

            if categoria_pais in categorias:
                return categoria_pais

    # --------------------------------------------------------
    # CATEGORIAS TEMATICAS EXISTENTES
    # --------------------------------------------------------
    equivalencias = [
        ("anime", ["anime"]),
        ("comedia", ["comedia"]),
        ("general", ["general"]),
        ("deportes", ["deportes", "sport"]),
        ("musica", ["musica", "music"]),
        ("religiosos", ["religioso", "religiosos"]),
        ("cine", ["cine", "peliculas"]),
        ("series", ["series"]),
        ("infantiles", ["infantil", "infantiles"]),
        ("informativos", ["noticias", "informativos"]),
        ("documentales", ["documentales"]),
    ]

    for palabra, aliases in equivalencias:
        if any(
            alias in texto
            for alias in aliases
        ):
            for categoria_existente in categorias:
                categoria_normalizada = normalizar(
                    categoria_existente
                )

                if any(
                    alias in categoria_normalizada
                    for alias in aliases
                ):
                    return categoria_existente

    return None


def agregar_canal(canal, pais_fuente, categorias,
                  urls_existentes, bloques_nuevos):
    url = canal["url"].strip()

    if url in urls_existentes:
        return False

    destino = determinar_destino(
        canal.get("categoria", ""),
        canal.get("nombre", ""),
        pais_fuente,
        categorias,
    )

    if not destino:
        destino = canal.get("categoria", "").strip()

    if not destino:
        destino = "OTROS"

    extinf = reemplazar_categoria(
        canal["extinf"],
        destino
    )

    bloques_nuevos.append(
        extinf + "\n" + url
    )

    urls_existentes.add(url)

    return True


print("=" * 70)
print("       ALIMENTADOR DE LISTA PRINCIPAL")
print("=" * 70)

if not PRINCIPAL.exists():
    print("ERROR: no existe:")
    print(PRINCIPAL)
    raise SystemExit(1)


texto_principal = PRINCIPAL.read_text(
    encoding="utf-8",
    errors="replace"
)

lineas_principal = texto_principal.splitlines()


# ------------------------------------------------------------
# CATEGORIAS EXISTENTES
# ------------------------------------------------------------
categorias = []

for linea in lineas_principal:
    if linea.startswith("#EXTINF"):
        categoria = extraer_categoria(linea)

        if categoria and categoria not in categorias:
            categorias.append(categoria)


print()
print(f"Categorías detectadas: {len(categorias)}")


# ------------------------------------------------------------
# URLS EXISTENTES


def main():
    # ------------------------------------------------------------
    urls_existentes = set()

    for linea in lineas_principal:
        linea = linea.strip()

        if url_es_valida(linea):
            urls_existentes.add(linea)


    print(f"URLs existentes: {len(urls_existentes)}")


    agregados = 0
    omitidos = 0
    errores = 0

    bloques_nuevos = []


    # ------------------------------------------------------------
    # PROCESAR FUENTES REMOTAS
    # ------------------------------------------------------------
    for i, fuente in enumerate(FUENTES, 1):

        print()
        print(f"[FUENTE {i}/{len(FUENTES)}]")
        print("-" * 60)
        print(fuente)

        try:
            respuesta = requests.get(
                fuente,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            respuesta.raise_for_status()

            canales = parsear_m3u(respuesta.text)

            if not canales:
                print("  -> Sin canales #EXTINF.")
                continue

            pais_fuente = pais_de_fuente(fuente)

            nuevos_fuente = 0

            for canal in canales:

                if agregar_canal(
                    canal,
                    pais_fuente,
                    categorias,
                    urls_existentes,
                    bloques_nuevos
                ):
                    agregados += 1
                    nuevos_fuente += 1
                else:
                    omitidos += 1

            print(
                f"  -> URLs nuevas agregadas: {nuevos_fuente}"
            )

        except Exception as e:
            errores += 1
            print(f"  -> ERROR: {e}")


    # ------------------------------------------------------------
    # PROCESAR LISTAS LOCALES DE CHILE
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

                    if agregar_canal(
                        canal,
                        "chile",
                        categorias,
                        urls_existentes,
                        bloques_nuevos
                    ):
                        agregados += 1
                        nuevos_chile += 1
                    else:
                        omitidos += 1

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
    # GUARDAR UNA SOLA VEZ
    # ------------------------------------------------------------
    if bloques_nuevos:

        if not texto_principal.endswith("\n"):
            texto_principal += "\n"

        texto_principal += (
            "\n".join(bloques_nuevos)
            + "\n"
        )

        PRINCIPAL.write_text(
            texto_principal,
            encoding="utf-8",
            newline="\n"
        )


    # ------------------------------------------------------------
    # RESUMEN
    # ------------------------------------------------------------
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
    print("REGLAS:")
    print("  - No duplica URLs.")
    print("  - Respeta las categorías existentes.")
    print("  - CL.m3u -> CHILE.")
    print("  - Listas locales de CHILE -> CHILE.")
    print("  - Países conocidos -> categoría existente.")
    print("  - No crea carpetas.")
    print("  - No escribe dos veces.")
    print("  - No crea backups automáticos.")
    print("=" * 70)


if __name__ == "__main__":
    main()

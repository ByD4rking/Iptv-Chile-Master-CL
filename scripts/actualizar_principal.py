#!/usr/bin/env python3

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
# RUTA BASE DEL REPOSITORIO
# ============================================================

BASE = Path(__file__).resolve().parent.parent


# ============================================================
# LISTA PRINCIPAL
# ============================================================

ARCHIVO = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"


# ============================================================
# FUENTES EXTERNAS
# ============================================================
#
# "categoria" es la categoría que se utilizará cuando el canal
# sea nuevo.
#
# Para Pluto TV se fuerza "Pluto TV" para que ambas fuentes
# terminen en la misma categoría.
#
# XXX se fuerza a XXX.Adultos.Porno y se coloca al FINAL.
# ============================================================

FUENTES = [
    {
        "url": "https://m3u.cl/lista/XXX.m3u",
        "categoria": "XXX.Adultos.Porno",
        "forzar_categoria": True,
        "adultos": True,
    },
    {
        "url": "https://m3u.cl/lista/religiosos.m3u",
        "categoria": "Religiosos",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/musica.m3u",
        "categoria": "Música",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/LATAM.m3u",
        "categoria": "LATAM",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/VE.m3u",
        "categoria": "Venezuela",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/DO.m3u",
        "categoria": "República Dominicana",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/PE.m3u",
        "categoria": "Perú",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/PY.m3u",
        "categoria": "Paraguay",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/MX.m3u",
        "categoria": "México",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/ES.m3u",
        "categoria": "España",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/EC.m3u",
        "categoria": "Ecuador",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/CR.m3u",
        "categoria": "Costa Rica",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/CO.m3u",
        "categoria": "Colombia",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/CL.m3u",
        "categoria": "Chile",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/BR.m3u",
        "categoria": "Brasil",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/BO.m3u",
        "categoria": "Bolivia",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/AR.m3u",
        "categoria": "Argentina",
        "forzar_categoria": False,
        "adultos": False,
    },

    # --------------------------------------------------------
    # PLUTO TV
    # --------------------------------------------------------

    {
        "url": (
            "https://raw.githubusercontent.com/"
            "JMigue85/IPTV-SV/refs/heads/main/PlutoTV.ES.m3u"
        ),
        "categoria": "Pluto TV",
        "forzar_categoria": True,
        "adultos": False,
    },
    {
        "url": (
            "https://raw.githubusercontent.com/"
            "JMigue85/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u"
        ),
        "categoria": "Pluto TV",
        "forzar_categoria": True,
        "adultos": False,
    },

    # --------------------------------------------------------
    # LISTAS AGREGADAS / COMPLEMENTARIAS
    # --------------------------------------------------------

    {
        "url": "https://m3u.cl/lista/total.m3u",
        "categoria": "Total",
        "forzar_categoria": False,
        "adultos": False,
    },
    {
        "url": "https://m3u.cl/lista/top.m3u",
        "categoria": "TOP",
        "forzar_categoria": False,
        "adultos": False,
    },
]


# ============================================================
# CONFIGURACIÓN HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    )
}


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(texto):
    """
    Normaliza nombres para comparar canales.

    Ejemplos:

        Chile
        CHILE
        chile
        Chile TV
        chile-tv

    se pueden comparar de forma más consistente.
    """

    if not texto:
        return ""

    texto = str(texto)

    # Eliminar acentos.
    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = texto.lower()

    # Sustituir separadores por espacios.
    texto = re.sub(
        r"[_./\\|:+\-]+",
        " ",
        texto,
    )

    # Eliminar caracteres especiales.
    texto = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto,
    )

    # Espacios múltiples.
    texto = re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()

    return texto


# ============================================================
# NORMALIZAR NOMBRE DE CANAL
# ============================================================

def normalizar_nombre_canal(nombre):
    """
    Normaliza nombres para detectar variantes evidentes.

    No modifica el nombre que finalmente se escribe.
    Solo se utiliza para comparar.
    """

    nombre = normalizar_texto(nombre)

    # Palabras que normalmente son separadores descriptivos.
    nombre = re.sub(
        r"\bhd\b",
        "",
        nombre,
    )

    nombre = re.sub(
        r"\bfhd\b",
        "",
        nombre,
    )

    nombre = re.sub(
        r"\buhd\b",
        "",
        nombre,
    )

    nombre = re.sub(
        r"\btv\b",
        "",
        nombre,
    )

    nombre = re.sub(
        r"\btelevision\b",
        "",
        nombre,
    )

    nombre = re.sub(
        r"\btelevisión\b",
        "",
        nombre,
    )

    nombre = re.sub(
        r"\s+",
        " ",
        nombre,
    ).strip()

    return nombre


# ============================================================
# EXTRAER NOMBRE DEL EXTINF
# ============================================================

def extraer_nombre(info):
    """
    Intenta obtener el nombre visible del canal.

    Primero busca tvg-name.
    Si no existe, utiliza el texto después de la última coma.
    """

    coincidencia = re.search(
        r'tvg-name="([^"]*)"',
        info,
        re.IGNORECASE,
    )

    if coincidencia:
        nombre = coincidencia.group(1).strip()

        if nombre:
            return nombre

    if "," in info:
        return info.rsplit(",", 1)[1].strip()

    return ""


# ============================================================
# OBTENER CATEGORÍA
# ============================================================

def obtener_categoria(info):
    coincidencia = re.search(
        r'group-title="([^"]*)"',
        info,
        re.IGNORECASE,
    )

    if coincidencia:
        categoria = coincidencia.group(1).strip()

        if categoria:
            return categoria

    return "OTROS"


# ============================================================
# CAMBIAR CATEGORÍA
# ============================================================

def cambiar_categoria(info, categoria):

    if re.search(
        r'group-title="',
        info,
        re.IGNORECASE,
    ):
        return re.sub(
            r'group-title="[^"]*"',
            f'group-title="{categoria}"',
            info,
            count=1,
            flags=re.IGNORECASE,
        )

    if "," in info:
        return info.replace(
            ",",
            f' group-title="{categoria}",',
            1,
        )

    return info


# ============================================================
# DESCARGAR M3U
# ============================================================

def descargar(url):
    print()
    print("------------------------------------------------------------")
    print("Descargando:")
    print(url)
    print("------------------------------------------------------------")

    respuesta = requests.get(
        url,
        timeout=90,
        headers=HEADERS,
    )

    respuesta.raise_for_status()

    if "#EXTINF" not in respuesta.text:
        raise Exception(
            "La fuente no parece una M3U válida."
        )

    return respuesta.text.splitlines()


# ============================================================
# EXTRAER CANALES
# ============================================================

def extraer_canales(lineas):
    """
    Devuelve:

        [
            {
                "info": "...",
                "url": "...",
                "nombre": "...",
                "categoria": "..."
            }
        ]
    """

    canales = []

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

        if url.startswith(
            (
                "http://",
                "https://",
            )
        ):

            canales.append(
                {
                    "info": info,
                    "url": url,
                    "nombre": extraer_nombre(info),
                    "categoria": obtener_categoria(info),
                }
            )

        i = j + 1

    return canales


# ============================================================
# COMPARAR CANALES
# ============================================================

def clave_canal(nombre):
    return normalizar_nombre_canal(nombre)


# ============================================================
# CONSTRUIR ÍNDICE DE LA LISTA PRINCIPAL
# ============================================================

def construir_indices(canales):
    """
    Crea índices para:

    1. URLs existentes.
    2. Nombres normalizados.
    3. Categorías existentes.
    """

    urls_existentes = set()

    canales_por_nombre = {}

    categorias = {}

    for canal in canales:

        url = canal["url"]
        nombre = canal["nombre"]
        categoria = canal["categoria"]

        urls_existentes.add(url)

        clave = clave_canal(nombre)

        if clave:
            canales_por_nombre.setdefault(
                clave,
                []
            ).append(canal)

        categoria_clave = normalizar_texto(
            categoria
        )

        if categoria_clave:
            categorias.setdefault(
                categoria_clave,
                categoria
            )

    return (
        urls_existentes,
        canales_por_nombre,
        categorias,
    )


# ============================================================
# RESOLVER CATEGORÍA
# ============================================================

def resolver_categoria(
    canal,
    fuente,
):
    """
    Si la fuente tiene categoría forzada,
    se utiliza esa.

    Si no, se intenta utilizar group-title
    de la fuente.

    Si no existe, se utiliza la categoría
    definida para la fuente.
    """

    if fuente.get("forzar_categoria"):
        return fuente["categoria"]

    categoria = canal.get(
        "categoria",
        "",
    ).strip()

    if categoria and categoria.upper() != "OTROS":
        return categoria

    return fuente["categoria"]


# ============================================================
# CREAR BLOQUE DE CANAL
# ============================================================

def crear_bloque(
    canal,
    categoria,
):
    info = cambiar_categoria(
        canal["info"],
        categoria,
    )

    return (
        info,
        canal["url"],
    )


# ============================================================
# ACTUALIZAR LISTA
# ============================================================

def actualizar_lista():
    print("=" * 70)
    print(" IPTV CHILE MASTER - ACTUALIZACIÓN DE LISTA PRINCIPAL")
    print("=" * 70)

    if not ARCHIVO.exists():

        raise FileNotFoundError(
            f"No existe la lista principal: {ARCHIVO}"
        )

    # --------------------------------------------------------
    # LEER LISTA ACTUAL
    # --------------------------------------------------------

    print()
    print("[1/5] Leyendo lista principal...")

    texto = ARCHIVO.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    lineas = texto.splitlines()

    canales_principales = extraer_canales(
        lineas
    )

    (
        urls_existentes,
        canales_por_nombre,
        categorias_existentes,
    ) = construir_indices(
        canales_principales
    )

    print(
        f"Canales actuales: "
        f"{len(canales_principales)}"
    )

    print(
        f"URLs únicas actuales: "
        f"{len(urls_existentes)}"
    )

    # --------------------------------------------------------
    # ACUMULADORES
    # --------------------------------------------------------

    nuevos_normales = []

    nuevos_adultos = []

    total_fuentes = 0
    total_candidatos = 0
    total_urls_duplicadas = 0
    total_alternativas = 0

    nombres_nuevos = set()

    # --------------------------------------------------------
    # PROCESAR FUENTES
    # --------------------------------------------------------

    print()
    print("[2/5] Procesando fuentes externas...")

    for numero, fuente in enumerate(
        FUENTES,
        start=1,
    ):

        print()
        print(
            f"[FUENTE {numero}/{len(FUENTES)}]"
        )

        try:
            lineas_externas = descargar(
                fuente["url"]
            )

            canales_externos = extraer_canales(
                lineas_externas
            )

        except Exception as error:

            print(
                f"[!] No se pudo procesar la fuente:"
            )

            print(
                f"    {error}"
            )

            continue

        total_fuentes += 1

        print(
            f"Canales encontrados: "
            f"{len(canales_externos)}"
        )

        total_candidatos += len(
            canales_externos
        )

        for canal in canales_externos:

            url = canal["url"]
            nombre = canal["nombre"]

            # ------------------------------------------------
            # URL EXACTAMENTE IGUAL
            # ------------------------------------------------

            if url in urls_existentes:

                total_urls_duplicadas += 1

                continue

            clave = clave_canal(
                nombre
            )

            categoria = resolver_categoria(
                canal,
                fuente,
            )

            # ------------------------------------------------
            # CANAL YA EXISTENTE POR NOMBRE
            # ------------------------------------------------
            #
            # La URL es diferente.
            #
            # Se agrega como alternativa.
            #
            # NO se mueve el canal existente.
            # NO se cambia el canal existente.
            # ------------------------------------------------

            if clave and clave in canales_por_nombre:

                info_nuevo = cambiar_categoria(
                    canal["info"],
                    categoria,
                )

                nuevo = {
                    "info": info_nuevo,
                    "url": url,
                    "nombre": nombre,
                    "categoria": categoria,
                }

                if fuente.get("adultos"):
                    nuevos_adultos.append(
                        nuevo
                    )
                else:
                    nuevos_normales.append(
                        nuevo
                    )

                urls_existentes.add(url)

                canales_por_nombre.setdefault(
                    clave,
                    []
                ).append(nuevo)

                total_alternativas += 1

                continue

            # ------------------------------------------------
            # CANAL REALMENTE NUEVO
            # ------------------------------------------------

            # Evitar que dos fuentes externas distintas
            # introduzcan exactamente el mismo nombre
            # en la misma ejecución.
            #
            # IMPORTANTE:
            # la URL sigue siendo el identificador absoluto.
            # ------------------------------------------------

            if clave and clave in nombres_nuevos:

                # Si el mismo canal ya fue incorporado
                # durante esta ejecución con otra URL,
                # también es una alternativa válida.
                #
                # Por tanto se agrega.
                pass

            info_nuevo = cambiar_categoria(
                canal["info"],
                categoria,
            )

            nuevo = {
                "info": info_nuevo,
                "url": url,
                "nombre": nombre,
                "categoria": categoria,
            }

            if fuente.get("adultos"):

                nuevos_adultos.append(
                    nuevo
                )

            else:

                nuevos_normales.append(
                    nuevo
                )

            urls_existentes.add(url)

            if clave:
                nombres_nuevos.add(
                    clave
                )

                canales_por_nombre.setdefault(
                    clave,
                    []
                ).append(nuevo)

    # --------------------------------------------------------
    # ELIMINAR DUPLICADOS INTERNOS
    # --------------------------------------------------------
    #
    # Se conserva únicamente una entrada por URL.
    # --------------------------------------------------------

    def deduplicar_por_url(lista):

        resultado = []
        vistos = set()

        for canal in lista:

            url = canal["url"]

            if url in vistos:
                continue

            vistos.add(url)
            resultado.append(canal)

        return resultado

    nuevos_normales = deduplicar_por_url(
        nuevos_normales
    )

    nuevos_adultos = deduplicar_por_url(
        nuevos_adultos
    )

    # --------------------------------------------------------
    # REVISAR CATEGORÍAS NUEVAS
    # --------------------------------------------------------

    print()
    print("[3/5] Revisando categorías...")

    categorias_nuevas = []

    categorias_vistas = set(
        categorias_existentes.keys()
    )

    for canal in (
        nuevos_normales
        + nuevos_adultos
    ):

        categoria = canal["categoria"]

        clave_categoria = normalizar_texto(
            categoria
        )

        if (
            clave_categoria
            and clave_categoria
            not in categorias_vistas
        ):

            categorias_vistas.add(
                clave_categoria
            )

            categorias_nuevas.append(
                categoria
            )

    if categorias_nuevas:

        print(
            "Categorías nuevas que se crearán:"
        )

        for categoria in categorias_nuevas:

            print(
                f"    + {categoria}"
            )

    else:

        print(
            "No hay categorías nuevas."
        )

    # --------------------------------------------------------
    # CONSTRUIR NUEVOS BLOQUES
    # --------------------------------------------------------

    print()
    print("[4/5] Preparando canales nuevos...")

    # --------------------------------------------------------
    # CANALES NORMALES
    # --------------------------------------------------------

    bloques_normales = []

    for canal in nuevos_normales:

        bloques_normales.append(
            canal["info"]
        )

        bloques_normales.append(
            canal["url"]
        )

    # --------------------------------------------------------
    # XXX
    # --------------------------------------------------------
    #
    # Siempre después de TODO lo demás.
    # --------------------------------------------------------

    bloques_adultos = []

    for canal in nuevos_adultos:

        bloques_adultos.append(
            canal["info"]
        )

        bloques_adultos.append(
            canal["url"]
        )

    # --------------------------------------------------------
    # ESCRIBIR
    # --------------------------------------------------------

    print()
    print("[5/5] Guardando lista actualizada...")

    cambios = []

    if bloques_normales:

        cambios.extend(
            bloques_normales
        )

    if bloques_adultos:

        cambios.extend(
            bloques_adultos
        )

    if cambios:

        contenido_actual = ARCHIVO.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        contenido_actual = contenido_actual.rstrip()

        with ARCHIVO.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as archivo:

            archivo.write(
                contenido_actual
            )

            archivo.write(
                "\n"
            )

            for linea in cambios:

                archivo.write(
                    linea
                )

                archivo.write(
                    "\n"
                )

    # --------------------------------------------------------
    # RESULTADOS
    # --------------------------------------------------------

    total_nuevos = (
        len(nuevos_normales)
        + len(nuevos_adultos)
    )

    print()
    print("=" * 70)
    print(" ACTUALIZACIÓN TERMINADA")
    print("=" * 70)

    print(
        f"Fuentes procesadas:       "
        f"{total_fuentes}"
    )

    print(
        f"Candidatos encontrados:   "
        f"{total_candidatos}"
    )

    print(
        f"URLs ya existentes:       "
        f"{total_urls_duplicadas}"
    )

    print(
        f"Alternativas agregadas:   "
        f"{total_alternativas}"
    )

    print(
        f"Canales nuevos normales:  "
        f"{len(nuevos_normales)}"
    )

    print(
        f"Canales XXX agregados:    "
        f"{len(nuevos_adultos)}"
    )

    print(
        f"Total agregado:           "
        f"{total_nuevos}"
    )

    print()

    if not cambios:

        print(
            "No había canales nuevos para agregar."
        )

    else:

        print(
            "Se agregaron los canales faltantes."
        )

    print()
    print(
        "Archivo actualizado:"
    )

    print(
        ARCHIVO
    )

    print()
    print(
        "Los canales XXX.Adultos.Porno "
        "se colocaron al final."
    )

    print()
    print(
        "Proceso terminado correctamente."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    try:

        actualizar_lista()

    except requests.RequestException as error:

        print()
        print(
            "[ERROR] Falló una conexión HTTP:"
        )
        print(
            error
        )

        raise

    except Exception as error:

        print()
        print(
            "[ERROR]"
        )
        print(
            error
        )

        raise


if __name__ == "__main__":
    main()
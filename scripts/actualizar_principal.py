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
# FUENTE EXTERNA
# ============================================================

FUENTE = (
    "https://raw.githubusercontent.com/"
    "JMigue85/IPTV-SV/refs/heads/main/IPTVSV.m3u"
)


# ============================================================
# DESCARGAR M3U
# ============================================================

def descargar(url):
    print("Descargando fuente externa...")
    print(url)

    respuesta = requests.get(
        url,
        timeout=90,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
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
    canales = []

    i = 0

    while i < len(lineas):

        if not lineas[i].strip().startswith("#EXTINF"):
            i += 1
            continue

        info = lineas[i].strip()

        j = i + 1

        while j < len(lineas) and not lineas[j].strip():
            j += 1

        if j >= len(lineas):
            break

        url = lineas[j].strip()

        if url.startswith(("http://", "https://")):
            canales.append((info, url))

        i = j + 1

    return canales


# ============================================================
# OBTENER CATEGORÍA
# ============================================================

def obtener_categoria(info):
    coincidencia = re.search(
        r'group-title="([^"]*)"',
        info,
        re.IGNORECASE
    )

    if coincidencia:
        return coincidencia.group(1)

    return "OTROS"


# ============================================================
# CAMBIAR CATEGORÍA
# ============================================================

def cambiar_categoria(info, categoria):

    if re.search(
        r'group-title="',
        info,
        re.IGNORECASE
    ):
        return re.sub(
            r'group-title="[^"]*"',
            f'group-title="{categoria}"',
            info,
            count=1,
            flags=re.IGNORECASE
        )

    return info.replace(
        ",",
        f' group-title="{categoria}",',
        1
    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    print("=" * 70)
    print(" IPTV CHILE MASTER - ACTUALIZAR LISTA PRINCIPAL")
    print("=" * 70)

    # --------------------------------------------------------
    # COMPROBAR LISTA PRINCIPAL
    # --------------------------------------------------------

    if not ARCHIVO.exists():

        print()
        print("ERROR: No existe:")
        print(ARCHIVO)
        print()

        raise FileNotFoundError(
            f"No existe la lista principal: {ARCHIVO}"
        )

    # --------------------------------------------------------
    # LEER LISTA PRINCIPAL
    # --------------------------------------------------------

    print("\n[1/4] Leyendo lista principal...")

    texto = ARCHIVO.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    lineas_principal = texto.splitlines()

    canales_principal = extraer_canales(
        lineas_principal
    )

    urls_existentes = {
        url
        for info, url in canales_principal
    }

    print(
        f"Canales actuales: "
        f"{len(canales_principal)}"
    )

    # --------------------------------------------------------
    # DESCARGAR IPTV-SV
    # --------------------------------------------------------

    print("\n[2/4] Descargando IPTVSV...")

    lineas_externa = descargar(FUENTE)

    canales_externos = extraer_canales(
        lineas_externa
    )

    print(
        f"Canales encontrados en IPTVSV: "
        f"{len(canales_externos)}"
    )

    # --------------------------------------------------------
    # BUSCAR CANALES FALTANTES
    # --------------------------------------------------------

    print("\n[3/4] Buscando canales que faltan...")

    nuevos = []

    for info, url in canales_externos:

        # Si la URL ya existe,
        # no se modifica.
        if url in urls_existentes:
            continue

        categoria = obtener_categoria(info)

        info_nuevo = cambiar_categoria(
            info,
            categoria
        )

        nuevos.append(
            (info_nuevo, url)
        )

        urls_existentes.add(url)

    print(
        f"Canales nuevos encontrados: "
        f"{len(nuevos)}"
    )

    # --------------------------------------------------------
    # AGREGAR CANALES NUEVOS
    # --------------------------------------------------------

    print(
        "\n[4/4] Agregando únicamente "
        "los canales faltantes..."
    )

    if nuevos:

        with ARCHIVO.open(
            "a",
            encoding="utf-8"
        ) as archivo:

            archivo.write("\n")

            for info, url in nuevos:

                archivo.write(
                    info + "\n"
                )

                archivo.write(
                    url + "\n"
                )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    total = (
        len(canales_principal)
        + len(nuevos)
    )

    print()
    print("=" * 70)
    print(" ACTUALIZACIÓN TERMINADA")
    print("=" * 70)

    print(
        f"Canales anteriores: "
        f"{len(canales_principal)}"
    )

    print(
        f"Canales agregados:  "
        f"{len(nuevos)}"
    )

    print(
        f"Total aproximado:   "
        f"{total}"
    )

    print()
    print("Archivo actualizado:")
    print(ARCHIVO)

    print()
    print("URL RAW NO CAMBIA:")
    print(
        "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
    )

    print()
    print("Proceso terminado correctamente.")


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
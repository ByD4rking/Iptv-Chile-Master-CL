#!/usr/bin/env python3

"""
Genera REPORTE.md a partir de uno o varios archivos M3U.

Si no se indican archivos en la línea de comandos, busca automáticamente
todos los archivos .m3u y .m3u8 ubicados en la raíz del repositorio.

Además registra cada comprobación en:
    scripts/aprendizaje.json

Uso automático:
    py scripts/generar_reporte.py

Uso manual:
    py scripts/generar_reporte.py lista1.m3u lista2.m3u
"""

import argparse
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from verificar_m3u import parsear_m3u, verificar_canal
from aprendizaje import registrar_lote


# ============================================================
# RUTAS
# ============================================================

BASE = Path(__file__).resolve().parent.parent


# ============================================================
# POSIBLES FALSOS POSITIVOS
# ============================================================

CODIGOS_POSIBLE_FALSO_POSITIVO = (
    "HTTP 403",
    "HTTP 451",
    "HTTP 401",
)

ETIQUETAS_GEO_EN_NOMBRE = (
    "geo-blocked",
    "geo blocked",
    "geobloqueado",
    "geo-bloqueado",
    "geo bloqueado",
)


def es_posible_falso_positivo(error, nombre=""):
    if nombre:
        nombre_lower = nombre.lower()

        if any(
            etiqueta in nombre_lower
            for etiqueta in ETIQUETAS_GEO_EN_NOMBRE
        ):
            return True

    if not error:
        return False

    return any(
        codigo in error
        for codigo in CODIGOS_POSIBLE_FALSO_POSITIVO
    )


# ============================================================
# DETECCIÓN AUTOMÁTICA DE LISTAS
# ============================================================

def detectar_listas():
    """
    Busca automáticamente archivos .m3u y .m3u8
    en la raíz del repositorio.

    Ignora:
        - carpetas
        - archivos ocultos
        - archivos dentro de .git
    """

    extensiones = {
        ".m3u",
        ".m3u8",
    }

    listas = []

    for archivo in BASE.iterdir():

        if not archivo.is_file():
            continue

        if archivo.name.startswith("."):
            continue

        if archivo.suffix.lower() not in extensiones:
            continue

        listas.append(archivo)

    listas.sort(
        key=lambda archivo: archivo.name.lower()
    )

    return listas


# ============================================================
# VERIFICACIÓN DE UN ARCHIVO
# ============================================================

def verificar_archivo(
    ruta,
    hilos,
    timeout,
    max_por_servidor,
    reintentos,
    espera_reintento,
):
    print(f"\n[+] Procesando {ruta}...")

    canales = parsear_m3u(ruta)

    total = len(canales)

    print(
        f"    Canales encontrados: {total}"
    )

    if total == 0:
        print(
            "    [!] La lista no contiene canales válidos."
        )
        return []

    resultados = []

    with ThreadPoolExecutor(
        max_workers=hilos
    ) as ex:

        futuros = {
            ex.submit(
                verificar_canal,
                canal,
                timeout,
                max_por_servidor,
                reintentos,
                espera_reintento,
            ): canal
            for canal in canales
        }

        completados = 0

        for futuro in as_completed(futuros):

            resultado = futuro.result()

            resultados.append(resultado)

            completados += 1

            if (
                completados % 50 == 0
                or completados == total
            ):
                print(
                    f"    [{completados}/{total}] "
                    "verificados..."
                )

    return resultados


# ============================================================
# GENERAR REPORTE
# ============================================================

def escribir_reporte(
    resultados_por_archivo,
    ruta_salida,
):
    fecha = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    total_general = sum(
        len(resultados)
        for resultados
        in resultados_por_archivo.values()
    )

    ok_general = sum(
        sum(
            1
            for canal in resultados
            if canal["estado"].startswith("OK")
        )
        for resultados
        in resultados_por_archivo.values()
    )

    caidos_general = (
        total_general - ok_general
    )

    lineas = []

    lineas.append(
        "# 📡 Reporte de estado de canales\n"
    )

    lineas.append(
        f"**Última verificación:** {fecha}\n"
    )

    lineas.append(
        "> ⚠️ **Nota importante:** este reporte se genera "
        "automáticamente. Un canal puede aparecer como caído "
        "sin estarlo realmente para el usuario final por "
        "geo-bloqueo, restricciones de User-Agent, "
        "restricciones de Referer u otras condiciones de red.\n"
    )

    # --------------------------------------------------------
    # RESUMEN GENERAL
    # --------------------------------------------------------

    lineas.append(
        "## Resumen general\n"
    )

    lineas.append(
        "| Total canales | ✅ OK | ❌ Caídos/Error |"
    )

    lineas.append(
        "|---|---|---|"
    )

    lineas.append(
        f"| {total_general} | "
        f"{ok_general} | "
        f"{caidos_general} |\n"
    )

    # --------------------------------------------------------
    # CADA LISTA
    # --------------------------------------------------------

    for archivo, resultados in (
        resultados_por_archivo.items()
    ):

        total = len(resultados)

        ok = [
            canal
            for canal in resultados
            if canal["estado"].startswith("OK")
        ]

        caidos = [
            canal
            for canal in resultados
            if canal["estado"] == "ERROR"
        ]

        lineas.append(
            f"## {archivo}\n"
        )

        lineas.append(
            f"**Total:** {total} "
            f"&nbsp;|&nbsp; "
            f"**OK:** {len(ok)} "
            f"&nbsp;|&nbsp; "
            f"**Caídos:** {len(caidos)}\n"
        )

        if not caidos:

            lineas.append(
                "✅ Todos los canales respondieron "
                "correctamente.\n"
            )

            continue

        # ----------------------------------------------------
        # AGRUPAR POR CATEGORÍA
        # ----------------------------------------------------

        por_categoria = {}

        for canal in caidos:

            categoria = canal.get(
                "categoria",
                "Sin categoría"
            )

            por_categoria.setdefault(
                categoria,
                []
            ).append(canal)

        # ----------------------------------------------------
        # ESCRIBIR CATEGORÍAS
        # ----------------------------------------------------

        for categoria in sorted(
            por_categoria.keys()
        ):

            lista = por_categoria[categoria]

            lineas.append(
                "<details>"
            )

            lineas.append(
                f"<summary><strong>"
                f"{categoria}"
                f"</strong> "
                f"({len(lista)} caídos)"
                f"</summary>\n"
            )

            lineas.append(
                "| Canal | Motivo |"
            )

            lineas.append(
                "|---|---|"
            )

            for canal in lista:

                if es_posible_falso_positivo(
                    canal.get("error"),
                    canal.get("nombre", ""),
                ):
                    marca = (
                        "🟡 *(posible falso positivo)*"
                    )
                else:
                    marca = "🔴"

                nombre = canal.get(
                    "nombre",
                    "Sin nombre"
                )

                error = canal.get(
                    "error",
                    "Error desconocido"
                )

                # Evitar romper la tabla Markdown
                nombre = str(nombre).replace(
                    "|",
                    "\\|"
                )

                error = str(error).replace(
                    "|",
                    "\\|"
                )

                lineas.append(
                    f"| {nombre} | "
                    f"{marca} {error} |"
                )

            lineas.append(
                "\n</details>\n"
            )

    # --------------------------------------------------------
    # GUARDAR REPORTE
    # --------------------------------------------------------

    ruta_salida = Path(ruta_salida)

    ruta_salida.write_text(
        "\n".join(lineas),
        encoding="utf-8",
    )

    print(
        f"\n[+] Reporte guardado en: "
        f"{ruta_salida}"
    )

    print(
        f"[+] Resumen -> "
        f"OK: {ok_general} | "
        f"Caídos: {caidos_general} "
        f"de {total_general}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Genera REPORTE.md, verifica listas M3U "
            "y registra resultados en aprendizaje.json"
        )
    )

    parser.add_argument(
        "archivos",
        nargs="*",
        help=(
            "Archivos M3U a verificar. "
            "Si no se indican, se detectan automáticamente."
        ),
    )

    parser.add_argument(
        "--salida",
        default="REPORTE.md",
        help="Archivo Markdown de salida.",
    )

    parser.add_argument(
        "--hilos",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=6,
    )

    parser.add_argument(
        "--max-por-servidor",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--reintentos",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--espera-reintento",
        type=float,
        default=1.0,
    )

    args = parser.parse_args()

    # ========================================================
    # DETECTAR LISTAS AUTOMÁTICAMENTE
    # ========================================================

    if not args.archivos:

        listas = detectar_listas()

        if not listas:

            print(
                "[!] No se encontraron archivos "
                ".m3u o .m3u8 en:"
            )

            print(
                f"    {BASE}"
            )

            sys.exit(1)

        args.archivos = [
            str(lista)
            for lista in listas
        ]

        print(
            "\n[+] Listas detectadas automáticamente:"
        )

        for lista in listas:

            print(
                f"    - {lista.name}"
            )

    else:

        # Convertir rutas manuales a texto
        args.archivos = [
            str(Path(archivo))
            for archivo in args.archivos
        ]

    # ========================================================
    # CONFIGURAR SESSION HTTP
    # ========================================================

    adapter = requests.adapters.HTTPAdapter(
        pool_connections=args.hilos,
        pool_maxsize=args.hilos,
    )

    import verificar_m3u

    verificar_m3u._SESSION.mount(
        "http://",
        adapter,
    )

    verificar_m3u._SESSION.mount(
        "https://",
        adapter,
    )

    # ========================================================
    # VERIFICAR LISTAS
    # ========================================================

    resultados_por_archivo = {}

    for archivo in args.archivos:

        ruta = Path(archivo)

        if not ruta.exists():

            print(
                f"\n[!] Archivo no encontrado: "
                f"{ruta}"
            )

            continue

        if not ruta.is_file():

            print(
                f"\n[!] No es un archivo: "
                f"{ruta}"
            )

            continue

        resultados_por_archivo[
            str(ruta)
        ] = verificar_archivo(
            str(ruta),
            args.hilos,
            args.timeout,
            args.max_por_servidor,
            args.reintentos,
            args.espera_reintento,
        )

    # ========================================================
    # COMPROBAR RESULTADOS
    # ========================================================

    if not resultados_por_archivo:

        print(
            "\n[!] No se pudo procesar ninguna lista."
        )

        sys.exit(1)

    # ========================================================
    # PREPARAR APRENDIZAJE
    # ========================================================

    resultados_aprendizaje = []

    for resultados in (
        resultados_por_archivo.values()
    ):

        for canal in resultados:

            resultados_aprendizaje.append(
                {
                    "url": canal["url"],
                    "nombre": canal["nombre"],
                    "ok": canal["estado"].startswith(
                        "OK"
                    ),
                }
            )

    # ========================================================
    # GUARDAR APRENDIZAJE
    # ========================================================

    if resultados_aprendizaje:

        registrar_lote(
            resultados_aprendizaje
        )

        print(
            f"[+] Aprendizaje actualizado: "
            f"{len(resultados_aprendizaje)} "
            f"comprobaciones"
        )

    # ========================================================
    # GENERAR REPORTE
    # ========================================================

    escribir_reporte(
        resultados_por_archivo,
        args.salida,
    )


if __name__ == "__main__":
    main()
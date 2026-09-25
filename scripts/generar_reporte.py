#!/usr/bin/env python3

"""
Genera REPORTE.md a partir de uno o varios archivos M3U.

Además registra cada comprobación en:
    scripts/aprendizaje.json

Uso:
    py scripts\generar_reporte.py IPTV-CHILE-MAESTRA_CORREGIDO.m3u
"""

import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from verificar_m3u import parsear_m3u, verificar_canal
from aprendizaje import registrar_lote


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

    print(f"    Canales encontrados: {total}")

    if total == 0:
        return []

    resultados = []

    with ThreadPoolExecutor(max_workers=hilos) as ex:

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

            if completados % 50 == 0 or completados == total:
                print(
                    f"    [{completados}/{total}] verificados..."
                )

    return resultados


def escribir_reporte(
    resultados_por_archivo,
    ruta_salida,
):
    fecha = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    total_general = sum(
        len(resultados)
        for resultados in resultados_por_archivo.values()
    )

    ok_general = sum(
        sum(
            1
            for canal in resultados
            if canal["estado"].startswith("OK")
        )
        for resultados in resultados_por_archivo.values()
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
        "automáticamente desde servidores de GitHub Actions "
        "(ubicados en EE.UU./Europa). Un canal puede aparecer "
        "como caído sin estarlo realmente para el usuario final "
        "por geo-bloqueo, restricciones de User-Agent, "
        "restricciones de Referer u otras condiciones de red.\n"
    )

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
        f"| {total_general} | {ok_general} | "
        f"{caidos_general} |\n"
    )

    for archivo, resultados in resultados_por_archivo.items():

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
            f"**Total:** {total} &nbsp;|&nbsp; "
            f"**OK:** {len(ok)} &nbsp;|&nbsp; "
            f"**Caídos:** {len(caidos)}\n"
        )

        if not caidos:

            lineas.append(
                "✅ Todos los canales respondieron "
                "correctamente.\n"
            )

            continue

        por_categoria = {}

        for canal in caidos:

            categoria = canal["categoria"]

            por_categoria.setdefault(
                categoria,
                []
            ).append(canal)

        for categoria in sorted(
            por_categoria.keys()
        ):

            lista = por_categoria[categoria]

            lineas.append(
                "<details>"
            )

            lineas.append(
                f"<summary><strong>{categoria}</strong> "
                f"({len(lista)} caídos)</summary>\n"
            )

            lineas.append(
                "| Canal | Motivo |"
            )

            lineas.append(
                "|---|---|"
            )

            for canal in lista:

                if es_posible_falso_positivo(
                    canal["error"],
                    canal["nombre"],
                ):
                    marca = (
                        "🟡 *(posible falso positivo)*"
                    )
                else:
                    marca = "🔴"

                lineas.append(
                    f"| {canal['nombre']} | "
                    f"{marca} {canal['error']} |"
                )

            lineas.append(
                "\n</details>\n"
            )

    with open(
        ruta_salida,
        "w",
        encoding="utf-8",
    ) as archivo:

        archivo.write(
            "\n".join(lineas)
        )

    print(
        f"\n[+] Reporte guardado en: "
        f"{ruta_salida}"
    )

    print(
        f"[+] Resumen -> OK: {ok_general} | "
        f"Caídos: {caidos_general} "
        f"de {total_general}"
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Genera REPORTE.md y registra "
            "resultados en aprendizaje.json"
        )
    )

    parser.add_argument(
        "archivos",
        nargs="+",
        help="Archivos M3U a verificar",
    )

    parser.add_argument(
        "--salida",
        default="REPORTE.md",
        help="Archivo Markdown de salida",
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

    resultados_por_archivo = {}

    # -------------------------------------------------
    # VERIFICAR CADA ARCHIVO
    # -------------------------------------------------

    for archivo in args.archivos:

        resultados_por_archivo[archivo] = (
            verificar_archivo(
                archivo,
                args.hilos,
                args.timeout,
                args.max_por_servidor,
                args.reintentos,
                args.espera_reintento,
            )
        )

    # -------------------------------------------------
    # PREPARAR DATOS PARA EL APRENDIZAJE
    # -------------------------------------------------

    resultados_aprendizaje = []

    for resultados in resultados_por_archivo.values():

        for canal in resultados:

            resultados_aprendizaje.append(
                {
                    "url": canal["url"],
                    "nombre": canal["nombre"],
                    "ok": canal["estado"].startswith("OK"),
                }
            )

    # -------------------------------------------------
    # GUARDAR APRENDIZAJE
    # -------------------------------------------------

    if resultados_aprendizaje:

        registrar_lote(
            resultados_aprendizaje
        )

        print(
            f"[+] Aprendizaje actualizado: "
            f"{len(resultados_aprendizaje)} "
            f"comprobaciones"
        )

    # -------------------------------------------------
    # GENERAR REPORTE
    # -------------------------------------------------

    escribir_reporte(
        resultados_por_archivo,
        args.salida,
    )


if __name__ == "__main__":
    main()
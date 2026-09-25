import re
import requests
from pathlib import Path

BASE = Path(__file__).parent

# ============================================================
# LISTA PRINCIPAL — NO CAMBIAR
# ============================================================

ARCHIVO = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"

# ============================================================
# LISTA EXTERNA
# ============================================================

FUENTE = "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/IPTVSV.m3u"


def descargar(url):
    print("Descargando fuente externa...")
    print(url)

    r = requests.get(
        url,
        timeout=90,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    r.raise_for_status()

    if "#EXTINF" not in r.text:
        raise Exception("La fuente no parece una M3U válida.")

    return r.text.splitlines()


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


def obtener_categoria(info):
    m = re.search(
        r'group-title="([^"]*)"',
        info,
        re.IGNORECASE
    )

    if m:
        return m.group(1)

    return "OTROS"


def cambiar_categoria(info, categoria):
    if re.search(r'group-title="', info, re.IGNORECASE):
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


def main():

    print("=" * 70)
    print(" IPTV CHILE MASTER - ACTUALIZAR LISTA PRINCIPAL")
    print("=" * 70)

    if not ARCHIVO.exists():
        print()
        print("ERROR: No existe:")
        print(ARCHIVO)
        input("\nPulsa Enter para cerrar...")
        return

    # --------------------------------------------------------
    # LEER LISTA PRINCIPAL
    # --------------------------------------------------------

    print("\n[1/4] Leyendo lista principal...")

    texto = ARCHIVO.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    lineas_principal = texto.splitlines()

    canales_principal = extraer_canales(lineas_principal)

    urls_existentes = {
        url for info, url in canales_principal
    }

    print(f"Canales actuales: {len(canales_principal)}")

    # --------------------------------------------------------
    # DESCARGAR IPTVSV
    # --------------------------------------------------------

    print("\n[2/4] Descargando IPTVSV...")

    lineas_externa = descargar(FUENTE)

    canales_externos = extraer_canales(lineas_externa)

    print(f"Canales encontrados en IPTVSV: {len(canales_externos)}")

    # --------------------------------------------------------
    # SOLO CANALES FALTANTES
    # --------------------------------------------------------

    print("\n[3/4] Buscando canales que faltan...")

    nuevos = []

    for info, url in canales_externos:

        # Si la URL ya existe, NO SE TOCA
        if url in urls_existentes:
            continue

        categoria = obtener_categoria(info)

        # Conservamos la categoría que trae la fuente
        info_nuevo = cambiar_categoria(
            info,
            categoria
        )

        nuevos.append(
            (info_nuevo, url)
        )

        urls_existentes.add(url)

    print(f"Canales nuevos encontrados: {len(nuevos)}")

    # --------------------------------------------------------
    # AGREGAR SIN MODIFICAR LOS EXISTENTES
    # --------------------------------------------------------

    print("\n[4/4] Agregando únicamente los canales faltantes...")

    if nuevos:

        with ARCHIVO.open(
            "a",
            encoding="utf-8"
        ) as f:

            f.write("\n")

            for info, url in nuevos:
                f.write(info + "\n")
                f.write(url + "\n")

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(" ACTUALIZACIÓN TERMINADA")
    print("=" * 70)

    print(f"Canales anteriores: {len(canales_principal)}")
    print(f"Canales agregados:  {len(nuevos)}")
    print(f"Total aproximado:   {len(canales_principal) + len(nuevos)}")

    print()
    print("Archivo actualizado:")
    print(ARCHIVO)

    print()
    print("URL RAW NO CAMBIA:")
    print("IPTV-CHILE-MAESTRA_CORREGIDO.m3u")

    input("\nPulsa Enter para cerrar...")


if __name__ == "__main__":
    main()
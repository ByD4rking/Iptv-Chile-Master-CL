from pathlib import Path
import re

ARCHIVO = Path("IPTV-CHILE-MAESTRA_CORREGIDO.m3u")


def main():
    if not ARCHIVO.exists():
        raise FileNotFoundError(f"No existe: {ARCHIVO}")

    texto = ARCHIVO.read_text(
        encoding="utf-8",
        errors="replace"
    )

    # La categoría oficial de Chile en la principal es CHILE TV.
    # Este paso NO crea/recrea ninguna categoría eliminada y solo
    # normaliza variantes antiguas de Chile hacia CHILE TV.
    texto = re.sub(
        r'group-title="CHILE\s+TV"',
        'group-title="CHILE TV"',
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r'group-title="CHILE"',
        'group-title="CHILE TV"',
        texto,
        flags=re.IGNORECASE
    )

    ARCHIVO.write_text(
        texto,
        encoding="utf-8",
        newline="\n"
    )

    cantidad = len(
        re.findall(
            r'group-title="CHILE"',
            texto,
            flags=re.IGNORECASE
        )
    )

    print("=" * 70)
    print("CATEGORÍA CHILE CORREGIDA")
    print("=" * 70)
    print(f"Entradas CHILE TV: {cantidad}")
    print("=" * 70)


if __name__ == "__main__":
    main()

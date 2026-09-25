from pathlib import Path
import re

ARCHIVO = Path("IPTV-CHILE-MAESTRA_CORREGIDO.m3u")

texto = ARCHIVO.read_text(encoding="utf-8", errors="replace")

# Unificar todas las variantes de la categoría Chile.
texto = re.sub(
    r'group-title="CHILE TV"',
    'group-title="CHILE"',
    texto,
    flags=re.IGNORECASE
)

texto = re.sub(
    r'group-title="CHILE"',
    'group-title="CHILE"',
    texto,
    flags=re.IGNORECASE
)

ARCHIVO.write_text(texto, encoding="utf-8", newline="\n")

print("=" * 70)
print("CATEGORÍA CHILE CORREGIDA")
print("=" * 70)
print("CHILE TV -> CHILE")
print("CHILE    -> CHILE")
print()
print(f"Archivo: {ARCHIVO}")
print("=" * 70)

from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent.parent
PRINCIPAL = ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
SCRIPT = ROOT / "scripts" / "alimentar_principal.py"

# ------------------------------------------------------------
# BACKUPS
# ------------------------------------------------------------

backup = PRINCIPAL.with_name(
    PRINCIPAL.name + ".backup_chile"
)

shutil.copy2(PRINCIPAL, backup)

print("=" * 70)
print("       CORRECCIÓN CHILE")
print("=" * 70)
print()
print(f"Backup creado:")
print(backup)
print()

# ------------------------------------------------------------
# CAMBIAR CHILE TV -> CHILE EN LA LISTA PRINCIPAL
# ------------------------------------------------------------

texto = PRINCIPAL.read_text(
    encoding="utf-8",
    errors="replace"
)

antes = texto

texto = re.sub(
    r'(group-title=")CHILE TV(")',
    r'\1CHILE\2',
    texto,
    flags=re.IGNORECASE
)

PRINCIPAL.write_text(
    texto,
    encoding="utf-8",
    newline="\n"
)

cambios_lista = 0 if texto == antes else 1

print("Lista principal:")
print("  -> CHILE TV cambiado a CHILE.")
print()

# ------------------------------------------------------------
# CORREGIR EL ALIMENTADOR
# ------------------------------------------------------------

if SCRIPT.exists():

    script_texto = SCRIPT.read_text(
        encoding="utf-8",
        errors="replace"
    )

    # Todas las referencias destinadas a CHILE TV
    # pasan a CHILE.
    script_texto = script_texto.replace(
        "CHILE TV",
        "CHILE"
    )

    SCRIPT.write_text(
        script_texto,
        encoding="utf-8",
        newline="\n"
    )

    print("Script alimentador:")
    print("  -> CHILE TV cambiado a CHILE.")
else:
    print("ADVERTENCIA: no existe:")
    print(SCRIPT)

print()
print("=" * 70)
print("CORRECCIÓN TERMINADA")
print("=" * 70)

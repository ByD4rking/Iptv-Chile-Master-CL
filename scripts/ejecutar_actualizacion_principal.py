#!/usr/bin/env python3
"""Ejecuta una actualización integral de la playlist principal."""
from pathlib import Path
import subprocess
import sys

import alimentar_principal as alimentador
from sincronizar_complementos import synchronize_once

ROOT = Path(__file__).resolve().parents[1]
PRINCIPAL = ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"


def main():
    original_lines = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()

    print("\n[ORQUESTADOR] Alimentador histórico, sin reordenar la maestra.")
    alimentador.main(restaurar_faltantes=True, preservar_orden=True)

    print("\n[ORQUESTADOR] Unificando categorías CHILE.")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "unificar_chile.py")],
        cwd=ROOT,
        check=True,
    )

    print("\n[ORQUESTADOR] Sincronizando fuentes complementarias.")
    result = synchronize_once()

    print("\n[ORQUESTADOR] Restaurando el orden original por categoría.")
    current_lines = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()
    ordered_lines, order_stats = alimentador.restaurar_orden_original_por_categoria(
        current_lines,
        original_lines,
    )
    # Elimina espacios finales de líneas M3U sin alterar nombres, metadatos ni URLs.
    ordered_lines = [line.rstrip() for line in ordered_lines]
    temporary = PRINCIPAL.with_name(PRINCIPAL.name + ".orden.tmp")
    temporary.write_text("\n".join(ordered_lines) + "\n", encoding="utf-8")
    temporary.replace(PRINCIPAL)

    print("[ORQUESTADOR] Orden protegido:", order_stats)
    print("[ORQUESTADOR] Resultado de sincronización:", result)
    return result


if __name__ == "__main__":
    main()

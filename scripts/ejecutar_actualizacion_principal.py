#!/usr/bin/env python3
"""Ejecuta una actualización integral de la playlist principal."""
from pathlib import Path
import re
import subprocess
import sys

import requests

import alimentar_principal as alimentador
from sincronizar_complementos import (
    _group_and_label_alternatives,
    _prioritize_infantiles,
    get_last_url_priority,
    synchronize_once,
)

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

    print("\n[ORQUESTADOR] Aplicando reglas finales de Anime, Infantil y alternativas.")
    ids_pluto_es_anime = alimentador.cargar_ids_pluto_es_anime(requests.Session())
    ordered_lines = alimentador.aplicar_ajustes_referencia(ordered_lines, ids_pluto_es_anime)

    # Recuperar alternativas históricas explícitas que el sincronizador haya omitido.
    # Se conserva el bloque original solo si su URL exacta desapareció; se excluye Pluto ES.
    def blocks_by_url(lines):
        found = {}
        i = 0
        while i < len(lines):
            if not lines[i].startswith("#EXTINF"):
                i += 1
                continue
            j = i + 1
            while j < len(lines) and lines[j].startswith("#") and not lines[j].startswith("#EXTINF"):
                j += 1
            if j < len(lines) and lines[j].startswith(("http://", "https://")):
                found[lines[j].strip()] = lines[i:j + 1]
                i = j + 1
            else:
                i = j
        return found

    present_urls = set(blocks_by_url(ordered_lines))
    for url, block in blocks_by_url(original_lines).items():
        is_option = bool(re.search(r"\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]", block[0], re.I))
        if not is_option or url in present_urls:
            continue
        display = block[0].split(",", 1)[-1].lower()
        if "pluto es" in display or "country=es" in url.lower() or "marketingregion=es" in url.lower():
            continue
        category_match = re.search(r'group-title="([^"]*)"', block[0], re.I)
        category = category_match.group(1) if category_match else ""
        indexes = [
            i for i, line in enumerate(ordered_lines)
            if line.startswith("#EXTINF") and
            (re.search(r'group-title="([^"]*)"', line, re.I) or [None, ""])[1].strip().lower() == category.lower()
        ]
        if indexes:
            last = indexes[-1]
            end = last + 1
            while end < len(ordered_lines) and not ordered_lines[end].startswith("#EXTINF"):
                end += 1
            ordered_lines[end:end] = block
            present_urls.add(url)

    # Agrupar alternativas y ordenar los bloques de MAGNA en el lugar solicitado.
    url_priority = get_last_url_priority()
    ordered_lines = _group_and_label_alternatives(ordered_lines, url_priority)
    ordered_lines = _prioritize_infantiles(ordered_lines)
    ordered_lines, _ = alimentador.ordenar_bloques_magma_y_originales(ordered_lines, requests.Session())

    temporary = PRINCIPAL.with_name(PRINCIPAL.name + ".orden.tmp")
    temporary.write_text("\n".join(ordered_lines) + "\n", encoding="utf-8")
    temporary.replace(PRINCIPAL)

    print("[ORQUESTADOR] Orden protegido:", order_stats)
    print("[ORQUESTADOR] Resultado de sincronización:", result)
    return result


if __name__ == "__main__":
    main()

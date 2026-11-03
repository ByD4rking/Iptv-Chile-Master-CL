#!/usr/bin/env python3
"""Ejecuta la actualización integral de la principal y reconcilia sus complementos."""
from pathlib import Path
import subprocess
import sys

import requests

import alimentar_principal as alimentador
from sincronizar_complementos import (
    _group_and_label_alternatives,
    _prioritize_infantiles,
    normalizar_nombres_solicitados,
    quitar_los_pitufos_es,
    get_last_url_priority,
    synchronize_once,
)

ROOT = Path(__file__).resolve().parents[1]
PRINCIPAL = ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"


def main():
    # La referencia de orden es la M3U comprometida en main, antes de que el
    # alimentador base normalice o reordene canales.
    original_lines = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()

    print("\n[ORQUESTADOR] Actualización base: Pluto, IPTVSV, MAGMA y fuentes existentes.")
    # El alimentador conserva las barreras de identidad/cobertura Pluto.
    alimentador.main()

    print("\n[ORQUESTADOR] Unificando categorías CHILE.")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "unificar_chile.py")],
        cwd=ROOT,
        check=True,
    )

    print("\n[ORQUESTADOR] Sincronizando todas las fuentes complementarias.")
    result = synchronize_once()

    # Restaurar el orden histórico DESPUÉS de sincronizar: el reconciliador puede
    # insertar alternativas en medio de una categoría. La restauración también
    # recupera bloques retirados; por eso se reaplican inmediatamente las
    # exclusiones explícitas de Pluto ES.
    current_lines = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()
    ordered_lines = alimentador.restaurar_orden_original_por_categoria(
        current_lines,
        original_lines,
    )
    ordered_lines = quitar_los_pitufos_es(ordered_lines)
    ordered_lines = [line.rstrip() for line in ordered_lines]

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    print("\n[ORQUESTADOR] Aplicando exclusiones y reclasificaciones finales.")
    ids_pluto_es_anime = alimentador.cargar_ids_pluto_es_anime(session)
    ordered_lines = alimentador.aplicar_ajustes_referencia(
        ordered_lines,
        ids_pluto_es_anime,
    )

    # MAGMA se vuelve a ordenar DESPUÉS de sincronizar: así los canales que
    # entren en este ciclo no quedan mezclados con el bloque histórico.
    ordered_lines, magma_stats = alimentador.ordenar_bloques_magma_y_originales(
        ordered_lines,
        session,
    )
    alimentador.validar_orden_canales(
        original_lines,
        ordered_lines,
        categorias_reordenables={
            "Entretenimiento / Cine / Series",
            "Infantiles",
            "Anime",
            "CHILE TV",
        },
    )

    print("\n[ORQUESTADOR] Agrupando alternativas y priorizando Infantiles.")
    ordered_lines = _group_and_label_alternatives(
        ordered_lines,
        get_last_url_priority(),
    )
    ordered_lines = _prioritize_infantiles(ordered_lines)
    ordered_lines = normalizar_nombres_solicitados(ordered_lines)

    temporary = PRINCIPAL.with_name(PRINCIPAL.name + ".orden.tmp")
    temporary.write_text("\n".join(ordered_lines) + "\n", encoding="utf-8")
    temporary.replace(PRINCIPAL)

    print("[ORQUESTADOR] Orden previo restaurado por categoría.")
    print("[ORQUESTADOR] Bloque MAGMA:", magma_stats)
    print("[ORQUESTADOR] Resultado de sincronización:", result)
    return result


if __name__ == "__main__":
    main()

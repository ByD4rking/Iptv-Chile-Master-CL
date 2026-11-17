#!/usr/bin/env python3
"""Ejecuta la actualización integral de la principal y reconcilia sus complementos."""
from pathlib import Path
import subprocess
import sys

import requests
import json
from auditar_logos import audit as auditar_logos, check_url as verificar_logo_url

import alimentar_principal as alimentador
from calidad_magma_cine import (
    audit_and_filter_channels as _audit_magma_cinema,
    probe_stream as _probe_magma_stream,
    remove_rejected_cinema_blocks as _remove_rejected_magma_cinema,
)
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
            # España recibe reclasificaciones regionales desde Anime.
            "España",
        },
    )

    print("\n[ORQUESTADOR] Agrupando alternativas y priorizando Infantiles.")
    ordered_lines = _group_and_label_alternatives(
        ordered_lines,
        get_last_url_priority(),
    )
    ordered_lines = _prioritize_infantiles(ordered_lines)
    ordered_lines = normalizar_nombres_solicitados(ordered_lines)

    # Última restauración de orden después de sincronizar y agrupar alternativas.
    # CHILE TV y Anime no son categorías reordenables: los canales históricos
    # mantienen su posición; los nuevos quedan al final. Infantiles y MAGMA
    # conservan sus reglas explícitas.
    ordered_lines = alimentador.restaurar_orden_original_por_categoria(
        ordered_lines,
        original_lines,
        categorias_reordenables={
            "Entretenimiento / Cine / Series",
            "Infantiles",
        },
    )
    # Reagrupar después de restaurar: el sincronizador ancla cada grupo en
    # la posición del canal base, por lo que las opciones quedan contiguas sin
    # desplazar el orden histórico de la categoría.
    ordered_lines = _group_and_label_alternatives(
        ordered_lines,
        get_last_url_priority(),
    )
    ordered_lines = alimentador.ordenar_anime_alfabeticamente(ordered_lines)
    ordered_lines = alimentador.ordenar_informativos(ordered_lines)
    ordered_lines = quitar_los_pitufos_es(ordered_lines)
    # Restaurar logos perdidos desde la versión anterior y el catálogo oficial Pluto.
    try:
        pluto_por_id, pluto_por_nombre, _, _ = alimentador.cargar_catalogo_pluto_propio(session)
    except Exception as error:
        print(f"[ORQUESTADOR] Catálogo Pluto no disponible para logos: {error}")
        pluto_por_id, pluto_por_nombre = {}, {}
    # GOD se consulta solo como catálogo histórico de logos; nunca se escribe ni modifica.
    god_path = ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"
    god_lines = god_path.read_text(encoding="utf-8-sig").splitlines() if god_path.is_file() else []
    referencias_logos = original_lines + god_lines
    logos_por_url_prioritarios = {}
    logos_forzados_por_url = {}
    ruta_referencias_logos = ROOT / "scripts" / "logo_references.json"
    if ruta_referencias_logos.is_file():
        try:
            datos_referencias = json.loads(ruta_referencias_logos.read_text(encoding="utf-8"))
            logos_por_url_prioritarios = {
                str(url).strip(): str(logo).strip()
                for url, logo in datos_referencias.get("logos", {}).items()
                if alimentador.url_es_valida(str(url).strip())
                and alimentador.url_es_valida(str(logo).strip())
            }
            logos_forzados_por_url = {
                str(url).strip(): str(logo).strip()
                for url, logo in datos_referencias.get("forced_overrides", {}).items()
                if alimentador.url_es_valida(str(url).strip())
                and alimentador.url_es_valida(str(logo).strip())
            }
            print(
                f"[LOGOS] Referencias manuales exactas={len(logos_por_url_prioritarios)}; "
                f"reemplazos explícitos={len(logos_forzados_por_url)}"
            )
        except (OSError, ValueError, TypeError) as error_referencias:
            print(f"[LOGOS] No se pudo cargar logo_references.json: {error_referencias}")

    # Solo se reemplazan logos con fallo confirmado (404/410 o contenido no-imagen).
    # 401/403, límites y errores transitorios quedan como inconclusos y se conservan.
    auditoria_logos = auditar_logos("\n".join(ordered_lines))
    logos_rotos_confirmados = {
        item["url"] for item in auditoria_logos["results"]
        if item.get("status") == "broken"
    }
    conteos_logos = auditoria_logos["logo_urls"]
    print(
        "[LOGOS AUDIT] "
        f"accesibles={conteos_logos.get('ok', 0)}; "
        f"rotos_confirmados={len(logos_rotos_confirmados)}; "
        f"inconclusos={conteos_logos.get('inconclusive', 0)}; "
        f"sin_logo={len(auditoria_logos['missing_logo_entries'])}."
    )
    cache_logos_candidatos = {}

    def validar_logo_candidato(url):
        if url not in cache_logos_candidatos:
            cache_logos_candidatos[url] = (
                verificar_logo_url(url).get("status") == "ok"
            )
        return cache_logos_candidatos[url]

    ordered_lines, logo_stats = alimentador.restaurar_logos_historicos(
        ordered_lines,
        referencias_logos,
        pluto_por_id,
        pluto_por_nombre,
        logos_por_url_prioritarios=logos_por_url_prioritarios,
        logos_forzados_por_url=logos_forzados_por_url,
        logos_bloqueados_por_url=alimentador.extraer_logos_bloqueados_por_url(original_lines),
        logos_rotos_confirmados=logos_rotos_confirmados,
        validar_logo=validar_logo_candidato,
    )
    # Último blindaje de orden: España y todos los países deben quedar al final.
    ordered_lines = alimentador.mover_paises_al_final(ordered_lines)
    # La sincronización complementaria tampoco puede recrear General.
    ordered_lines = alimentador.blindar_categoria_general(ordered_lines)

    # La restauración del orden histórico puede recuperar bloques previos.
    # Reaplicar al final la regla estricta solo a URLs de Cine/Películas MAGMA.
    respuesta_magma = session.get(alimentador.FUENTE_MAGMA, timeout=30)
    respuesta_magma.raise_for_status()
    canales_magma = alimentador.parsear_m3u(respuesta_magma.text)
    _, rechazados_magma, no_verificados_magma = _audit_magma_cinema(
        canales_magma,
        probe=lambda url: _probe_magma_stream(url, session=session),
    )
    urls_rechazadas_magma = {
        item["channel"].get("url", "").strip()
        for item in rechazados_magma
        if item["channel"].get("url", "").strip()
    }
    # No eliminar canales históricos por URL: la M3U no registra de forma
    # fiable su procedencia y una URL compartida podría afectar otra entrada.
    # Los nuevos candidatos MAGMA no conformes ya se bloquean en sincronización.
    print(
        "[ORQUESTADOR] Canales existentes preservados; "
        "nuevas importaciones MAGMA no conformes bloqueadas."
    )
    print(
        "[ORQUESTADOR] Regla MAGMA Cine/Películas: "
        f"{len(rechazados_magma)} rechazados por resolución/formato; "
        f"{len(no_verificados_magma)} sin verificar y conservados sin cambios."
    )

    ids_pluto_orden = (
        alimentador.obtener_ids_pluto_existentes(original_lines)
        | alimentador.obtener_ids_pluto_existentes(ordered_lines)
    )
    alimentador.validar_orden_canales(
        original_lines,
        ordered_lines,
        categorias_reordenables={
            "Entretenimiento / Cine / Series",
            "Infantiles",
            "Anime",
            "Informativos",
            # España recibe reclasificaciones regionales desde Anime.
            "España",
        },
        ids_pluto_omitidos=ids_pluto_orden,
    )

    temporary = PRINCIPAL.with_name(PRINCIPAL.name + ".orden.tmp")
    temporary.write_text("\n".join(ordered_lines) + "\n", encoding="utf-8")
    temporary.replace(PRINCIPAL)

    print("[ORQUESTADOR] Orden previo restaurado por categoría.")
    print("[ORQUESTADOR] Bloque MAGMA:", magma_stats)
    print("[ORQUESTADOR] Resultado de sincronización:", result)
    return result


if __name__ == "__main__":
    main()

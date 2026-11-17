#!/usr/bin/env python3
"""Ejecuta la actualización integral de la principal y reconcilia sus complementos."""
from pathlib import Path
import re
import subprocess
import sys

import requests

import alimentar_principal as alimentador
from blindajes_principal import (
    blindar_logos,
    ordenar_categorias_definitivo,
    priorizar_history_documentales,
    restaurar_categoria_bloqueada,
    validar_orden_categorias,
)
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
PITUFOS_MX_URL = "https://jmp2.uk/plu-68a3a97fd8f7693ae3f8575f.m3u8"


def _trace_pitufos_mx(etapa, lineas=None):
    if lineas is None:
        lineas = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()
    entradas = []
    for indice, linea in enumerate(lineas):
        if not linea.startswith("#EXTINF") or "pitufos" not in linea.lower():
            continue
        j = indice + 1
        while j < len(lineas) and lineas[j].startswith("#"):
            j += 1
        url = lineas[j].strip() if j < len(lineas) else ""
        entradas.append((linea.split(",", 1)[-1], url))
    print(
        f"[DIAGNÓSTICO PITUFOS MX] {etapa}: "
        f"URL MX exacta={'sí' if any(url == PITUFOS_MX_URL for _, url in entradas) else 'no'}; "
        f"entradas={entradas}"
    )


def main():
    # La referencia de orden es la M3U comprometida en main, antes de que el
    # alimentador base normalice o reordene canales.
    original_lines = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()

    print("\n[ORQUESTADOR] Actualización base: Pluto, IPTVSV, MAGMA y fuentes existentes.")
    # El alimentador conserva las barreras de identidad/cobertura Pluto.
    alimentador.main()
    _trace_pitufos_mx("después de alimentar_principal")

    print("\n[ORQUESTADOR] Unificando categorías CHILE.")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "unificar_chile.py")],
        cwd=ROOT,
        check=True,
    )

    print("\n[ORQUESTADOR] Sincronizando todas las fuentes complementarias.")
    result = synchronize_once()
    _trace_pitufos_mx("después de synchronize_once")

    # Restaurar el orden histórico DESPUÉS de sincronizar: el reconciliador puede
    # insertar alternativas en medio de una categoría. La restauración también
    # recupera bloques retirados; por eso se reaplican inmediatamente las
    # exclusiones explícitas de Pluto ES.
    current_lines = PRINCIPAL.read_text(encoding="utf-8-sig").splitlines()
    ordered_lines = alimentador.restaurar_orden_original_por_categoria(
        current_lines,
        original_lines,
    )
    _trace_pitufos_mx("después de restaurar orden", ordered_lines)
    ordered_lines = quitar_los_pitufos_es(ordered_lines)
    _trace_pitufos_mx("después de filtro Pitufos ES", ordered_lines)
    ordered_lines = [line.rstrip() for line in ordered_lines]

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    print("\n[ORQUESTADOR] Aplicando exclusiones y reclasificaciones finales.")
    ids_pluto_es_anime = alimentador.cargar_ids_pluto_es_anime(session)
    ordered_lines = alimentador.aplicar_ajustes_referencia(
        ordered_lines,
        ids_pluto_es_anime,
    )
    _trace_pitufos_mx("después de ajustes referencia", ordered_lines)

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
    _trace_pitufos_mx("después de agrupar/priorizar", ordered_lines)

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
    _trace_pitufos_mx("después de segunda agrupación", ordered_lines)
    ordered_lines = alimentador.ordenar_anime_alfabeticamente(ordered_lines)
    ordered_lines = alimentador.ordenar_informativos(ordered_lines)
    ordered_lines = quitar_los_pitufos_es(ordered_lines)
    # Restaurar logos perdidos desde la versión anterior y el catálogo oficial Pluto.
    try:
        pluto_por_id, pluto_por_nombre, _, _, _ = alimentador.cargar_catalogo_pluto_propio(session)
    except Exception as error:
        print(f"[ORQUESTADOR] Catálogo Pluto no disponible para logos: {error}")
        pluto_por_id, pluto_por_nombre = {}, {}
    # GOD se consulta solo como catálogo histórico de logos; nunca se escribe ni modifica.
    god_path = ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"
    god_lines = god_path.read_text(encoding="utf-8-sig").splitlines() if god_path.is_file() else []
    referencias_logos = original_lines + god_lines
    ordered_lines, logo_stats = alimentador.restaurar_logos_historicos(
        ordered_lines,
        referencias_logos,
        pluto_por_id,
        pluto_por_nombre,
        logos_bloqueados_por_url=alimentador.extraer_logos_bloqueados_por_url(original_lines),
        logos_bloqueados_por_identidad=alimentador.extraer_logos_bloqueados_por_identidad(original_lines),
        nombres_autorizados=alimentador.NOMBRES_LOGOS_AUTORIZADOS_PRINCIPAL,
        logos_autorizados_por_nombre=alimentador.LOGOS_AUTORIZADOS_PRINCIPAL,
    )
    # Último blindaje de orden: España y todos los países deben quedar al final.
    ordered_lines = alimentador.mover_paises_al_final(ordered_lines)
    # Agrupar variantes de una misma familia al final del flujo, preservando
    # el orden actual de categorías y de la primera aparición de cada familia.
    ordered_lines = alimentador.agrupar_familias_por_categoria(ordered_lines, original_lines)
    # La sincronización complementaria tampoco puede recrear General.
    ordered_lines = alimentador.blindar_categoria_general(ordered_lines)

    # La sincronización complementaria y las restauraciones de orden pueden
    # retirar una URL MX aunque el alimentador base ya la haya integrado.
    # Reconciliar Pluto MX DESPUÉS de todas las transformaciones estructurales
    # para que las alternativas externas sobrevivan en la salida publicada.
    ordered_lines, pluto_mx_final = alimentador.integrar_pluto_mx(
        ordered_lines,
        session,
    )
    print(
        "[ORQUESTADOR] Blindaje terminal Pluto MX: "
        f"{pluto_mx_final['agregadas']} alternativas recuperadas; "
        f"{pluto_mx_final['sin_coincidencia']} sin coincidencia."
    )
    _trace_pitufos_mx("después del blindaje terminal Pluto MX", ordered_lines)

    # La integración terminal puede añadir opciones después del agrupador inicial.
    # Reagrupar aquí para mantenerlas contiguas y renumerarlas por posición real.
    ordered_lines = alimentador.agrupar_alternativas_por_identidad(ordered_lines)

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

    # La agrupación global puede alterar el orden de las sagas; Anime se reordena
    # aquí, al final, para que Naruto/Boruto/Películas y las demás franquicias
    # respeten la secuencia canónica después de todas las reconciliaciones.
    ordered_lines = alimentador.ordenar_anime_alfabeticamente(ordered_lines)

    # Última reconciliación de Pluto después de todas las restauraciones,
    # agrupaciones y sincronizaciones complementarias. Evita que una etapa
    # posterior vuelva a introducir JWT antiguos en la maestra.
    ordered_lines, pluto_renovacion_final = alimentador.reemplazar_pluto_tercero_por_propio(
        ordered_lines,
        session,
    )
    print(
        "[ORQUESTADOR] Renovación final Pluto: "
        f"{pluto_renovacion_final['reemplazados']} URLs actualizadas; "
        f"{pluto_renovacion_final['conservados_sin_reemplazo']} conservadas sin "
        "correspondencia; "
        f"{pluto_renovacion_final['expirados_eliminados']} expiradas retiradas."
    )

    # Blindajes terminales: Anime se restaura íntegro desde la maestra de entrada;
    # todos los logos existentes se congelan por identidad; el orden global de
    # carpetas se aplica al final para que ninguna sincronización lo deshaga.
    ordered_lines = restaurar_categoria_bloqueada(
        ordered_lines, original_lines, "Anime"
    )
    ordered_lines, blindaje_logos_stats = blindar_logos(
        ordered_lines, original_lines
    )
    ordered_lines = ordenar_categorias_definitivo(ordered_lines)
    ordered_lines = priorizar_history_documentales(ordered_lines)
    validar_orden_categorias(ordered_lines)
    print("[ORQUESTADOR] Blindaje global de logos:", blindaje_logos_stats)
    print("[ORQUESTADOR] Orden global definitivo de categorías: validado.")
    jwt_pendientes = []
    for linea in ordered_lines:
        url = linea.strip()
        if "jwt=" not in url.lower() or not alimentador.es_url_pluto(url):
            continue
        country_match = re.search(r"(?:[?&])country=([A-Za-z]{2})", url, re.I)
        # Solo bloquear la publicación por regiones que este reconciliador
        # puede renovar (LATAM/ES/MX). Regiones ajenas al catálogo se preservan.
        if country_match and country_match.group(1).lower() not in {"mx", "es"}:
            continue
        if alimentador.jwt_necesita_renovacion_en_url(url):
            jwt_pendientes.append(url)
    if jwt_pendientes:
        raise RuntimeError(
            "La maestra no se publica: quedan "
            f"{len(jwt_pendientes)} URLs Pluto con JWT vencido o con menos de "
            "6 horas de vigencia. Se conserva la lista anterior."
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
            "Informativos",  # Se ordena explícitamente por prioridad y regionales.
            "Documentales y Cultura",  # Reordenación History autorizada explícitamente.
            # España recibe reclasificaciones regionales desde Anime.
            "España",
        },
        ids_pluto_omitidos=ids_pluto_orden,
    )

    _trace_pitufos_mx("antes de escribir", ordered_lines)
    temporary = PRINCIPAL.with_name(PRINCIPAL.name + ".orden.tmp")
    temporary.write_text("\n".join(ordered_lines) + "\n", encoding="utf-8")
    temporary.replace(PRINCIPAL)

    print("[ORQUESTADOR] Orden previo restaurado por categoría.")
    print("[ORQUESTADOR] Bloque MAGMA:", magma_stats)
    print("[ORQUESTADOR] Resultado de sincronización:", result)
    return result


if __name__ == "__main__":
    main()

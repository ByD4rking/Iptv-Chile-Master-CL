#!/usr/bin/env python3
"""Sincronización incremental común de todas las fuentes complementarias.

No elimina canales por ausencia en una fuente. La identidad estable (tvg-id,
o nombre inequívoco como respaldo) permite actualizar URL y categoría aunque
la URL anterior haya cambiado.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import requests

import alimentar_principal as ap

BASE = Path(__file__).resolve().parent.parent
PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
MANIFEST = BASE / "scripts" / "sync_sources.json"
TIMEOUT = 30

# Solo LATAM, España y México alimentan la principal. Las demás regiones
# Pluto siguen disponibles como playlists independientes.
# LATAM y España son nuestras listas tokenizadas. México entra desde la lista
# externa PlutoTV.MX, con enlaces jmp2.uk sin JWT. La playlist MX propia con
# JWT permanece independiente y no se copia a la maestra.
FUENTES_PLUTO_COMPLETAS = [ap.FUENTES_PLUTO[0], ap.FUENTES_PLUTO[1], ap.FUENTE_PLUTO_ALTERNATIVAS]

LAST_URL_PRIORITY: dict[str, int] = {}


def get_last_url_priority() -> dict[str, int]:
    return dict(LAST_URL_PRIORITY)


def _attr(text: str, name: str) -> str:
    match = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', text or "", re.I)
    return match.group(1).strip() if match else ""


def _is_pluto_url(url: str) -> bool:
    return ap.es_url_pluto(url or "") or bool(
        re.search(r"jmp2\.uk/plu-[a-f0-9]{20,}\.m3u8", url or "", re.I)
    )


TVG_IDS_INVALIDOS = {"", "-1", "0", "none", "null", "na", "n/a", "undefined"}


def _valid_tvg_id(value: str) -> str:
    value = str(value or "").strip()
    return value if ap.normalizar(value) not in TVG_IDS_INVALIDOS else ""


def _identity(channel: dict, *, pluto: bool = False) -> str:
    extinf = channel.get("extinf", "")
    url = channel.get("url", "") or ""
    channel_id = ""
    if pluto:
        channel_id = ap.extraer_pluto_id(url)
        if not channel_id:
            match = re.search(r"/plu-([a-f0-9]{20,})\.m3u8", url, re.I)
            channel_id = match.group(1) if match else ""
    if not channel_id:
        channel_id = _valid_tvg_id(_attr(extinf, "tvg-id"))
    if channel_id:
        return "id:" + ap.normalizar(channel_id)
    name = _base_channel_name(_attr(extinf, "tvg-name") or channel.get("nombre", ""))
    return "name:" + name if name else ""


def _base_channel_name(name: str) -> str:
    name = re.sub(r"\s*(?:\[\s*v2\s*\]|\(\s*v2\s*\)|v2)\s*$", " 2", name or "", flags=re.I)
    name = re.sub(
        r"\s*(?:\[\s*opc(?:ion)?\.?\s*\d+\s*\]|\(\s*opci[oó]n\s*\d+\s*\))\s*$",
        "",
        name or "",
        flags=re.I,
    )
    name = re.sub(
        r"\s*(?:\[\s*pluto(?:\s*tv)?\s*(?:es|españa)\s*\]|\(\s*pluto(?:\s*tv)?\s*(?:es|españa)\s*\))\s*$",
        "",
        name,
        flags=re.I,
    )
    name = re.sub(r"\s+(?:hd|sd|fhd|uhd)$", "", name, flags=re.I)
    return ap.normalizar(name)


def _is_los_pitufos(extinf: str) -> bool:
    """Identifica el canal sin confundirlo con su variante española."""
    tvg_name = _attr(extinf, "tvg-name")
    display_name = ap.extraer_nombre(extinf)
    return (
        _base_channel_name(tvg_name) == "los pitufos"
        or _base_channel_name(display_name) == "los pitufos"
    )


def _is_los_pitufos_es(extinf: str) -> bool:
    """Identifica la variante española por etiqueta explícita."""
    for value in (_attr(extinf, "tvg-name"), ap.extraer_nombre(extinf)):
        normalized = ap.normalizar(value)
        if normalized.startswith("los pitufos ") and normalized.split()[-1].strip("()[]{}.,") in {"es", "espana"}:
            return True
        if normalized in {"los pitufos pluto es", "los pitufos pluto espana"}:
            return True
    return False


def _is_los_pitufos_es_channel(extinf: str, url: str = "") -> bool:
    """Identifica Los Pitufos España por etiqueta o región de la URL."""
    return _is_los_pitufos_es(extinf) or (
        _is_los_pitufos(extinf) and _is_pluto_es_url(url)
    )


def _source_priority(source: str) -> int:
    """Prioridad de alternativas acordada: LATAM, MX, MAGMA y luego el resto."""
    if source == ap.FUENTES_PLUTO[0]:
        return 0
    if source == ap.FUENTE_PLUTO_ALTERNATIVAS:
        return 1
    if source == ap.FUENTE_MAGMA:
        return 2
    if source == ap.FUENTES_PLUTO[1]:
        return 3
    if source == ap.FUENTE_IPTVSV:
        return 4
    return 5


def _set_display_name(extinf: str, display_name: str) -> str:
    head, comma, _ = extinf.partition(",")
    return head + comma + display_name if comma else extinf


def _without_option_suffix(value: str) -> str:
    return re.sub(
        r"\s*(?:\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]|\(\s*(?:opci[oó]n|option)\s*\d+\s*\))\s*$",
        "",
        value or "",
        flags=re.I,
    ).strip()


def _canonical_channel_name(channel: dict) -> str:
    # El nombre visible identifica la variante real. Algunas fuentes reutilizan
    # tvg-name entre streams distintos (p. ej. Cartoonito HD Opc.3/Opc.4) o lo
    # escriben distinto para dos URLs del mismo canal (p. ej. CYGTVCL).
    # Por eso el display-name tiene prioridad; tvg-name queda como respaldo.
    value = (
        channel.get("nombre", "")
        or ap.extraer_nombre(channel.get("extinf", ""))
        or _attr(channel.get("extinf", ""), "tvg-name")
    )
    value = _without_option_suffix(value)
    value = re.sub(r"\s*(?:\[\s*v2\s*\]|\(\s*v2\s*\)|v2)\s*$", " 2", value, flags=re.I)
    value = re.sub(
        r"\s*(?:\[\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\]|"
        r"\(\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\))\s*$",
        "",
        value,
        flags=re.I,
    )
    value = re.sub(
        r"\s*(?:[-–—|•]\s*)?(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?|"
        r"espanol|españa|spanish|hd|sd|fhd|uhd)$",
        "",
        value,
        flags=re.I,
    )
    return re.sub(r"[^a-z0-9]+", "", ap.normalizar(value))


def normalizar_nombres_solicitados(lines: list[str]) -> list[str]:
    """Normaliza Delmi TV V2 y lo ubica en Anime sin duplicar ni alterar su URL."""
    result = list(lines)
    for index, line in enumerate(result):
        if not line.startswith("#EXTINF:"):
            continue
        name_key = re.sub(r"[^a-z0-9]+", "", ap.normalizar(ap.extraer_nombre(line)))
        if name_key in {"delmitvv2", "delmitv2"}:
            line = _set_display_name(line, "Delmi TV 2")
            result[index] = _set_attr(line, "group-title", "Anime")
    return result


def _canonical_category(value: str) -> str:
    category = ap.normalizar(value or "")
    if category in {"infantil", "infantiles"}:
        return "infantiles"
    return category


def _is_spanish_anime_label(extinf: str) -> bool:
    value = ap.normalizar(_attr(extinf, "tvg-name") + " " + ap.extraer_nombre(extinf))
    return bool(re.search(r"\b(?:espanol|espana|pluto\s*es)\b", value))


def _is_pluto_es_url(url: str) -> bool:
    value = (url or "").lower()
    return any(marker in value for marker in (
        "country=es",
        "marketingregion=es",
        "preferredlanguage=es-es",
    ))


def _clean_channel_display(value: str) -> str:
    value = _without_option_suffix(value)
    value = re.sub(
        r"\s*(?:\[\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\]|"
        r"\(\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\))\s*$",
        "",
        value or "",
        flags=re.I,
    )
    value = re.sub(
        r"\s*(?:[-–—|•]\s*)?(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?|"
        r"espanol|españa|spanish)$",
        "",
        value,
        flags=re.I,
    )
    return value.strip()


def _clean_channel_display_preserving_option(value: str) -> str:
    option = re.search(
        r"\s*(\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]|\(\s*(?:opci[oó]n|option)\s*\d+\s*\))\s*$",
        value or "",
        flags=re.I,
    )
    suffix = option.group(1) if option else ""
    base = (value or "")[:option.start()] if option else (value or "")
    cleaned = _clean_channel_display(base)
    return f"{cleaned} {suffix}".strip() if suffix else cleaned


def _merge_alternative_extinf(primary: str, alternative: str, destination: str) -> str:
    result = _merge_extinf(primary, alternative, destination)
    for key in ("tvg-id", "tvg-name"):
        value = _attr(primary, key)
        if value:
            result = _set_attr(result, key, value)
    display = _clean_channel_display(ap.extraer_nombre(primary))
    if display:
        result = _set_display_name(result, display)
    return result


def _group_and_label_alternatives(lines: list[str], url_priority: dict[str, int]) -> list[str]:
    """Agrupa URLs por nombre/categoría inequívocos y comparte ID, nombre y logo."""
    prefix, blocks, trailing = _read_blocks(lines)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for block in blocks:
        if not block.get("url"):
            continue
        canonical_name = _canonical_channel_name({
            "extinf": block["extinf"],
            "nombre": ap.extraer_nombre(block["extinf"]),
            "url": block["url"],
        })
        category = _canonical_category(ap.extraer_categoria(block["extinf"]))
        if canonical_name:
            grouped[(category, canonical_name)].append(block)

    ordered: list[dict] = []
    emitted: set[tuple[str, str]] = set()
    for block in blocks:
        if not block.get("url"):
            ordered.append(block)
            continue
        canonical_name = _canonical_channel_name({
            "extinf": block["extinf"],
            "nombre": ap.extraer_nombre(block["extinf"]),
            "url": block["url"],
        })
        category_key = _canonical_category(ap.extraer_categoria(block["extinf"]))
        group_key = (category_key, canonical_name)
        group = grouped.get(group_key, [])
        group_ids = {
            _valid_tvg_id(_attr(item["extinf"], "tvg-id"))
            for item in group
            if _valid_tvg_id(_attr(item["extinf"], "tvg-id"))
        }
        if not canonical_name or len(group) < 2 or len(group_ids) > 1:
            extinf = block["extinf"]
            clean_display = _clean_channel_display_preserving_option(ap.extraer_nombre(extinf))
            extinf = _set_display_name(extinf, clean_display)
            clean_tvg_name = _clean_channel_display_preserving_option(_attr(extinf, "tvg-name"))
            if clean_tvg_name:
                extinf = _set_attr(extinf, "tvg-name", clean_tvg_name)
            block["extinf"] = extinf
            block["raw"] = [extinf] + block["extras"] + [block["url"]]
            ordered.append(block)
            continue
        if group_key in emitted:
            continue
        emitted.add(group_key)

        # Prioridad: Pluto LATAM, Pluto MX externo sin JWT, MAGNA y después
        # URLs históricas cuya fuente ya no está disponible.
        unique: list[dict] = []
        seen_urls: set[str] = set()
        for item in sorted(group, key=lambda value: url_priority.get(value["url"], 10)):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique.append(item)
        if not unique:
            continue

        primary = unique[0]
        base_display = _clean_channel_display(ap.extraer_nombre(primary["extinf"]))
        if not base_display:
            base_display = _clean_channel_display(_attr(primary["extinf"], "tvg-name"))
        base_tvg_name = next(
            (
                _clean_channel_display(_attr(item["extinf"], "tvg-name"))
                for item in unique
                if _clean_channel_display(_attr(item["extinf"], "tvg-name"))
            ),
            base_display,
        )

        channel_id = ""
        for item in unique:
            url = item.get("url", "")
            if _is_pluto_url(url):
                channel_id = ap.extraer_pluto_id(url)
                if not channel_id:
                    match = re.search(r"/plu-([a-f0-9]{20,})\.m3u8", url, re.I)
                    channel_id = match.group(1) if match else ""
                if channel_id:
                    break
        if not channel_id:
            channel_id = next(
                (_valid_tvg_id(_attr(item["extinf"], "tvg-id")) for item in unique if _valid_tvg_id(_attr(item["extinf"], "tvg-id"))),
                "",
            )

        category = next(
            (ap.extraer_categoria(item["extinf"]) for item in unique if ap.extraer_categoria(item["extinf"])),
            "",
        )
        logo = next(
            (
                _attr(item["extinf"], "tvg-logo") or _attr(item["extinf"], "logo")
                for item in unique
                if _attr(item["extinf"], "tvg-logo") or _attr(item["extinf"], "logo")
            ),
            "",
        )
        for option_index, item in enumerate(unique, start=1):
            extinf = item["extinf"]
            if channel_id:
                extinf = _set_attr(extinf, "tvg-id", channel_id)
            if base_tvg_name:
                extinf = _set_attr(extinf, "tvg-name", base_tvg_name)
            if category:
                extinf = _set_attr(extinf, "group-title", category)
            if logo:
                extinf = _set_attr(extinf, "tvg-logo", logo)
                extinf = _set_attr(extinf, "logo", logo)
            label = base_display if option_index == 1 else f"{base_display} [Opción {option_index}]"
            extinf = _set_display_name(extinf, label)
            item["extinf"] = extinf
            item["raw"] = [extinf] + item["extras"] + [item["url"]]
            ordered.append(item)

    output = list(prefix)
    for block in ordered:
        output.extend(block.get("raw") or ([block["extinf"]] + block["extras"] + ([block["url"]] if block.get("url") else [])))
    output.extend(trailing)
    return output


def _prioritize_infantiles(lines: list[str]) -> list[str]:
    """Deja Popeye, Los Pitufos y Heidi al inicio de Infantiles, en ese orden."""
    prefix, blocks, trailing = _read_blocks(lines)
    targets = ("popeye", "los pitufos", "heidi")
    selected: dict[str, list[dict]] = {name: [] for name in targets}
    for block in blocks:
        if ap.normalizar(ap.extraer_categoria(block["extinf"])) not in {"infantiles", "infantil"}:
            continue
        name = ap.normalizar(_without_option_suffix(ap.extraer_nombre(block["extinf"])))
        for target in targets:
            if name == target or name.startswith(target + " "):
                selected[target].append(block)
                break

    moving_ids = {id(block) for group in selected.values() for block in group}
    if not moving_ids:
        return lines
    remaining = [block for block in blocks if id(block) not in moving_ids]
    first_kids = next((i for i, block in enumerate(remaining) if ap.normalizar(ap.extraer_categoria(block["extinf"])) in {"infantiles", "infantil"}), len(remaining))
    ordered_targets = [block for target in targets for block in selected[target]]
    blocks = remaining[:first_kids] + ordered_targets + remaining[first_kids:]
    output = list(prefix)
    for block in blocks:
        output.extend(block.get("raw") or ([block["extinf"]] + block["extras"] + ([block["url"]] if block.get("url") else [])))
    output.extend(trailing)
    return output


def _set_attr(extinf: str, key: str, value: str) -> str:
    if not value:
        return extinf
    pattern = r'(?<![\w-])' + re.escape(key) + r'="[^"]*"'
    replacement = f'{key}="{value}"'
    if re.search(pattern, extinf, re.I):
        return re.sub(pattern, lambda _: replacement, extinf, count=1, flags=re.I)
    comma = extinf.find(",")
    if comma < 0:
        return extinf
    return extinf[:comma].rstrip() + " " + replacement + extinf[comma:]


def _merge_extinf(current: str, source: str, destination: str) -> str:
    """Actualiza categoría/logos sin sobrescribir la identidad ya existente."""
    result = current
    existing_id = _valid_tvg_id(_attr(current, "tvg-id"))
    source_id = _valid_tvg_id(_attr(source, "tvg-id"))
    if existing_id and source_id:
        result = _set_attr(result, "tvg-id", source_id)

    # En un bloque existente, el nombre visible y tvg-name son datos
    # protegidos. Algunas fuentes reutilizan el tvg-name de Opc.3 para la URL
    # que en la maestra está identificada como Opc.4; no deben renombrarla.
    existing_tvg_name = _attr(current, "tvg-name")
    source_name = _attr(source, "tvg-name")
    if not existing_tvg_name and not ap.extraer_nombre(current) and source_name:
        result = _set_attr(result, "tvg-name", _clean_channel_display(source_name))

    existing_display = ap.extraer_nombre(current)
    source_display = ap.extraer_nombre(source)
    if not existing_display and source_display:
        result = _set_display_name(result, _clean_channel_display(source_display))

    for key in ("tvg-logo", "logo", "tvg-language", "tvg-country", "tvg-chno"):
        value = _attr(source, key)
        if value:
            result = _set_attr(result, key, value)

    return _set_attr(result, "group-title", destination)


def _read_blocks(lines: list[str]) -> tuple[list[str], list[dict], list[str]]:
    prefix: list[str] = []
    blocks: list[dict] = []
    trailing: list[str] = []
    i = 0
    seen_entry = False
    while i < len(lines):
        if not lines[i].startswith("#EXTINF:"):
            if seen_entry:
                trailing.append(lines[i])
            else:
                prefix.append(lines[i])
            i += 1
            continue
        seen_entry = True
        extinf = lines[i]
        j = i + 1
        while j < len(lines) and lines[j].startswith("#") and not lines[j].startswith("#EXTINF:"):
            j += 1
        if j >= len(lines) or not ap.url_es_valida(lines[j].strip()):
            # No se destruye una entrada malformada: se conserva como bloque.
            blocks.append({"extinf": extinf, "extras": lines[i + 1:j], "url": "", "raw": lines[i:j]})
            i = j
            continue
        blocks.append({
            "extinf": extinf,
            "extras": lines[i + 1:j],
            "url": lines[j].strip(),
            "raw": lines[i:j + 1],
        })
        i = j + 1
    return prefix, blocks, trailing


def quitar_los_pitufos_es(lines: list[str]) -> list[str]:
    """Retira solo los bloques explícitamente identificados como Los Pitufos ES."""
    result: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("#EXTINF:"):
            result.append(lines[index])
            index += 1
            continue
        start = index
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].startswith("#") and not lines[cursor].startswith("#EXTINF:"):
            cursor += 1
        end = cursor + 1 if cursor < len(lines) and ap.url_es_valida(lines[cursor].strip()) else cursor
        url = lines[cursor].strip() if cursor < len(lines) and ap.url_es_valida(lines[cursor].strip()) else ""
        if not _is_los_pitufos_es_channel(lines[start], url):
            result.extend(lines[start:end])
        index = end
    return result


def _source_label(source: str) -> str:
    known = {
        ap.FUENTE_IPTVSV: "IPTVSV",
        ap.FUENTE_MAGMA: "MAGMA",
        ap.FUENTES_PLUTO[0]: "Pluto LATAM",
        ap.FUENTES_PLUTO[1]: "Pluto ES",
        ap.FUENTES_PLUTO[2]: "Pluto MX JWT interno",
        ap.FUENTE_PLUTO_ALTERNATIVAS: "Pluto MX",
    }
    if source in known:
        return known[source]
    return (source or "fuente_desconocida").rstrip("/").rsplit("/", 1)[-1]


def _destination(source_url: str, channel: dict, categories: list[str]) -> str | None:
    category = (channel.get("categoria") or "").strip()
    name = channel.get("nombre", "")
    category_norm = ap.normalizar(category)
    canonical_name = _canonical_channel_name(channel)
    # Estos tres canales van al comienzo de la categoría infantil aunque
    # Pluto LATAM los publique bajo Retro o Pluto MX no incluya group-title.
    if canonical_name in {"popeye", "lospitufos", "heidi"}:
        if canonical_name == "lospitufos" and source_url == ap.FUENTES_PLUTO[1]:
            return None
        return "Infantiles"
    if not category:
        return None

    if source_url == ap.FUENTE_IPTVSV:
        # TV Chichicasteca pertenece a Chichicastenango, Guatemala; no es
        # contenido salvadoreño aunque llegue desde la fuente IPTV-SV.
        if category_norm in {"tv chichicasteca", "los chichastecas"}:
            return "Guatemala"
        country_destinations = {
            "el salvador": "El Salvador",
            "el salvador - tcs": "El Salvador",
            "el salvador local": "El Salvador",
            "guatemala": "Guatemala",
            "honduras": "Honduras",
            "costa rica": "Costa Rica",
            "mexico": "México",
            "colombia": "Colombia",
            "ecuador": "Ecuador",
            "peru": "Perú",
            "chile": "CHILE TV",
            "argentina": "Argentina",
            "paraguay": "Paraguay",
            "republica dominicana": "República Dominicana",
            "venezuela": "Venezuela",
            "bolivia": "Bolivia",
            "espana": "España",
            "brasil": "Brasil",
            "panama": "Panamá",
            "nicaragua": "Nicaragua",
            "cuba": "Cuba",
            "puerto rico": "Puerto Rico",
            "uruguay": "Uruguay",
        }
        if category_norm in country_destinations:
            return country_destinations[category_norm]
        return ap.determinar_destino_iptvsv(category, name, categories) or category

    if source_url == ap.FUENTE_MAGMA:
        return ap.determinar_destino_magma(category, name, categories) or category

    if source_url in FUENTES_PLUTO_COMPLETAS:
        if source_url.lower().endswith("pluto_es.m3u") and category_norm == "anime":
            return None
        destination = ap.determinar_destino_pluto(category, name, categories)
        if destination:
            return destination
        # Las carpetas nuevas de Pluto se crean usando el group-title de origen.
        return None if category_norm in {"pluto tv", "total", "otros"} else category

    pais = next(
        (country for suffix, country in ap.PAIS_POR_FUENTE.items() if suffix.lower() in source_url.lower()),
        None,
    )
    return ap.determinar_destino(category, name, pais, categories)


def collect_candidates(session: requests.Session) -> tuple[list[dict], dict]:
    """Descarga fuentes válidas; una fuente vacía/rota nunca provoca borrados."""
    ordinary = list(ap.FUENTES)
    # Orden explícito de autoridad para la misma identidad.
    ordered = [ap.FUENTE_IPTVSV, ap.FUENTE_MAGMA]
    ordered.extend(url for url in ordinary if url not in ordered)
    ordered.extend(FUENTES_PLUTO_COMPLETAS)

    candidates: list[dict] = []
    stats = {"fuentes_ok": 0, "fuentes_error": 0, "canales_fuente": 0, "sin_categoria": 0}
    for source_url in ordered:
        try:
            response = session.get(source_url, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.text or ""
            if not body.lstrip("\ufeff \r\n\t").startswith("#EXTM3U"):
                raise ValueError("respuesta sin cabecera #EXTM3U")
            parsed = ap.parsear_m3u(body)
            if not parsed:
                raise ValueError("fuente sin entradas M3U válidas")
            stats["fuentes_ok"] += 1
        except Exception as exc:
            stats["fuentes_error"] += 1
            print(f"[SYNC] Fuente omitida sin alterar la maestra: {source_url} :: {exc}")
            continue

        for channel in parsed:
            if _is_los_pitufos_es_channel(channel.get("extinf", ""), channel.get("url", "")):
                continue
            if (
                ap.normalizar(channel.get("categoria", "")) == "anime"
                and _is_spanish_anime_label(channel.get("extinf", ""))
            ):
                continue
            url = (channel.get("url") or "").strip()
            if not ap.url_es_valida(url):
                continue
            candidate = dict(channel)
            candidate["source"] = source_url
            candidate["is_pluto"] = source_url in FUENTES_PLUTO_COMPLETAS
            identity = _identity(candidate, pluto=candidate["is_pluto"])
            candidate["identity"] = identity
            candidates.append(candidate)
            stats["canales_fuente"] += 1

    if not stats["fuentes_ok"]:
        raise RuntimeError("Ninguna fuente complementaria entregó una M3U válida; no se modifica la maestra.")
    return candidates, stats


def reconcile_lines(lines: list[str], candidates: list[dict], manifest: dict | None = None) -> tuple[list[str], dict]:
    """Agrega, actualiza URL/metadatos y reclasifica por identidad estable.

    El manifiesto conserva qué fuente es propietaria de cada canal. Así MAGNA
    puede actualizar sus canales aunque otra lista también publique el mismo ID.
    """
    if manifest is None:
        manifest = {}
    prefix, blocks, trailing = _read_blocks(lines)

    # Excluir Pluto España de Anime, pero mantener el mismo ID si también
    # está disponible en Pluto LATAM o México.
    pluto_es_anime_ids = {
        "id:" + ap.normalizar(channel_id)
        for channel_id in ap.PLUTO_ES_ANIME_IDS_HISTORICOS
    }
    pluto_es_anime_urls = {
        candidate["url"].strip()
        for candidate in candidates
        if candidate.get("source") == ap.FUENTES_PLUTO[1]
        and ap.normalizar(candidate.get("categoria", "")) == "anime"
        and candidate.get("url")
    }
    pluto_latam_mx_ids = set()
    for candidate in candidates:
        identity = candidate.get("identity") or _identity(
            candidate, pluto=candidate.get("is_pluto", False)
        )
        if not identity.startswith("id:"):
            continue
        source = candidate.get("source", "")
        category = ap.normalizar(candidate.get("categoria", ""))
        if source == ap.FUENTES_PLUTO[1] and category == "anime":
            pluto_es_anime_ids.add(identity)
        elif source in {ap.FUENTES_PLUTO[0], ap.FUENTE_PLUTO_ALTERNATIVAS}:
            # Si el mismo ID existe en MX/LATAM, se conserva esa versión aunque
            # la categoría regional sea distinta de Anime.
            pluto_latam_mx_ids.add(identity)
    pluto_es_only_ids = pluto_es_anime_ids - pluto_latam_mx_ids

    # Retirar únicamente la variante española no funcional; la versión
    # normal de Los Pitufos debe permanecer en Infantiles.
    filtered_blocks = []
    pitufos_removed = 0
    pluto_es_anime_removed = 0
    chichicasteca_moved = 0
    for block in blocks:
        identity = _identity(
            {"extinf": block["extinf"], "nombre": ap.extraer_nombre(block["extinf"]), "url": block["url"]},
            pluto=_is_pluto_url(block.get("url", "")),
        )
        owner_record = manifest.get(identity, {})
        owner_is_pluto_es = (
            isinstance(owner_record, dict)
            and owner_record.get("source") == ap.FUENTES_PLUTO[1]
        )
        if (
            _is_los_pitufos_es(block["extinf"])
            or (
                _is_los_pitufos(block["extinf"])
                and block.get("url")
                and (_is_pluto_es_url(block["url"]) or owner_is_pluto_es)
            )
        ):
            pitufos_removed += 1
            manifest.pop(identity, None)
            continue
        if (
            ap.normalizar(ap.extraer_categoria(block["extinf"])) == "anime"
            and (
                _is_spanish_anime_label(block["extinf"])
                or (
                    block.get("url")
                    and _is_pluto_url(block["url"])
                    and identity in pluto_es_anime_ids
                    and (
                        identity in pluto_es_only_ids
                        or _is_pluto_es_url(block["url"])
                        or block["url"].strip() in pluto_es_anime_urls
                    )
                )
            )
        ):
            pluto_es_anime_removed += 1
            manifest.pop(identity, None)
            continue
        if ap.normalizar(ap.extraer_categoria(block["extinf"])) in {"tv chichicasteca", "los chichastecas"}:
            moved_extinf = _set_attr(block["extinf"], "group-title", "Guatemala")
            if moved_extinf != block["extinf"]:
                chichicasteca_moved += 1
                block["extinf"] = moved_extinf
                if block.get("raw"):
                    block["raw"][0] = moved_extinf
        filtered_blocks.append(block)
    blocks = filtered_blocks

    categories = ap.categorias_de_lineas(lines)
    category_lookup = {ap.normalizar(value): value for value in categories}

    # Pluto MX externo no publica group-title útil en la mayoría de sus URLs.
    # Heredar categoría solo cuando LATAM/ES/MAGMA o la maestra dan un destino
    # único; si hay conflicto, no se inventa una categoría.
    main_destinations_by_id: dict[str, list[str]] = defaultdict(list)
    main_destinations_by_name: dict[str, list[str]] = defaultdict(list)
    for block in blocks:
        category = ap.extraer_categoria(block["extinf"])
        if not category:
            continue
        identity = _identity(
            {
                "extinf": block["extinf"],
                "nombre": ap.extraer_nombre(block["extinf"]),
                "url": block.get("url", ""),
            },
            pluto=_is_pluto_url(block.get("url", "")),
        )
        if identity.startswith("id:"):
            main_destinations_by_id[identity].append(category)
        canonical = _canonical_channel_name(
            {"extinf": block["extinf"], "nombre": ap.extraer_nombre(block["extinf"])}
        )
        if canonical:
            main_destinations_by_name[canonical].append(category)

    pluto_destinations_by_name: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        if candidate.get("source") not in {
            ap.FUENTES_PLUTO[0],
            ap.FUENTES_PLUTO[1],
            ap.FUENTE_MAGMA,
        }:
            continue
        destination = _destination(candidate.get("source", ""), candidate, categories)
        canonical = _canonical_channel_name(candidate)
        if destination and canonical:
            pluto_destinations_by_name[canonical].append(destination)

    def unique_destination(values: list[str]) -> str | None:
        distinct = {_canonical_category(value) for value in values if value}
        if len(distinct) != 1:
            return None
        key = next(iter(distinct))
        return next(value for value in values if _canonical_category(value) == key)

    # Recalcular destinos con el catálogo real de categorías de la maestra.
    valid_candidates = []
    valid_by_source = Counter()
    skipped_by_source = Counter()
    pitufos_by_source = Counter()
    for candidate in candidates:
        source_label = _source_label(candidate.get("source", ""))
        if _is_los_pitufos_es(candidate.get("extinf", "")):
            pitufos_by_source[source_label] += 1
            continue
        destination = _destination(
            candidate.get("source", ""),
            candidate,
            categories,
        )
        if not destination and candidate.get("source") == ap.FUENTE_PLUTO_ALTERNATIVAS:
            canonical = _canonical_channel_name(candidate)
            identity = candidate.get("identity") or _identity(candidate, pluto=True)
            destination = unique_destination(pluto_destinations_by_name.get(canonical, []))
            if not destination:
                destination = unique_destination(main_destinations_by_id.get(identity, []))
            if not destination:
                destination = unique_destination(main_destinations_by_name.get(canonical, []))
        if not destination:
            skipped_by_source[source_label] += 1
            continue
        valid_by_source[source_label] += 1
        item = dict(candidate)
        # Reutiliza el nombre canónico existente; si no existe, crea la
        # categoría al añadir el primer canal con ese group-title.
        item["destination"] = category_lookup.get(ap.normalizar(destination), destination)
        valid_candidates.append(item)

    main_by_id: dict[str, list[int]] = defaultdict(list)
    main_by_name: dict[str, list[int]] = defaultdict(list)
    main_by_canonical_name: dict[str, list[int]] = defaultdict(list)
    main_by_url: dict[str, int] = {}
    for index, block in enumerate(blocks):
        if not block.get("url"):
            continue
        identity = _identity({
            "extinf": block["extinf"],
            "nombre": ap.extraer_nombre(block["extinf"]),
            "url": block["url"],
        }, pluto=_is_pluto_url(block["url"]))
        if identity.startswith("id:"):
            main_by_id[identity].append(index)
        main_by_url.setdefault(block["url"], index)
        name = ap.normalizar(_attr(block["extinf"], "tvg-name") or ap.extraer_nombre(block["extinf"]))
        if name:
            main_by_name[name].append(index)
        canonical_name = _canonical_channel_name({
            "extinf": block["extinf"],
            "nombre": ap.extraer_nombre(block["extinf"]),
        })
        if canonical_name:
            main_by_canonical_name[canonical_name].append(index)

    candidate_groups: dict[str, list[dict]] = defaultdict(list)
    for item in valid_candidates:
        identity = item.get("identity") or _identity(
            item, pluto=item.get("is_pluto", False)
        )
        if identity:
            candidate_groups[identity].append(item)

    for identity, group in candidate_groups.items():
        group.sort(key=lambda item: _source_priority(item.get("source", "")))

    # Varias fuentes pueden asignar tvg-id distintos al mismo canal. Si el
    # nombre normalizado y la categoría son únicos, se reúnen como opciones.
    by_canonical_name: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)
    for identity, group in candidate_groups.items():
        canonical_name = _canonical_channel_name(group[0])
        if canonical_name:
            by_canonical_name[canonical_name].append((identity, group))
    for canonical_name, parts in by_canonical_name.items():
        main_matches = main_by_canonical_name.get(canonical_name, [])
        main_categories = {
            _canonical_category(ap.extraer_categoria(blocks[index]["extinf"]))
            for index in main_matches
        }
        main_ids = {
            _attr(blocks[index]["extinf"], "tvg-id")
            for index in main_matches
            if _attr(blocks[index]["extinf"], "tvg-id")
        }
        if len(parts) < 2 or len(main_categories) > 1 or len(main_ids) > 1:
            continue
        combined = [item for _, group in parts for item in group]
        destinations = {_canonical_category(item.get("destination", "")) for item in combined}
        if len(destinations) > 1:
            continue
        combined.sort(key=lambda item: _source_priority(item.get("source", "")))
        primary_identity = _identity(combined[0], pluto=combined[0].get("is_pluto", False))
        if not primary_identity:
            primary_identity = "name:" + canonical_name
        for item in combined:
            item["identity"] = primary_identity
        for old_identity, _ in parts:
            candidate_groups.pop(old_identity, None)
        candidate_groups[primary_identity] = combined

    candidate_name_counts = Counter()
    for group in candidate_groups.values():
        item = group[0]
        name = ap.normalizar(
            _attr(item.get("extinf", ""), "tvg-name") or item.get("nombre", "")
        )
        if name:
            candidate_name_counts[name] += 1

    main_name_counts = Counter({
        name: len(indexes) for name, indexes in main_by_name.items()
    })
    stats = {
        "canales_nuevos": 0,
        "url_actualizadas": 0,
        "categorias_movidas": chichicasteca_moved,
        "metadatos_actualizados": 0,
        "ambiguos": 0,
        "sin_categoria": len(candidates) - len(valid_candidates),
        "candidatos_validos_por_fuente": dict(sorted(valid_by_source.items())),
        "sin_categoria_por_fuente": dict(sorted(skipped_by_source.items())),
        "pitufos_omitidos_por_fuente": dict(sorted(pitufos_by_source.items())),
        "fuentes_propietarias": 0,
        "los_pitufos_eliminados": pitufos_removed,
        "pluto_es_anime_eliminados": pluto_es_anime_removed,
        "canales_chichicasteca_a_guatemala": chichicasteca_moved,
    }
    updated_indices: set[int] = set()
    reserved_urls = set(main_by_url)
    additions_by_category: dict[str, list[dict]] = defaultdict(list)

    for identity, group in candidate_groups.items():
        first = group[0]
        source_name = ap.normalizar(
            _attr(first.get("extinf", ""), "tvg-name") or first.get("nombre", "")
        )
        match = None
        if identity.startswith("id:"):
            matches = main_by_id.get(identity, [])
            if matches:
                match = next((idx for idx in matches if idx not in updated_indices), matches[0])
        if match is None:
            exact_matches = [
                main_by_url[item["url"].strip()]
                for item in group
                if item["url"].strip() in main_by_url
            ]
            if exact_matches:
                match = exact_matches[0]
        if match is None:
            canonical_name = _canonical_channel_name(first)
            canonical_matches = main_by_canonical_name.get(canonical_name, [])
            canonical_categories = {
                _canonical_category(ap.extraer_categoria(blocks[index]["extinf"]))
                for index in canonical_matches
            }
            canonical_ids = {
                _attr(blocks[index]["extinf"], "tvg-id")
                for index in canonical_matches
                if _attr(blocks[index]["extinf"], "tvg-id")
            }
            if canonical_matches and len(canonical_categories) == 1 and len(canonical_ids) <= 1:
                match = canonical_matches[0]
            elif canonical_matches:
                stats["ambiguos"] += 1
                continue
        if match is None and source_name:
            if candidate_name_counts[source_name] == 1 and main_name_counts[source_name] == 1:
                match = main_by_name[source_name][0]
            elif candidate_name_counts[source_name] > 1 or main_name_counts[source_name] > 1:
                stats["ambiguos"] += 1
                continue

        if match is not None and match in updated_indices:
            stats["ambiguos"] += 1
            continue

        owner_record = manifest.get(identity, {})
        owner_source = owner_record.get("source") if isinstance(owner_record, dict) else None
        selected = None
        if owner_source:
            selected = next((item for item in group if item.get("source") == owner_source), None)
            # Excepción explícita: si la fuente propietaria es Pluto ES y su
            # variante está en Anime, LATAM/MX pueden sustituirla. España no
            # alimenta Anime; las versiones LATAM/MX sí.
            if selected is None and identity in pluto_es_anime_ids and group:
                selected = group[0]
                manifest[identity] = {"source": selected["source"]}
            # En cualquier otra ausencia temporal se conserva la entrada y
            # no se permite que otra fuente se apropie del canal.
            if selected is None:
                continue
        elif match is not None:
            old_url = blocks[match]["url"]
            exact = [item for item in group if item["url"].strip() == old_url]
            if len(exact) == 1:
                selected = exact[0]
            else:
                old_category = ap.normalizar(ap.extraer_categoria(blocks[match]["extinf"]))
                same_category = [
                    item for item in group
                    if ap.normalizar(item["destination"]) == old_category
                ]
                if len(same_category) == 1:
                    selected = same_category[0]
                elif len(group) == 1:
                    selected = group[0]
                elif identity.startswith("id:"):
                    selected = group[0]
                else:
                    stats["ambiguos"] += 1
                    continue
            manifest[identity] = {"source": selected["source"]}
        else:
            if identity.startswith("name:") and len(group) > 1:
                stats["ambiguos"] += 1
                continue
            selected = group[0]
            manifest[identity] = {"source": selected["source"]}

        if selected is None:
            continue
        stats["fuentes_propietarias"] += 1
        source_url = selected["url"].strip()

        if match is not None:
            canonical_name = _canonical_channel_name(first)
            canonical_related = main_by_canonical_name.get(canonical_name, [])
            canonical_categories = {
                _canonical_category(ap.extraer_categoria(blocks[index]["extinf"]))
                for index in canonical_related
            }
            id_related = list(main_by_id.get(identity, [])) if identity.startswith("id:") else []
            canonical_ids = {
                _attr(blocks[index]["extinf"], "tvg-id")
                for index in canonical_related
                if _attr(blocks[index]["extinf"], "tvg-id")
            }
            if id_related:
                related_matches = id_related
            elif canonical_related and len(canonical_categories) == 1 and len(canonical_ids) <= 1:
                related_matches = list(canonical_related)
            else:
                related_matches = [match]
            if match not in related_matches:
                related_matches.append(match)
            occupied_by = main_by_url.get(source_url)
            if occupied_by is not None and occupied_by not in related_matches:
                stats["ambiguos"] += 1
                continue

            # Si la URL nueva ya existe como alternativa del mismo canal,
            # esa entrada pasa a ser la principal; las otras alternativas
            # permanecen, pero todas adoptan la categoría fuente.
            primary_match = next(
                (idx for idx in related_matches if blocks[idx]["url"] == source_url),
                match,
            )
            for idx in related_matches:
                block = blocks[idx]
                old_url = block["url"]
                old_category = ap.extraer_categoria(block["extinf"])
                destination = selected["destination"]
                merged = _merge_extinf(
                    block["extinf"],
                    selected.get("extinf", ""),
                    destination,
                )
                if idx == primary_match and old_url != source_url:
                    block["url"] = source_url
                    main_by_url.pop(old_url, None)
                    main_by_url[source_url] = idx
                    reserved_urls.add(source_url)
                    stats["url_actualizadas"] += 1
                if ap.normalizar(old_category) != ap.normalizar(destination):
                    stats["categorias_movidas"] += 1
                if merged != block["extinf"]:
                    stats["metadatos_actualizados"] += 1
                block["extinf"] = merged
                block["raw"] = [merged] + block["extras"] + [block["url"]]
            updated_indices.update(related_matches)

            # Incorporar cada URL alternativa válida del mismo canal. No se
            # incrusta el nombre de la fuente: la numeración se aplica después
            # sobre el conjunto completo de opciones.
            existing_related_urls = {blocks[idx]["url"] for idx in related_matches}
            for alternative in group:
                alternative_url = alternative["url"].strip()
                if not alternative_url or alternative_url in existing_related_urls or alternative_url in reserved_urls:
                    continue
                alternative_extinf = _merge_alternative_extinf(
                    blocks[primary_match]["extinf"],
                    alternative.get("extinf", ""),
                    selected["destination"],
                )
                additions_by_category[ap.normalizar(selected["destination"])].append({
                    "extinf": alternative_extinf,
                    "extras": list(alternative.get("extras", [])),
                    "url": alternative_url,
                    "raw": [alternative_extinf] + list(alternative.get("extras", [])) + [alternative_url],
                })
                existing_related_urls.add(alternative_url)
                reserved_urls.add(alternative_url)
                stats["alternativas_agregadas"] = stats.get("alternativas_agregadas", 0) + 1
            continue

        if source_url in reserved_urls:
            continue
        reserved_urls.add(source_url)
        extinf = _merge_extinf(
            selected.get("extinf", ""),
            selected.get("extinf", ""),
            selected["destination"],
        )
        additions_by_category[ap.normalizar(selected["destination"])].append({
            "extinf": extinf,
            "extras": list(selected.get("extras", [])),
            "url": source_url,
            "raw": [extinf] + list(selected.get("extras", [])) + [source_url],
        })
        stats["canales_nuevos"] += 1

        # Un canal nuevo puede llegar desde varias fuentes o con varias URLs.
        # Añadimos todas las alternativas sin repetir la URL principal.
        for alternative in group:
            alternative_url = alternative["url"].strip()
            if not alternative_url or alternative_url == source_url or alternative_url in reserved_urls:
                continue
            alternative_extinf = _merge_alternative_extinf(
                extinf,
                alternative.get("extinf", ""),
                selected["destination"],
            )
            additions_by_category[ap.normalizar(selected["destination"])].append({
                "extinf": alternative_extinf,
                "extras": list(alternative.get("extras", [])),
                "url": alternative_url,
                "raw": [alternative_extinf] + list(alternative.get("extras", [])) + [alternative_url],
            })
            reserved_urls.add(alternative_url)
            stats["alternativas_agregadas"] = stats.get("alternativas_agregadas", 0) + 1

    # Se conserva el orden relativo histórico, pero las alternativas de cada
    # canal se reúnen y numeran consecutivamente como pidió el usuario.
    output = list(prefix)
    for block in blocks:
        output.extend(
            block.get("raw")
            or ([block["extinf"]] + block["extras"] + ([block["url"]] if block.get("url") else []))
        )
    for new_blocks in additions_by_category.values():
        for block in new_blocks:
            output.extend(
                block.get("raw")
                or ([block["extinf"]] + block["extras"] + ([block["url"]] if block.get("url") else []))
            )
    output.extend(trailing)
    url_priority = {
        item["url"].strip(): _source_priority(item.get("source", ""))
        for item in candidates
        if item.get("url")
    }
    output = _group_and_label_alternatives(output, url_priority)
    output = _prioritize_infantiles(output)
    return output, stats


def synchronize_once() -> dict:
    if not PRINCIPAL.is_file() or not PRINCIPAL.stat().st_size:
        raise RuntimeError(f"No existe una playlist principal válida: {PRINCIPAL}")
    session = requests.Session()
    session.headers.update({"User-Agent": "IPTV-Chile-Master/1.1 (+source-sync)"})
    candidates, source_stats = collect_candidates(session)
    global LAST_URL_PRIORITY
    LAST_URL_PRIORITY = {
        candidate["url"]: _source_priority(candidate.get("source", ""))
        for candidate in candidates
        if candidate.get("url")
    }

    original_bytes = PRINCIPAL.read_bytes()
    original = original_bytes.decode("utf-8-sig", errors="replace").splitlines()
    manifest_original = MANIFEST.read_bytes() if MANIFEST.exists() else None
    if manifest_original:
        try:
            manifest_data = json.loads(manifest_original.decode("utf-8"))
            manifest = manifest_data.get("channels", {})
            if not isinstance(manifest, dict):
                raise ValueError("channels no es un objeto")
        except Exception as exc:
            raise RuntimeError(
                f"Manifiesto de propiedad inválido; se cancela la sincronización segura: {exc}"
            ) from exc
    else:
        manifest = {}

    updated, changes = reconcile_lines(original, candidates, manifest)
    text = "\n".join(updated).rstrip("\n") + "\n"
    if not text.startswith("#EXTM3U\n") or not any(line.startswith("#EXTINF:") for line in updated):
        raise RuntimeError("La sincronización produjo una M3U inválida; se conserva el archivo original.")

    manifest_text = json.dumps(
        {"version": 1, "channels": manifest},
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temp_playlist = PRINCIPAL.with_name(PRINCIPAL.name + ".sync.tmp")
    temp_manifest = MANIFEST.with_name(MANIFEST.name + ".sync.tmp")
    try:
        temp_playlist.write_text(text, encoding="utf-8", newline="\n")
        temp_manifest.write_text(manifest_text, encoding="utf-8", newline="\n")

        staged = temp_playlist.read_text(encoding="utf-8")
        if not staged.startswith("#EXTM3U\n") or not any(
            line.startswith("#EXTINF:") for line in staged.splitlines()
        ):
            raise RuntimeError("Validación temporal de M3U fallida.")
        staged_manifest = json.loads(temp_manifest.read_text(encoding="utf-8"))
        if staged_manifest.get("version") != 1 or not isinstance(staged_manifest.get("channels"), dict):
            raise RuntimeError("Validación temporal del manifiesto fallida.")

        # Publicar los dos artefactos como una operación recuperable.
        temp_playlist.replace(PRINCIPAL)
        temp_manifest.replace(MANIFEST)
    except Exception:
        temp_playlist.unlink(missing_ok=True)
        temp_manifest.unlink(missing_ok=True)
        if PRINCIPAL.exists() and PRINCIPAL.read_bytes() != original_bytes:
            restore = PRINCIPAL.with_name(PRINCIPAL.name + ".sync.restore")
            restore.write_bytes(original_bytes)
            restore.replace(PRINCIPAL)
        if manifest_original is None:
            MANIFEST.unlink(missing_ok=True)
        elif not MANIFEST.exists() or MANIFEST.read_bytes() != manifest_original:
            restore_manifest = MANIFEST.with_name(MANIFEST.name + ".sync.restore")
            restore_manifest.write_bytes(manifest_original)
            restore_manifest.replace(MANIFEST)
        raise
    return {**source_stats, **changes}


def main() -> None:
    result = synchronize_once()
    print("\n========== SINCRONIZACIÓN UNIFICADA ==========")
    for key, value in result.items():
        print(f"{key}: {value}")
    print("OK: todas las fuentes complementarias fueron reconciliadas sin borrar canales ausentes.")


if __name__ == "__main__":
    main()

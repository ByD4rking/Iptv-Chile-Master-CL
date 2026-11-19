#!/usr/bin/env python3
"""Blindajes terminales de identidad de logos, Anime y orden global de categorías."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from collections import defaultdict


_ATTRS = ("tvg-logo", "logo")
LOGOS_AUTORIZADOS_PATH = Path(__file__).resolve().parents[1] / "config" / "logos_autorizados.json"

# Únicas excepciones autorizadas por el usuario para cambiar logos existentes.
LOGOS_AUTORIZADOS_POR_NOMBRE = {
    "TVN HD (LOCAL)": "https://i.imgur.com/3FKZHL4.png",
    "TV Chile (1080p) [Geo-blocked]": "https://i.imgur.com/3FKZHL4.png",
}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    # [Geo-blocked] es metadato, no parte de la identidad del canal.
    return re.sub(r"\s+geo blocked$", "", value)


def _cargar_logos_autorizados():
    """Carga excepciones manuales desde config; ante errores, detiene el proceso."""
    autorizados = {
        _norm(nombre): url
        for nombre, url in LOGOS_AUTORIZADOS_POR_NOMBRE.items()
    }
    if not LOGOS_AUTORIZADOS_PATH.is_file():
        return autorizados
    try:
        data = json.loads(LOGOS_AUTORIZADOS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("No se pudo leer " + str(LOGOS_AUTORIZADOS_PATH) + ": " + str(error)) from error
    if not isinstance(data, dict):
        raise RuntimeError("config/logos_autorizados.json debe contener un objeto JSON.")
    logos = data.get("logos", {})
    if not isinstance(logos, dict):
        raise RuntimeError("config/logos_autorizados.json: 'logos' debe ser un objeto.")
    for identidad, url in logos.items():
        identidad = str(identidad).strip()
        url = str(url).strip()
        if not identidad or not re.match(r"^https?://\S+$", url, re.I):
            raise RuntimeError("Override de logo inválido para " + repr(identidad) + ": se requiere una URL HTTP(S).")
        autorizados[_norm(identidad)] = url
    return autorizados


def _buscar_logo_autorizado(record, autorizados):
    """Prioriza identidad categoría::canal; permite nombre simple como alias global."""
    nombres = (record.get("name", ""), record.get("tvg_name", ""))
    if record.get("category_key"):
        for nombre in nombres:
            if nombre:
                clave = _norm(record["category_key"] + "::" + nombre)
                if clave in autorizados:
                    return autorizados[clave]
    for nombre in nombres:
        if nombre and _norm(nombre) in autorizados:
            return autorizados[_norm(nombre)]
    return None



def _attr(line: str, name: str) -> str:
    match = re.search(r"(?<![\w-])" + re.escape(name) + r'="([^"]*)"', line, re.I)
    return match.group(1).strip() if match else ""


def _set_attr(line: str, name: str, value: str) -> str:
    pattern = r"(?<![\w-])" + re.escape(name) + r'="[^"]*"'
    if value:
        replacement = f'{name}="{value}"'
        if re.search(pattern, line, re.I):
            return re.sub(pattern, lambda _: replacement, line, count=1, flags=re.I)
        comma = line.find(",")
        return line[:comma].rstrip() + " " + replacement + line[comma:] if comma >= 0 else line
    return re.sub(r"\s+" + pattern, "", line, count=1, flags=re.I)


def _split_blocks(lines):
    prefix, blocks = [], []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("#EXTINF"):
            if blocks:
                blocks[-1]["lines"].append(lines[index])
            else:
                prefix.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not lines[end].startswith("#EXTINF"):
            end += 1
        raw = list(lines[index:end])
        extinf = raw[0]
        category = _attr(extinf, "group-title")
        display_name = extinf.split(",", 1)[1].strip() if "," in extinf else ""
        tvg_name = _attr(extinf, "tvg-name")
        channel_id = _attr(extinf, "channelId")
        tvg_id = _attr(extinf, "tvg-id")
        url = next(
            (item.strip() for item in raw[1:] if item.strip().lower().startswith(("http://", "https://"))),
            "",
        )
        blocks.append({
            "lines": raw,
            "start": index,
            "category": category,
            "category_key": _norm(category),
            "name": _norm(display_name),
            "tvg_name": _norm(tvg_name),
            "channel_id": _norm(channel_id),
            "id": _norm(tvg_id),
            "url": url,
        })
        index = end
    return prefix, blocks


def _identity_keys(record):
    keys = []
    if record["url"]:
        keys.append(("url", record["url"]))
    if record.get("channel_id"):
        keys.append(("channel_id", record["channel_id"]))
    if record["id"]:
        keys.append(("id", record["id"]))
    if record["category_key"] and record["name"]:
        keys.append(("category_name", record["category_key"], record["name"]))
    if record["tvg_name"]:
        keys.append(("tvg_name", record["tvg_name"]))
    return keys


def blindar_logos(lineas, referencia):
    """Conserva los dos atributos de logo de cada canal existente.

    La identidad se resuelve por URL, tvg-id, categoría/nombre, tvg-name y
    nombre. Los logos de canales nuevos se retiran: no se heredan desde fuentes.
    """
    _, original_blocks = _split_blocks(referencia)
    _, current_blocks = _split_blocks(lineas)

    candidates = defaultdict(set)
    for record in original_blocks:
        metadata = tuple(_attr(record["lines"][0], name) for name in _ATTRS)
        for key in _identity_keys(record):
            candidates[key].add(metadata)

    frozen = {
        key: next(iter(values))
        for key, values in candidates.items()
        if len(values) == 1
    }

    output = list(lineas)
    preserved = 0
    stripped_new = 0
    unmatched = []
    authorized = _cargar_logos_autorizados()
    authorized_count = 0
    for record in current_blocks:
        match = next((frozen[key] for key in _identity_keys(record) if key in frozen), None)
        extinf = output[record["start"]]
        override = _buscar_logo_autorizado(record, authorized)
        if override:
            # Una autorización manual explícita prevalece sobre el logo histórico.
            previous_legacy = match[1] if match else ""
            values = (override, override if previous_legacy else "")
            authorized_count += 1
        elif match is None:
            values = ("", "")
            unmatched.append(record["name"] or "(sin nombre)")
            if any(_attr(extinf, name) for name in _ATTRS):
                stripped_new += 1
        else:
            values = match
            if any(_attr(extinf, name) != value for name, value in zip(_ATTRS, values)):
                preserved += 1
        for name, value in zip(_ATTRS, values):
            extinf = _set_attr(extinf, name, value)
        # Se usa el índice original del bloque: puede haber EXTINF idénticos.
        output[record["start"]] = extinf

    return output, {
        "logos_restaurados": preserved,
        "logos_fuente_retirados": stripped_new,
        "logos_autorizados": authorized_count,
        "canales_sin_identidad_historica": len(unmatched),
    }



def validar_logos_chile_tv(lineas, referencia):
    """Falla si un logo histórico de CHILE TV cambia o si una señal nueva trae uno no autorizado."""
    _, original_blocks = _split_blocks(referencia)
    _, current_blocks = _split_blocks(lineas)
    target = _norm("CHILE TV")

    candidates = defaultdict(set)
    for record in original_blocks:
        if record["category_key"] != target:
            continue
        metadata = tuple(_attr(record["lines"][0], name) for name in _ATTRS)
        for key in _identity_keys(record):
            candidates[key].add(metadata)

    frozen = {
        key: next(iter(values))
        for key, values in candidates.items()
        if len(values) == 1
    }

    authorized = _cargar_logos_autorizados()
    for record in current_blocks:
        if record["category_key"] != target:
            continue
        actual = tuple(_attr(record["lines"][0], name) for name in _ATTRS)
        match = next((frozen[key] for key in _identity_keys(record) if key in frozen), None)
        override = _buscar_logo_autorizado(record, authorized)
        if override:
            expected = (override, override if match and match[1] else "")
            allowed = {expected}
            # Una señal nueva puede llegar con ambos atributos de logo iguales.
            # Si el segundo atributo coincide exactamente con el override
            # explícito, se conserva; cualquier URL distinta sigue bloqueada.
            if not match or not match[1]:
                allowed.add((override, override))
            if actual not in allowed:
                name = record["name"] or record["tvg_name"] or "(sin nombre)"
                raise AssertionError(
                    "Logo manual autorizado incorrecto en CHILE TV: " + name
                    + "; esperado=" + repr(sorted(allowed)) + ", actual=" + repr(actual)
                )
            continue
        if match is None:
            if any(actual):
                name = record["name"] or record["tvg_name"] or "(sin nombre)"
                raise AssertionError(
                    f"Logo no autorizado en señal nueva de CHILE TV: {name}"
                )
            continue
        if actual != match:
            name = record["name"] or record["tvg_name"] or "(sin nombre)"
            raise AssertionError(
                f"Logo alterado en CHILE TV: {name}; esperado={match!r}, actual={actual!r}"
            )
    return True


def restaurar_categoria_bloqueada(lineas, referencia, categoria="Anime"):
    """Restaura literalmente todos los bloques de una categoría protegida."""
    prefix, current = _split_blocks(lineas)
    _, original = _split_blocks(referencia)
    target = _norm(categoria)
    locked = [record for record in original if record["category_key"] == target]
    if not locked:
        return list(lineas)
    current_indexes = [
        index for index, record in enumerate(current)
        if record["category_key"] == target
    ]
    insertion = min(current_indexes) if current_indexes else len(current)
    remaining = [
        record for record in current
        if record["category_key"] != target
    ]
    insertion = min(insertion, len(remaining))
    restored = remaining[:insertion] + locked + remaining[insertion:]
    output = list(prefix)
    for record in restored:
        output.extend(record["lines"])
    return output


def priorizar_history_documentales(lineas):
    """Mueve History y luego History 2 al inicio de Documentales y Cultura.

    Conserva el orden original dentro de cada familia y el orden relativo
    de todos los demás canales y categorías.
    """
    prefix, blocks = _split_blocks(lineas)
    target = _norm("Documentales y Cultura")
    category_records = [record for record in blocks if record["category_key"] == target]
    if not category_records:
        return list(lineas)

    def is_history2(record):
        names = (record["name"], record["tvg_name"])
        return any(
            re.match(r"^(?:history\s*2|h\s*2)(?:\s|$)", name)
            for name in names if name
        )

    def is_history(record):
        names = (record["name"], record["tvg_name"])
        return any(name.startswith("history") for name in names if name) and not is_history2(record)

    history = [record for record in category_records if is_history(record)]
    history2 = [record for record in category_records if is_history2(record)]
    prioritized_ids = {id(record) for record in history + history2}
    if not prioritized_ids:
        return list(lineas)

    reordered = history + history2 + [
        record for record in category_records if id(record) not in prioritized_ids
    ]
    output = list(prefix)
    inserted = False
    for record in blocks:
        if record["category_key"] == target:
            if not inserted:
                for prioritized in reordered:
                    output.extend(prioritized["lines"])
                inserted = True
            continue
        output.extend(record["lines"])
    return output


def validar_prioridad_history_documentales(lineas):
    """Verifica que todas las señales History y H2 estén antes del resto."""
    expected = priorizar_history_documentales(lineas)
    if expected != list(lineas):
        raise AssertionError(
            "History y History 2/H2 no están completos y agrupados al inicio "
            "de Documentales y Cultura."
        )
    return True


def validar_logos_tvn_autorizados(lineas):
    """Exige los dos logos TVN autorizados en sus canales exactos."""
    authorized = {_norm(name): logo for name, logo in LOGOS_AUTORIZADOS_POR_NOMBRE.items()}
    found = set()
    for record in _split_blocks(lineas)[1]:
        names = {record["name"], record["tvg_name"]}
        matched = next((name for name in names if name in authorized), None)
        if matched is None:
            continue
        logo = _attr(record["lines"][0], "tvg-logo")
        if logo != authorized[matched]:
            raise AssertionError(
                f"Logo incorrecto en {matched}: esperado={authorized[matched]!r}, actual={logo!r}"
            )
        found.add(matched)
    missing = set(authorized) - found
    if missing:
        raise AssertionError(
            "No se encontraron las dos señales TVN autorizadas en la principal: "
            + ", ".join(sorted(missing))
        )
    return True


def ordenar_categorias_definitivo(lineas):
    """Aplica el orden global acordado sin reordenar canales dentro de cada carpeta."""
    from alimentar_principal import PAISES_ORDEN_FINAL, CATEGORIAS_PAIS, PAIS_POR_FUENTE

    priority = [
        "CHILE TV",
        "Anime",
        "Competencia",
        "Infantiles",
        "Entretenimiento / Cine / Series",
        "Cine / Películas",
        "Entretenimiento Premium",
        "Cine / Películas Premium",
        "Documentales y Cultura",
        "Doramas",
        "Comedia",
        "South Park",
        "Reality",
        "Retro",
        "Series",
        "Informativos",
    ]
    priority_index = {_norm(name): index for index, name in enumerate(priority)}
    countries = {_norm(name) for name in PAISES_ORDEN_FINAL}
    countries.update(_norm(name) for name in CATEGORIAS_PAIS.values())
    countries.update(
        _norm(name) for name in PAIS_POR_FUENTE.values()
        if _norm(name) not in {"religiosos", "musica", "latam"}
    )

    prefix, blocks = _split_blocks(lineas)
    grouped = {}
    order = []
    for record in blocks:
        key = record["category_key"]
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(record)

    def sort_key(key):
        if key in priority_index:
            return (0, priority_index[key], order.index(key))
        if key in countries or key.startswith("el salvador"):
            return (2, order.index(key), key)
        return (1, order.index(key), key)

    sorted_keys = sorted(order, key=sort_key)
    output = list(prefix)
    for key in sorted_keys:
        for record in grouped[key]:
            output.extend(record["lines"])
    return output


def validar_orden_categorias(lineas):
    """Falla si el orden publicado no coincide con el orden global definitivo."""
    expected = ordenar_categorias_definitivo(lineas)
    if expected != list(lineas):
        raise AssertionError("El orden global de categorías no respeta el blindaje definitivo.")
    return True

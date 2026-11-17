#!/usr/bin/env python3
"""Blindajes terminales de identidad de logos, Anime y orden global de categorías."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict


_ATTRS = ("tvg-logo", "logo")


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


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
        channel_id = _attr(extinf, "tvg-id")
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
            "id": _norm(channel_id),
            "url": url,
        })
        index = end
    return prefix, blocks


def _identity_keys(record):
    keys = []
    if record["url"]:
        keys.append(("url", record["url"]))
    if record["id"]:
        keys.append(("id", record["id"]))
    if record["category_key"] and record["name"]:
        keys.append(("category_name", record["category_key"], record["name"]))
    if record["tvg_name"]:
        keys.append(("tvg_name", record["tvg_name"]))
    if record["name"]:
        keys.append(("name", record["name"]))
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
    for record in current_blocks:
        match = next((frozen[key] for key in _identity_keys(record) if key in frozen), None)
        extinf = output[record["start"]]
        if match is None:
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
        "canales_sin_identidad_historica": len(unmatched),
    }


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

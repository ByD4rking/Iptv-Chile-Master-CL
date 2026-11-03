#!/usr/bin/env python3
"""Sincronización incremental común de todas las fuentes complementarias.

No elimina canales por ausencia en una fuente. La identidad estable (tvg-id,
o nombre inequívoco como respaldo) permite actualizar URL y categoría aunque
la URL anterior haya cambiado.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import requests

import alimentar_principal as ap

BASE = Path(__file__).resolve().parent.parent
PRINCIPAL = BASE / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
TIMEOUT = 30

# Todas las regiones Pluto son complementarias de la principal. LATAM tiene
# prioridad cuando el mismo ID aparece en más de una región.
FUENTES_PLUTO_COMPLETAS = [
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_latam.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_es.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_mx.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_cl.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_ar.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_br.m3u",
    "https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_us.m3u",
]


def _attr(text: str, name: str) -> str:
    match = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', text or "", re.I)
    return match.group(1).strip() if match else ""


def _identity(channel: dict, *, pluto: bool = False) -> str:
    extinf = channel.get("extinf", "")
    channel_id = _attr(extinf, "tvg-id")
    if not channel_id and pluto:
        channel_id = ap.extraer_pluto_id(channel.get("url", ""))
    if channel_id:
        return "id:" + ap.normalizar(channel_id)
    name = ap.normalizar(_attr(extinf, "tvg-name") or channel.get("nombre", ""))
    return "name:" + name if name else ""


def _set_attr(extinf: str, key: str, value: str) -> str:
    if not value:
        return extinf
    pattern = r'\b' + re.escape(key) + r'="[^"]*"'
    replacement = f'{key}="{value}"'
    if re.search(pattern, extinf, re.I):
        return re.sub(pattern, lambda _: replacement, extinf, count=1, flags=re.I)
    comma = extinf.find(",")
    if comma < 0:
        return extinf
    return extinf[:comma].rstrip() + " " + replacement + extinf[comma:]


def _merge_extinf(current: str, source: str, destination: str) -> str:
    """Actualiza metadatos conocidos sin borrar atributos que la fuente omita."""
    result = current
    for key in ("tvg-id", "tvg-name", "tvg-logo", "tvg-language", "tvg-country", "tvg-chno"):
        value = _attr(source, key)
        if value:
            result = _set_attr(result, key, value)
    result = _set_attr(result, "group-title", destination)
    source_name = ap.extraer_nombre(source)
    if source_name:
        result = result.split(",", 1)[0] + "," + source_name
    return result


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


def _destination(source_url: str, channel: dict, categories: list[str]) -> str | None:
    category = (channel.get("categoria") or "").strip()
    name = channel.get("nombre", "")
    if not category:
        return None
    if source_url == ap.FUENTE_IPTVSV:
        if ap.es_categoria_pais_generica_iptvsv(category):
            return None
        return ap.determinar_destino_iptvsv(category, name, categories)
    if source_url == ap.FUENTE_MAGMA:
        return ap.determinar_destino_magma(category, name, categories)
    if source_url in FUENTES_PLUTO_COMPLETAS:
        if source_url.endswith("pluto_es.m3u") and ap.normalizar(category) == "anime":
            return None
        return ap.determinar_destino_pluto(category, name, categories)
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
    seen_identity: set[str] = set()

    for source_url in ordered:
        try:
            response = session.get(source_url, timeout=TIMEOUT)
            response.raise_for_status()
            body = response.text or ""
            if not body.lstrip("\\ufeff \\r\\n\\t").startswith("#EXTM3U"):
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
            url = (channel.get("url") or "").strip()
            if not ap.url_es_valida(url):
                continue
            destination = _destination(source_url, channel, [])
            # Se vuelve a resolver con las categorías reales en reconcile().
            candidate = dict(channel)
            candidate["source"] = source_url
            candidate["destination_hint"] = destination
            candidate["is_pluto"] = source_url in FUENTES_PLUTO_COMPLETAS
            identity = _identity(candidate, pluto=candidate["is_pluto"])
            if identity and identity in seen_identity:
                continue
            if identity:
                seen_identity.add(identity)
            candidate["identity"] = identity
            candidates.append(candidate)
            stats["canales_fuente"] += 1

    if not stats["fuentes_ok"]:
        raise RuntimeError("Ninguna fuente complementaria entregó una M3U válida; no se modifica la maestra.")
    return candidates, stats


def reconcile_lines(lines: list[str], candidates: list[dict]) -> tuple[list[str], dict]:
    """Agrega, actualiza URL/metadatos y reclasifica por identidad estable."""
    prefix, blocks, trailing = _read_blocks(lines)
    categories = ap.categorias_de_lineas(lines)
    category_lookup = {ap.normalizar(value): value for value in categories}

    # Recalcular destinos con el catálogo real de categorías de la maestra.
    valid_candidates = []
    for candidate in candidates:
        destination = _destination(
            candidate.get("source", ""),
            candidate,
            categories,
        )
        if not destination or ap.normalizar(destination) not in category_lookup:
            continue
        item = dict(candidate)
        item["destination"] = category_lookup[ap.normalizar(destination)]
        valid_candidates.append(item)

    main_by_id: dict[str, list[int]] = defaultdict(list)
    main_by_name: dict[str, list[int]] = defaultdict(list)
    main_by_url: dict[str, int] = {}
    for index, block in enumerate(blocks):
        if not block.get("url"):
            continue
        identity = _identity({
            "extinf": block["extinf"],
            "nombre": ap.extraer_nombre(block["extinf"]),
            "url": block["url"],
        }, pluto=ap.es_url_pluto(block["url"]))
        if identity.startswith("id:"):
            main_by_id[identity].append(index)
        main_by_url.setdefault(block["url"], index)
        name = ap.normalizar(_attr(block["extinf"], "tvg-name") or ap.extraer_nombre(block["extinf"]))
        if name:
            main_by_name[name].append(index)

    candidate_name_counts = Counter(
        ap.normalizar(_attr(item.get("extinf", ""), "tvg-name") or item.get("nombre", ""))
        for item in valid_candidates
        if ap.normalizar(_attr(item.get("extinf", ""), "tvg-name") or item.get("nombre", ""))
    )
    main_name_counts = Counter({
        name: len(indexes) for name, indexes in main_by_name.items()
    })

    stats = {
        "canales_nuevos": 0,
        "url_actualizadas": 0,
        "categorias_movidas": 0,
        "metadatos_actualizados": 0,
        "ambiguos": 0,
        "sin_categoria": len(candidates) - len(valid_candidates),
    }
    updated_indices: set[int] = set()
    added_identities: set[str] = set()
    processed_identities: set[str] = set()
    reserved_urls = set(main_by_url)
    additions_by_category: dict[str, list[dict]] = defaultdict(list)

    for candidate in valid_candidates:
        identity = candidate.get("identity") or _identity(
            candidate, pluto=candidate.get("is_pluto", False)
        )
        if identity and identity in processed_identities:
            continue
        if identity:
            processed_identities.add(identity)
        source_name = ap.normalizar(_attr(candidate.get("extinf", ""), "tvg-name") or candidate.get("nombre", ""))
        match = None
        if identity.startswith("id:"):
            matches = main_by_id.get(identity, [])
            if matches:
                match = next((idx for idx in matches if idx not in updated_indices), matches[0])
        source_url = candidate["url"].strip()
        if match is None:
            match = main_by_url.get(source_url)
        if match is None and source_name:
            if candidate_name_counts[source_name] == 1 and main_name_counts[source_name] == 1:
                match = main_by_name[source_name][0]
            elif candidate_name_counts[source_name] > 1 or main_name_counts[source_name] > 1:
                stats["ambiguos"] += 1

        if match is not None:
            block = blocks[match]
            old_url = block["url"]
            new_url = source_url
            destination = candidate["destination"]
            occupied_by = main_by_url.get(new_url)
            if occupied_by is not None and occupied_by != match:
                stats["ambiguos"] += 1
                continue
            old_category = ap.extraer_categoria(block["extinf"])
            merged = _merge_extinf(block["extinf"], candidate.get("extinf", ""), destination)
            if old_url != new_url:
                block["url"] = new_url
                main_by_url.pop(old_url, None)
                main_by_url[new_url] = match
                reserved_urls.add(new_url)
                stats["url_actualizadas"] += 1
            if ap.normalizar(old_category) != ap.normalizar(destination):
                stats["categorias_movidas"] += 1
            if merged != block["extinf"]:
                stats["metadatos_actualizados"] += 1
            block["extinf"] = merged
            block["raw"] = [merged] + block["extras"] + [block["url"]]
            updated_indices.add(match)
            continue

        if source_url in reserved_urls:
            continue
        if identity and identity in added_identities:
            continue
        if identity:
            added_identities.add(identity)
        reserved_urls.add(source_url)
        extinf = _merge_extinf(candidate.get("extinf", ""), candidate.get("extinf", ""), candidate["destination"])
        additions_by_category[ap.normalizar(candidate["destination"])].append({
            "extinf": extinf,
            "extras": list(candidate.get("extras", [])),
            "url": candidate["url"].strip(),
            "raw": [extinf] + list(candidate.get("extras", [])) + [candidate["url"].strip()],
        })
        stats["canales_nuevos"] += 1

    # Reagrupar físicamente por categoría: los canales movidos quedan dentro
    # de su sección. Se conserva el orden de categorías y el orden interno.
    grouped: dict[str, list[dict]] = {}
    category_order: list[str] = []
    for block in blocks:
        category = ap.normalizar(ap.extraer_categoria(block["extinf"]))
        if category not in grouped:
            grouped[category] = []
            category_order.append(category)
        grouped[category].append(block)

    for category, new_blocks in additions_by_category.items():
        if category not in grouped:
            continue
        grouped[category].extend(new_blocks)

    output = list(prefix)
    for category in category_order:
        for block in grouped[category]:
            output.extend(block.get("raw") or ([block["extinf"]] + block["extras"] + ([block["url"]] if block.get("url") else [])))
    output.extend(trailing)
    return output, stats


def synchronize_once() -> dict:
    if not PRINCIPAL.is_file() or not PRINCIPAL.stat().st_size:
        raise RuntimeError(f"No existe una playlist principal válida: {PRINCIPAL}")
    session = requests.Session()
    session.headers.update({"User-Agent": "IPTV-Chile-Master/1.1 (+source-sync)"})
    candidates, source_stats = collect_candidates(session)
    original_bytes = PRINCIPAL.read_bytes()
    original = original_bytes.decode("utf-8-sig", errors="replace").splitlines()
    updated, changes = reconcile_lines(original, candidates)
    text = "\n".join(updated).rstrip("\n") + "\n"
    if not text.startswith("#EXTM3U\n") or not any(line.startswith("#EXTINF:") for line in updated):
        raise RuntimeError("La sincronización produjo una M3U inválida; se conserva el archivo original.")
    temp = PRINCIPAL.with_name(PRINCIPAL.name + ".sync.tmp")
    try:
        temp.write_text(text, encoding="utf-8", newline="\n")
        staged = temp.read_text(encoding="utf-8")
        if not staged.startswith("#EXTM3U\n") or staged.count("#EXTINF:") != sum(
            1 for line in staged.splitlines() if line.startswith("#EXTINF:")
        ):
            raise RuntimeError("Validación temporal de M3U fallida.")
        temp.replace(PRINCIPAL)
    except Exception:
        temp.unlink(missing_ok=True)
        # La ruta principal solo se reemplaza después de validar el temporal.
        if PRINCIPAL.exists() and PRINCIPAL.read_bytes() != original_bytes:
            restore = PRINCIPAL.with_name(PRINCIPAL.name + ".sync.restore")
            restore.write_bytes(original_bytes)
            restore.replace(PRINCIPAL)
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

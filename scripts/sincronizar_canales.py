from __future__ import annotations

import re
from collections import defaultdict
from typing import Callable


def sincronizar_enlaces_existentes(
    lineas: list[str],
    canales_destinados: list[tuple[dict, str]],
    *,
    normalizar: Callable[[str], str],
    extraer_nombre: Callable[[str], str],
    extraer_categoria: Callable[[str], str],
    reemplazar_categoria: Callable[[str, str], str],
    url_es_valida: Callable[[str], bool],
) -> tuple[list[str], dict[str, int]]:
    """Actualiza bloques existentes por ID estable o nombre inequívoco.

    Dos IDs distintos nunca se fusionan por compartir nombre. El fallback por
    nombre solo se permite si hay una única coincidencia en la misma categoría
    y al menos una de las versiones carece de tvg-id.
    """
    stats = {
        "urls_actualizadas": 0,
        "nombres_actualizados": 0,
        "categorias_actualizadas": 0,
    }
    if not canales_destinados:
        return lineas, stats

    def source_id(canal: dict) -> str:
        extinf = str(canal.get("extinf") or "")
        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        return normalizar(match.group(1)) if match and match.group(1).strip() else ""

    def source_name(canal: dict) -> str:
        return normalizar(canal.get("nombre") or canal.get("tvg_name") or "")

    def source_display_name(canal: dict) -> str:
        return str(canal.get("nombre") or canal.get("tvg_name") or "").strip()

    sources_by_id: dict[str, list[dict]] = defaultdict(list)
    sources_by_name: dict[tuple[str, str], list[dict]] = defaultdict(list)
    sources_by_url: dict[str, list[dict]] = defaultdict(list)
    for canal, destino in canales_destinados:
        item = {"canal": canal, "destino": destino}
        cid = source_id(canal)
        name = source_name(canal)
        if cid:
            sources_by_id[cid].append(item)
        url = str(canal.get("url") or "").strip()
        if url:
            sources_by_url[url].append(item)
        if name and destino:
            sources_by_name[(normalizar(destino), name)].append(item)

    existing_by_name: dict[tuple[str, str], list[dict]] = defaultdict(list)
    blocks = []
    present_urls = set()
    url_counts: dict[str, int] = defaultdict(int)
    i = 0
    while i < len(lineas):
        if not lineas[i].startswith("#EXTINF"):
            i += 1
            continue
        extinf = lineas[i]
        j = i + 1
        while j < len(lineas) and lineas[j].startswith("#") and not lineas[j].startswith("#EXTINF"):
            j += 1
        if j >= len(lineas) or not url_es_valida(lineas[j].strip()):
            i = max(i + 1, j)
            continue

        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        cid = normalizar(match.group(1)) if match and match.group(1).strip() else ""
        category = extraer_categoria(extinf)
        name = normalizar(extraer_nombre(extinf))
        url = lineas[j].strip()
        block = {
            "extinf_index": i,
            "url_index": j,
            "id": cid,
            "category": category,
            "name": name,
            "url": url,
        }
        blocks.append(block)
        existing_by_name[(normalizar(category), name)].append(block)
        present_urls.add(url)
        url_counts[url] += 1
        i = j + 1

    used_ids = set()
    for block in blocks:
        candidate = None
        same_id = False
        same_url = False

        # La URL exacta prevalece cuando cambia el nombre visible o falta tvg-id.
        url_candidates = sources_by_url.get(block["url"], [])
        if len(url_candidates) == 1:
            candidate = url_candidates[0]
            same_url = True

        if candidate is None and block["id"]:
            candidates = sources_by_id.get(block["id"], [])
            unique_urls = {
                str(item["canal"].get("url") or "").strip()
                for item in candidates
                if str(item["canal"].get("url") or "").strip()
            }
            if candidates and len(unique_urls) == 1 and block["id"] not in used_ids:
                candidate = candidates[0]
                same_id = True
                used_ids.add(block["id"])

        if candidate is None and block["name"]:
            key = (normalizar(block["category"]), block["name"])
            candidates = sources_by_name.get(key, [])
            old_matches = existing_by_name.get(key, [])
            source_id_url_pairs = {
                (source_id(item["canal"]), str(item["canal"].get("url") or "").strip())
                for item in candidates
            }
            if len(old_matches) == 1 and len(source_id_url_pairs) == 1:
                item = candidates[0]
                new_id = source_id(item["canal"])
                if not block["id"] or not new_id:
                    candidate = item

        if candidate is None:
            continue

        canal = candidate["canal"]
        new_url = str(canal.get("url") or "").strip()
        old_url = block["url"]
        if new_url and new_url != old_url and new_url not in present_urls:
            lineas[block["url_index"]] = new_url
            url_counts[old_url] -= 1
            if url_counts[old_url] <= 0:
                present_urls.discard(old_url)
            present_urls.add(new_url)
            url_counts[new_url] += 1
            stats["urls_actualizadas"] += 1

        if same_id or same_url:
            new_display_name = source_display_name(canal)
            current_extinf = lineas[block["extinf_index"]]
            current_name = extraer_nombre(current_extinf)
            actualizar_nombre = same_id
            if same_url and not same_id and new_display_name:
                # Por URL exacta solo reparamos una etiqueta de resolución perdida
                # (HD/SD/FHD/UHD); no renombramos masivamente canales homónimos.
                current_base = re.sub(r"\s*\[(?:opc(?:ión)?\.?\s*\d+|v\d+)\]$", "", current_name, flags=re.I).strip()
                source_resolution = re.search(r"\s+(?:HD|SD|FHD|UHD)$", new_display_name, re.I)
                source_base = re.sub(r"\s+(?:HD|SD|FHD|UHD)$", "", new_display_name, flags=re.I).strip()
                current_base = re.sub(r"\s+(?:HD|SD|FHD|UHD)$", "", current_base, flags=re.I).strip()
                actualizar_nombre = bool(source_resolution and normalizar(source_base) == normalizar(current_base))
            if actualizar_nombre and new_display_name and normalizar(new_display_name) != normalizar(current_name):
                option_suffix = re.search(
                    r"(\s*\[(?:opc(?:ión)?\.?\s*\d+|v\d+)\])$",
                    current_name,
                    re.I,
                )
                display = new_display_name
                if same_id and not same_url and option_suffix and option_suffix.group(1).lower() not in display.lower():
                    display += option_suffix.group(1)
                if "," in current_extinf:
                    current_extinf = current_extinf.rsplit(",", 1)[0] + "," + display
                source_tvg_name = re.search(
                    "tvg-name=\"([^\"]*)\"",
                    str(canal.get("extinf") or ""),
                    re.I,
                )
                tvg_name_value = source_tvg_name.group(1) if source_tvg_name else (new_display_name if same_url else "")
                if tvg_name_value:
                    if re.search("tvg-name=\"[^\"]*\"", current_extinf, re.I):
                        current_extinf = re.sub(
                            "tvg-name=\"[^\"]*\"",
                            "tvg-name=\"" + tvg_name_value + "\"",
                            current_extinf,
                            count=1,
                            flags=re.I,
                        )
                    else:
                        comma = current_extinf.find(",")
                        if comma >= 0:
                            current_extinf = current_extinf[:comma].rstrip() + " tvg-name=\"" + tvg_name_value + "\"" + current_extinf[comma:]
                lineas[block["extinf_index"]] = current_extinf
                stats["nombres_actualizados"] += 1

            destination = candidate["destino"]
            if destination and normalizar(destination) != normalizar(block["category"]):
                lineas[block["extinf_index"]] = reemplazar_categoria(
                    lineas[block["extinf_index"]],
                    destination,
                )
                stats["categorias_actualizadas"] += 1

    return lineas, stats

#!/usr/bin/env python3
"""Prueba end-to-end de la reconciliación real en el checkout de una PR.

Solo se ejecuta desde selftest_reconexion_principal.py cuando
GITHUB_EVENT_NAME=pull_request. Modifica el checkout temporal de Actions,
nunca publica ni hace push.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import requests

import alimentar_principal as ap
from sincronizar_complementos import synchronize_once


ROOT = Path(__file__).resolve().parents[1]
PRINCIPAL = ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"


def norm(value: str) -> str:
    return ap.normalizar(value or "")


def base_name(value: str) -> str:
    value = re.sub(
        r"\s*(?:\[\s*opc(?:ion)?\.?\s*\d+\s*\]|\(\s*opci[oó]n\s*\d+\s*\))\s*$",
        "",
        value or "",
        flags=re.I,
    )
    value = re.sub(r"\s+(?:hd|sd|fhd|uhd)$", "", value, flags=re.I)
    return norm(value)


def parse_entries(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    entries = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        id_match = re.search(r'tvg-id="([^"]*)"', line, re.I)
        group_match = re.search(r'group-title="([^"]*)"', line, re.I)
        display = line.split(",", 1)[1].strip() if "," in line else ""
        url = ""
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("#EXTINF:"):
                break
            if lines[next_index].strip().startswith(("http://", "https://")):
                url = lines[next_index].strip()
                break
        entries.append({
            "id": (id_match.group(1).strip() if id_match else ""),
            "name": base_name(display),
            "category": group_match.group(1).strip() if group_match else "",
            "url": url,
        })
    return entries


def source_channels(url: str) -> list[dict]:
    response = requests.get(url, timeout=45, headers={"User-Agent": "IPTV-PR-E2E/1.0"})
    response.raise_for_status()
    parsed = ap.parsear_m3u(response.text)
    if not parsed:
        raise RuntimeError(f"Fuente sin canales M3U: {url}")
    return parsed


def source_ids(url: str, *, anime_only: bool = False) -> set[str]:
    ids = set()
    for channel in source_channels(url):
        if anime_only and norm(channel.get("categoria", "")) != "anime":
            continue
        extinf = channel.get("extinf", "")
        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        channel_id = match.group(1).strip() if match else ap.extraer_pluto_id(channel.get("url", ""))
        if channel_id:
            ids.add(norm(channel_id))
    return ids


def protected_hashes() -> dict[str, str]:
    paths = [
        ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u",
        ROOT / "IPTV-CHILE-GENERADOR" / "IPTV-CHILE-GENERADOR.m3u",
        *sorted((ROOT / "pluto" / "output" / "playlists").glob("*.m3u")),
    ]
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths if path.is_file()
    }


def same_channel(after: dict, before: dict, unique_names: set[str]) -> bool:
    if after["id"] and before["id"] and norm(after["id"]) == norm(before["id"]):
        return True
    return bool(
        before["name"]
        and before["name"] == after["name"]
        and before["name"] in unique_names
    )


def main() -> None:
    if not PRINCIPAL.is_file() or PRINCIPAL.stat().st_size == 0:
        raise RuntimeError("No existe la playlist principal para la prueba end-to-end.")

    before = parse_entries(PRINCIPAL)
    hashes_before = protected_hashes()

    iptvsv = source_channels(ap.FUENTE_IPTVSV)
    chichicasteca = [
        channel for channel in iptvsv
        if norm(channel.get("categoria", "")) == "tv chichicasteca"
    ]
    if not chichicasteca:
        raise RuntimeError("IPTVSV no entregó el grupo TV Chichicasteca para validar su clasificación.")

    es_anime_ids = source_ids(ap.FUENTES_PLUTO[1], anime_only=True)
    latam_mx_ids = (
        source_ids(ap.FUENTES_PLUTO[0])
        | source_ids(ap.FUENTES_PLUTO[2])
        | source_ids(ap.FUENTE_PLUTO_ALTERNATIVAS)
    )
    es_only_ids = es_anime_ids - latam_mx_ids
    es_only_ids |= {norm(value) for value in ap.PLUTO_ES_ANIME_IDS_HISTORICOS} - latam_mx_ids

    result = synchronize_once()
    after = parse_entries(PRINCIPAL)

    if any(item["name"] == "los pitufos" for item in after):
        raise AssertionError("Los Pitufos sigue presente en la principal.")

    if any(
        norm(item["category"]) in {"tv chichicasteca", "los chichastecas"}
        for item in after
    ):
        raise AssertionError("La carpeta TV Chichicasteca/Los Chichastecas no fue eliminada.")

    source_urls = {
        (channel.get("url") or "").strip()
        for channel in chichicasteca
        if channel.get("url")
    }
    guatemala_urls = {
        item["url"] for item in after
        if norm(item["category"]) == "guatemala" and item["url"]
    }
    missing_chichicasteca = source_urls - guatemala_urls
    if missing_chichicasteca:
        raise AssertionError(
            f"{len(missing_chichicasteca)} canales de TV Chichicasteca no quedaron en Guatemala."
        )

    if any(
        norm(item["id"]) in es_only_ids
        and norm(item["category"]) == "anime"
        and "pluto" in item["url"].lower()
        for item in after
    ):
        raise AssertionError("Quedó Anime exclusivo de Pluto España en la principal.")

    before_kept = [
        item for item in before
        if item["name"] != "los pitufos"
        and not (
            norm(item["id"]) in es_only_ids
            and norm(item["category"]) == "anime"
            and "pluto" in item["url"].lower()
        )
    ]
    before_name_counts = Counter(item["name"] for item in before_kept if item["name"])
    after_name_counts = Counter(item["name"] for item in after if item["name"])
    unique_names = {
        name for name, count in before_name_counts.items()
        if count == 1 and after_name_counts.get(name, 0) == 1
    }

    cursor = 0
    for old in before_kept:
        match_index = next(
            (
                index for index in range(cursor, len(after))
                if same_channel(after[index], old, unique_names)
            ),
            None,
        )
        if match_index is None:
            raise AssertionError(
                f"Se perdió un canal existente o una alternativa: {old['name']} / {old['id']}"
            )
        cursor = match_index + 1

    before_heidi = [item for item in before if "heidi" in item["name"]]
    after_heidi = [item for item in after if "heidi" in item["name"]]
    if before_heidi and not after_heidi:
        raise AssertionError("Heidi u otro canal Heidi existente fue eliminado.")

    hashes_after = protected_hashes()
    if hashes_before != hashes_after:
        changed = sorted(
            name for name in set(hashes_before) | set(hashes_after)
            if hashes_before.get(name) != hashes_after.get(name)
        )
        raise AssertionError("Se modificaron listas protegidas: " + ", ".join(changed))

    print("SELFTEST SINCRONIZACIÓN REAL: OK")
    print(f"Canales iniciales: {len(before)}")
    print(f"Canales finales: {len(after)}")
    print(f"Canales TV Chichicasteca clasificados en Guatemala: {len(source_urls)}")
    print(f"Canales Heidi conservados: {len(after_heidi)}")
    print(f"Canales Pluto ES Anime exclusivos excluidos: {len(es_only_ids)}")
    print(f"Resumen sincronización: {result}")
    print("Orden existente, alternativas y archivos protegidos: OK")


if __name__ == "__main__":
    main()

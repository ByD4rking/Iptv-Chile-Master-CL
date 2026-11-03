#!/usr/bin/env python3
"""Prueba end-to-end de la reconciliación real en el checkout de una PR.

Solo se ejecuta desde selftest_reconexion_principal.py cuando
GITHUB_EVENT_NAME=pull_request. Modifica el checkout temporal de Actions,
nunca publica ni hace push.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
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
    value = re.sub(
        r"\s*(?:\[\s*pluto(?:\s*tv)?\s*(?:es|españa)\s*\]|\(\s*pluto(?:\s*tv)?\s*(?:es|españa)\s*\))\s*$",
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
        name_match = re.search(r'tvg-name="([^"]*)"', line, re.I)
        group_match = re.search(r'group-title="([^"]*)"', line, re.I)
        display = line.split(",", 1)[1].strip() if "," in line else ""
        tvg_name = base_name(name_match.group(1) if name_match else display)
        display_name = base_name(display)
        url = ""
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("#EXTINF:"):
                break
            candidate_url = lines[next_index].strip()
            if candidate_url and not candidate_url.startswith("#"):
                url = candidate_url
                break
        entries.append({
            "id": (id_match.group(1).strip() if id_match else ""),
            "name": display_name,
            "tvg_name": tvg_name,
            "is_pitufos": tvg_name == "los pitufos" or display_name == "los pitufos",
            "category": group_match.group(1).strip() if group_match else "",
            "url": url,
            "extinf": line,
        })
    return entries


def source_channels(url: str) -> list[dict]:
    response = requests.get(url, timeout=45, headers={"User-Agent": "IPTV-PR-E2E/1.0"})
    response.raise_for_status()
    parsed = ap.parsear_m3u(response.text)
    if not parsed:
        raise RuntimeError(f"Fuente sin canales M3U: {url}")
    return parsed


def channel_ids(channels: list[dict], *, anime_only: bool = False) -> set[str]:
    ids = set()
    for channel in channels:
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


def identity_key(item: dict, other_ids: set[str], unique_names: set[str]) -> str:
    channel_id = norm(item.get("id", ""))
    name = item.get("tvg_name") or item.get("name") or ""
    if channel_id and channel_id in other_ids:
        return "id:" + channel_id
    if name and name in unique_names:
        return "name:" + name
    if channel_id:
        return "id:" + channel_id
    return "name:" + name


def main(args: argparse.Namespace) -> None:
    if not PRINCIPAL.is_file() or PRINCIPAL.stat().st_size == 0:
        raise RuntimeError("No existe la playlist principal para la prueba end-to-end.")

    before_path = args.before if args.before else PRINCIPAL
    before = parse_entries(before_path)
    hashes_before = protected_hashes()

    iptvsv = source_channels(ap.FUENTE_IPTVSV)
    magma = source_channels(ap.FUENTE_MAGMA)
    chichicasteca = [
        channel for channel in iptvsv
        if norm(channel.get("categoria", "")) == "tv chichicasteca"
    ]
    if not chichicasteca:
        raise RuntimeError("IPTVSV no entregó el grupo TV Chichicasteca para validar su clasificación.")

    pluto_latam = source_channels(ap.FUENTES_PLUTO[0])
    pluto_es = source_channels(ap.FUENTES_PLUTO[1])
    pluto_mx = source_channels(ap.FUENTES_PLUTO[2])
    pluto_mx_alt = source_channels(ap.FUENTE_PLUTO_ALTERNATIVAS)

    es_anime_ids = channel_ids(pluto_es, anime_only=True)
    latam_mx_ids = (
        channel_ids(pluto_latam)
        | channel_ids(pluto_mx)
        | channel_ids(pluto_mx_alt)
    )
    allowed_anime_ids = (
        channel_ids(pluto_latam, anime_only=True)
        | channel_ids(pluto_mx, anime_only=True)
        | channel_ids(pluto_mx_alt, anime_only=True)
    )
    es_only_ids = es_anime_ids - latam_mx_ids
    es_only_ids |= {norm(value) for value in ap.PLUTO_ES_ANIME_IDS_HISTORICOS} - latam_mx_ids

    if args.audit_only:
        result = {"mode": "audit-only"}
    else:
        # Ejecuta el mismo flujo de producción: sincronización previa,
        # alimentador histórico, unificación CHILE y reconciliación final.
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "ejecutar_actualizacion_principal.py")],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "unificar_chile.py")],
            cwd=ROOT,
            check=True,
        )
        result = synchronize_once()
    after = parse_entries(PRINCIPAL)
    after_ids = {norm(item["id"]) for item in after if item["id"]}
    missing_pluto_latam_mx = allowed_anime_ids - after_ids
    if missing_pluto_latam_mx:
        raise AssertionError(
            f"Faltan {len(missing_pluto_latam_mx)} IDs Anime de Pluto LATAM/MX en la principal."
        )

    if any(item["is_pitufos"] for item in after):
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

    forbidden_categories = {"pluto tv", "total", "otros", "tv chichicasteca", "los chichastecas"}
    if any(norm(item["category"]) in forbidden_categories for item in after):
        raise AssertionError("La principal conserva una carpeta prohibida o la carpeta Chichicasteca.")

    urls = [item["url"] for item in after if item["url"]]
    duplicates = [url for url, count in Counter(urls).items() if count > 1]
    if duplicates:
        raise AssertionError(f"Hay URLs duplicadas en la principal: {duplicates[:10]!r}")

    allowed_cleanup_categories = {
        "total", "otros", "telemundo noticias", "sky sports",
        "qatar", "palestina", "corea del norte", "corea del sur",
        "israel", "alemania", "francia", "iran", "rusia",
        "guinea ecuatorial", "estados unidos",
    }
    before_kept = [
        item for item in before
        if not item["is_pitufos"]
        and norm(item["category"]) not in allowed_cleanup_categories
        and not (
            norm(item["id"]) in es_only_ids
            and norm(item["category"]) == "anime"
            and "pluto" in item["url"].lower()
        )
    ]
    before_name_counts = Counter(
        item["tvg_name"] or item["name"] for item in before_kept
        if item["tvg_name"] or item["name"]
    )
    after_name_counts = Counter(
        item["tvg_name"] or item["name"] for item in after
        if item["tvg_name"] or item["name"]
    )
    unique_names = {
        name for name, count in before_name_counts.items()
        if count == 1 and after_name_counts.get(name, 0) == 1
    }
    before_ids = {norm(item["id"]) for item in before_kept if item["id"]}
    after_ids = {norm(item["id"]) for item in after if item["id"]}

    before_keys = [
        identity_key(item, after_ids, unique_names)
        for item in before_kept
    ]
    after_keys = [
        identity_key(item, before_ids, unique_names)
        for item in after
    ]
    before_counts = Counter(before_keys)
    after_counts = Counter(after_keys)
    for key, count in before_counts.items():
        if after_counts.get(key, 0) < count:
            raise AssertionError(
                f"Se perdió una alternativa existente: {key}; "
                f"antes={count}, después={after_counts.get(key, 0)}; resumen={result!r}"
            )

    before_order = list(dict.fromkeys(before_keys))
    after_order = [key for key in dict.fromkeys(after_keys) if key in before_counts]
    if after_order != before_order:
        raise AssertionError(
            f"Cambió el orden relativo de los canales/categorías existentes: "
            f"antes={before_order[:30]!r}; después={after_order[:30]!r}"
        )

    before_heidi = [item for item in before if "heidi" in item["name"] or "heidi" in item["tvg_name"]]
    after_heidi = [item for item in after if "heidi" in item["name"] or "heidi" in item["tvg_name"]]
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
    print(f"Canales IPTVSV: {len(iptvsv)}; MAGNA: {len(magma)}")
    print(f"Canales TV Chichicasteca clasificados en Guatemala: {len(source_urls)}")
    print(f"Canales Pluto LATAM/ES/MX: {len(pluto_latam)}/{len(pluto_es)}/{len(pluto_mx)}")
    print(f"IDs Anime LATAM/MX integrados: {len(allowed_anime_ids)}")
    print(f"Canales Heidi conservados: {len(after_heidi)}")
    print(f"Canales Pluto ES Anime exclusivos excluidos: {len(es_only_ids)}")
    print(f"Resumen sincronización: {result}")
    print("Orden existente, alternativas y archivos protegidos: OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--before", type=Path)
    main(parser.parse_args())

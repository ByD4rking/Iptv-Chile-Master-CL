#!/usr/bin/env python3
"""Prueba end-to-end de la reconciliación real en el checkout de una PR.

Solo se ejecuta desde selftest_reconexion_principal.py cuando
GITHUB_EVENT_NAME=pull_request. Modifica el checkout temporal de Actions,
nunca publica ni hace push.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse
from collections import Counter, defaultdict
from pathlib import Path

import requests

import alimentar_principal as ap


ROOT = Path(__file__).resolve().parents[1]
PRINCIPAL = ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"


def norm(value: str) -> str:
    return ap.normalizar(value or "")


def base_name(value: str) -> str:
    value = re.sub(r"\s*\|\s*(?:cl|chile)\s*$", "", value or "", flags=re.I)
    value = re.sub(r"\s*(?:\[\s*v2\s*\]|\(\s*v2\s*\)|v2)\s*$", " 2", value or "", flags=re.I)
    value = re.sub(
        r"\s*(?:\[\s*(?:opc(?:i[oó]n)?\.?|option)\s*\d+\s*\]|\(\s*(?:opci[oó]n|option)\s*\d+\s*\))\s*$",
        "",
        value or "",
        flags=re.I,
    )
    value = re.sub(
        r"\s*(?:\[\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\]|"
        r"\(\s*(?:magna|magma|pluto(?:\s*tv)?(?:\s*(?:latam|mx|es|españa))?)\s*\))\s*$",
        "",
        value or "",
        flags=re.I,
    )
    value = re.sub(r"\s+(?:magna|magma|pluto\s*(?:latam|mx|es)|espanol|españa|spanish|hd|sd|fhd|uhd)$", "", value, flags=re.I)
    return norm(value)


def channel_name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", base_name(value))


def is_es_region_url(url: str) -> bool:
    value = (url or "").lower()
    return any(marker in value for marker in ("country=es", "marketingregion=es", "preferredlanguage=es-es"))


def parse_entries(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    entries = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        id_match = re.search(r'tvg-id="([^"]*)"', line, re.I)
        name_match = re.search(r'tvg-name="([^"]*)"', line, re.I)
        group_match = re.search(r'group-title="([^"]*)"', line, re.I)
        display_raw = line.split(",", 1)[1].strip() if "," in line else ""
        tvg_name_raw = name_match.group(1).strip() if name_match else display_raw
        tvg_name = base_name(tvg_name_raw)
        display_name = base_name(display_raw)
        url = ""
        for next_index in range(index + 1, len(lines)):
            if lines[next_index].startswith("#EXTINF:"):
                break
            candidate_url = lines[next_index].strip()
            if candidate_url and not candidate_url.startswith("#"):
                url = candidate_url
                break
        category = group_match.group(1).strip() if group_match else ""
        full_name = norm(tvg_name_raw + " " + display_raw)
        is_pitufos = channel_name_key(tvg_name_raw).startswith("lospitufos") or channel_name_key(display_raw).startswith("lospitufos")
        is_pitufos_es = is_pitufos and (
            is_es_region_url(url) or bool(re.search(r"\b(?:es|espanol|espana)\b", full_name))
        )
        is_es_anime = norm(category) == "anime" and (
            is_es_region_url(url) or bool(re.search(r"\b(?:espanol|espana|pluto\s*es)\b", full_name))
        )
        option_match = re.search(
            r"\[\s*(?:opci[oó]n|opc\.?|option)\s*(\d+)\s*\]$",
            display_raw,
            re.I,
        )
        logo_match = re.search(r'(?:tvg-logo|logo)="([^"]*)"', line, re.I)
        entries.append({
            "id": (id_match.group(1).strip() if id_match else ""),
            "name": display_name,
            "tvg_name": tvg_name,
            "display_raw": display_raw,
            "is_option": bool(option_match),
            "option_number": int(option_match.group(1)) if option_match else 1,
            "logo": logo_match.group(1).strip() if logo_match else "",
            "is_pitufos": is_pitufos,
            "is_pitufos_es": is_pitufos_es,
            "is_es_anime": is_es_anime,
            "category": category,
            "url": url,
            "position": len(entries),
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


def stream_id(channel: dict) -> str:
    url = channel.get("url", "") or ""
    channel_id = ap.extraer_pluto_id(url)
    if not channel_id:
        extinf = channel.get("extinf", "")
        match = re.search(r'tvg-id="([^"]+)"', extinf, re.I)
        channel_id = match.group(1).strip() if match else ""
    return norm(channel_id)


def channel_ids(channels: list[dict], *, anime_only: bool = False) -> set[str]:
    ids = set()
    for channel in channels:
        if anime_only and norm(channel.get("categoria", "")) != "anime":
            continue
        channel_id = stream_id(channel)
        if channel_id:
            ids.add(channel_id)
    return ids


def jwt_expiry(url: str) -> int:
    token = parse_qs(urlparse(url).query).get("jwt", [""])[0]
    parts = token.split(".")
    if len(parts) != 3:
        raise RuntimeError(f"URL Pluto sin JWT válido: {url[:120]}")
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    expiry = data.get("exp")
    if not isinstance(expiry, (int, float)):
        raise RuntimeError("El JWT de Pluto no contiene exp.")
    return int(expiry)


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
    # Si una fuente añade o quita tvg-id, conserva la identidad por nombre
    # cuando ese nombre aparece en ambas versiones y no hay IDs en ambos lados.
    channel_id = norm(item.get("id", ""))
    valid_id = channel_id if channel_id and channel_id not in {"-1", "0", "none", "null", "na", "n/a", "undefined"} else ""
    name = item.get("tvg_name") or item.get("name") or ""
    name_key = channel_name_key(name)
    if valid_id and valid_id in other_ids:
        return "id:" + valid_id
    if name_key and name_key in unique_names:
        return "name:" + name_key
    if valid_id:
        return "id:" + valid_id
    return "name:" + name_key if name_key else "name:"


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
    # La principal usa Pluto MX externo sin JWT, no la playlist MX propia tokenizada.
    pluto_mx = source_channels(ap.FUENTE_PLUTO_ALTERNATIVAS)

    if any("jwt=" not in (channel.get("url", "").lower()) for channel in pluto_latam + pluto_es):
        raise AssertionError("Pluto LATAM/ES entregó una URL sin JWT.")
    if any("jwt=" in (channel.get("url", "").lower()) for channel in pluto_mx):
        raise AssertionError("Pluto MX externo no debe usar JWT.")

    es_anime_ids = channel_ids(pluto_es, anime_only=True)
    latam_mx_ids = channel_ids(pluto_latam) | channel_ids(pluto_mx)
    allowed_anime_names = {
        channel_name_key(channel.get("nombre") or channel.get("tvg-name") or "")
        for channel in pluto_latam + pluto_mx
        if norm(channel.get("categoria", "")) == "anime"
        and channel_name_key(channel.get("nombre") or channel.get("tvg-name") or "")
    }
    es_only_ids = es_anime_ids - latam_mx_ids
    es_only_ids |= {norm(value) for value in ap.PLUTO_ES_ANIME_IDS_HISTORICOS} - latam_mx_ids

    if args.audit_only:
        result = {"mode": "audit-only"}
    else:
        # Ejecuta el mismo flujo de producción: alimentador histórico
        # (con su barrera de orden), reconciliación, unificación CHILE
        # y reconciliación final.
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "ejecutar_actualizacion_principal.py")],
            cwd=ROOT,
            check=True,
        )
        result = {"mode": "full-production-orchestrator"}
    after = parse_entries(PRINCIPAL)
    after_playable = [item for item in after if item["url"]]
    after_ids = {
        stream_id({"id": item["id"], "extinf": item["extinf"], "url": item["url"]})
        for item in after_playable
        if stream_id({"id": item["id"], "extinf": item["extinf"], "url": item["url"]})
    }
    after_urls_by_id = defaultdict(set)
    after_urls = {item["url"] for item in after_playable}
    for item in after_playable:
        channel_id = stream_id({"id": item["id"], "extinf": item["extinf"], "url": item["url"]})
        if channel_id:
            after_urls_by_id[channel_id].add(item["url"])

    # Pluto MX externo es una URL estable jmp2, no un JWT propio.
    mx_source_channels = [channel for channel in pluto_mx if channel.get("url")]
    mx_source_urls = {channel["url"] for channel in mx_source_channels}
    missing_mx_urls = mx_source_urls - after_urls
    if missing_mx_urls:
        missing_names = sorted({
            channel.get("nombre", channel["url"])
            for channel in mx_source_channels
            if channel["url"] in missing_mx_urls
        })
        raise AssertionError(
            f"La maestra perdió {len(missing_mx_urls)} URLs de Pluto MX externo. "
            f"Ejemplos: {', '.join(missing_names[:8])}"
        )

    # Verificar que la maestra contiene el JWT recién generado en LATAM/ES
    # y que queda margen amplio antes de su expiración.
    expected_token_urls = defaultdict(set)
    for source_name, channels in (("LATAM", pluto_latam), ("ES", pluto_es)):
        for channel in channels:
            if source_name == "ES" and (
                norm(channel.get("categoria", "")) == "anime"
                or channel_name_key(channel.get("nombre", "")).startswith("lospitufos")
            ):
                continue
            url = channel.get("url", "")
            channel_id = stream_id(channel)
            if not channel_id or "jwt=" not in url.lower():
                continue
            expiry = jwt_expiry(url)
            if expiry - int(time.time()) < 12 * 60 * 60:
                raise AssertionError(f"JWT de Pluto {source_name} no fue renovado con suficiente anticipación.")
            expected_token_urls[channel_id].add(url)
    for channel_id, urls in expected_token_urls.items():
        if channel_id in after_urls_by_id:
            missing_urls = urls - after_urls_by_id[channel_id]
            if missing_urls:
                raise AssertionError(
                    f"La maestra no contiene el JWT actual de Pluto para ID {channel_id}."
                )
    after_nonpluto_all = [
        item for item in after_playable if not ap.es_url_pluto(item["url"])
    ]
    # Las alternativas se validan por grupo/contigüidad, no como un cambio
    # de orden de los canales principales históricos.
    after_nonpluto = [item for item in after_nonpluto_all if not item["is_option"]]
    after_anime_names = {
        channel_name_key(item["display_raw"])
        for item in after
        if norm(item["category"]) == "anime"
    }
    missing_pluto_latam_mx = allowed_anime_names - after_anime_names
    if missing_pluto_latam_mx:
        raise AssertionError(
            f"Faltan {len(missing_pluto_latam_mx)} canales Anime de Pluto LATAM/MX en la principal."
        )

    if any(item["is_pitufos_es"] for item in after):
        raise AssertionError("La variante Los Pitufos de Pluto ES sigue presente.")
    pitufos_infantiles = [
        item for item in after
        if item["is_pitufos"] and norm(item["category"]) in {"infantil", "infantiles"}
    ]
    if not pitufos_infantiles:
        raise AssertionError("No quedó Los Pitufos de LATAM/MX/MAGNA en Infantiles.")
    if any(item["is_es_anime"] for item in after):
        raise AssertionError("Quedó un canal Pluto ES o Español en Anime.")

    anime_names = {
        channel_name_key(item["display_raw"])
        for item in after
        if norm(item["category"]) == "anime"
    }
    if "delmitv" not in anime_names or "delmitv2" not in anime_names:
        raise AssertionError("Falta Delmi TV o Delmi TV 2 en Anime.")
    pluto_es_anime_urls = {
        channel.get("url", "")
        for channel in pluto_es
        if norm(channel.get("categoria", "")) == "anime"
    }
    if any(item["url"] in pluto_es_anime_urls for item in after_playable):
        raise AssertionError("La principal conserva una URL exacta de Pluto ES dentro de Anime.")

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
        if not item["is_pitufos_es"]
        and not item["is_es_anime"]
        and norm(item["category"]) not in allowed_cleanup_categories
        and item["url"]
        and not ap.es_url_pluto(item["url"])
        and not (
            norm(item["id"]) in es_only_ids
            and norm(item["category"]) == "anime"
            and "pluto" in item["url"].lower()
        )
    ]
    def valid_id(item):
        value = norm(item.get("id", ""))
        return value if value and value not in {"-1", "0", "none", "null", "na", "n/a", "undefined"} else ""

    def ids_by_name(items):
        result = defaultdict(set)
        for item in items:
            name = channel_name_key(item.get("tvg_name") or item.get("name") or "")
            if name:
                channel_id = valid_id(item)
                if channel_id:
                    result[name].add(channel_id)
        return result

    before_ids_by_name = ids_by_name(before_kept)
    after_ids_by_name = ids_by_name(after_nonpluto_all)
    unique_names = {
        name for name in set(before_ids_by_name) | set(after_ids_by_name)
        if name in before_ids_by_name and name in after_ids_by_name
        and (not before_ids_by_name[name] or not after_ids_by_name[name])
    }
    before_ids = {valid_id(item) for item in before_kept if valid_id(item)}
    after_ids_nonpluto = {valid_id(item) for item in after_nonpluto_all if valid_id(item)}

    before_by_category = defaultdict(list)
    after_by_category = defaultdict(list)
    for item in before_kept:
        category = norm(item["category"])
        key = identity_key(item, after_ids_nonpluto, unique_names)
        if key not in before_by_category[category]:
            before_by_category[category].append(key)
    for item in after_nonpluto:
        category = norm(item["category"])
        key = identity_key(item, before_ids, unique_names)
        # Las URLs alternativas del mismo tvg-id forman un solo canal lógico
        # para comparar orden; no deben contarse como canales nuevos.
        if key not in after_by_category[category]:
            after_by_category[category].append(key)

    global_after_counts = Counter(
        identity_key(item, before_ids, unique_names)
        for item in after_playable
    )
    for category, before_keys in before_by_category.items():
        # Estos dos bloques tienen reordenamiento intencional y validaciones
        # específicas: MAGMA se consolida en Entretenimiento y los tres
        # prioritarios se ponen al inicio de Infantiles.
        if category in {
            norm("Entretenimiento / Cine / Series"),
            norm("Infantiles"),
        }:
            continue
        after_keys = after_by_category.get(category, [])
        before_counts = Counter(before_keys)
        after_counts = Counter(after_keys)

        for key, count in before_counts.items():
            if after_counts.get(key, 0) < count and global_after_counts.get(key, 0) < count:
                raise AssertionError(
                    f"Se perdió una alternativa existente: {key} en {category}; "
                    f"antes={count}, después_total={global_after_counts.get(key, 0)}; "
                    f"resumen={result!r}"
                )

        # Las categorías pueden cambiar; se compara el orden solo de los
        # canales que permanecen en la misma categoría. Los movidos se auditan
        # por identidad y cantidad global, no como una pérdida.
        expected_order = [
            key for key in dict.fromkeys(before_keys)
            if after_counts.get(key, 0) > 0
        ]
        actual_order = [
            key for key in dict.fromkeys(after_keys)
            if key in before_counts
        ]
        if actual_order != expected_order:
            mismatch = next(
                (
                    index for index, (expected, actual) in enumerate(zip(expected_order, actual_order))
                    if expected != actual
                ),
                min(len(expected_order), len(actual_order)),
            )
            raise AssertionError(
                f"Cambió el orden relativo dentro de {category} en índice {mismatch}: "
                f"antes={expected_order[mismatch:mismatch + 8]!r}; "
                f"después={actual_order[mismatch:mismatch + 8]!r}; "
                f"longitudes={len(expected_order)}/{len(actual_order)}"
            )

    # Verificar el orden de los tres canales prioritarios dentro de Infantiles.
    infantiles = [
        item for item in after_playable
        if norm(item["category"]) in {"infantil", "infantiles"}
    ]
    infantiles_unique = []
    for item in infantiles:
        key = channel_name_key(item["display_raw"])
        if key and key not in infantiles_unique:
            infantiles_unique.append(key)
    if infantiles_unique[:3] != ["popeye", "lospitufos", "heidi"]:
        raise AssertionError(
            "Infantiles no comienza en el orden Popeye, Los Pitufos, Heidi: "
            + repr(infantiles_unique[:6])
        )

    # Verificar que las alternativas estén juntas, numeradas y compartan logo/ID.
    alternatives_by_name = defaultdict(list)
    for item in after_playable:
        key = (norm(item["category"]), channel_name_key(item["display_raw"]))
        if key[1]:
            alternatives_by_name[key].append(item)
    for key, group in alternatives_by_name.items():
        if len(group) < 2:
            continue
        ids = {item["id"] for item in group if item["id"]}
        # Nombres repetidos con IDs distintos son ambiguos; no se fusionan a ciegas.
        if len(ids) > 1:
            continue
        group.sort(key=lambda item: item["position"])
        positions = [item["position"] for item in group]
        if positions[-1] - positions[0] + 1 != len(positions):
            raise AssertionError(f"Alternativas separadas para {key}: {positions}")
        ids = {item["id"] for item in group}
        if len(ids) > 1:
            raise AssertionError(f"Alternativas con tvg-id diferentes para {key}: {ids}")
        tvg_names = {item["tvg_name"] for item in group if item["tvg_name"]}
        if len(tvg_names) > 1:
            raise AssertionError(f"Alternativas con tvg-name diferentes para {key}: {tvg_names}")
        logos = {item["logo"] for item in group if item["logo"]}
        if len(logos) > 1:
            raise AssertionError(f"Alternativas con logos diferentes para {key}: {logos}")
        for option_index, item in enumerate(group, start=1):
            if option_index == 1 and item["is_option"]:
                raise AssertionError(f"La URL principal tiene etiqueta de opción: {key}")
            if option_index > 1 and (not item["is_option"] or item["option_number"] != option_index):
                raise AssertionError(f"Numeración incorrecta de alternativas para {key}")
            if re.search(r"\bMAGNA\b|\bMAGMA\b|\bPluto\s+(?:LATAM|MX|ES)\b", item["display_raw"] + " " + item["tvg_name"], re.I):
                raise AssertionError(f"El nombre muestra el proveedor en {key}: {item['display_raw']}")

    before_heidi = [item for item in before if item["url"] and ("heidi" in item["name"] or "heidi" in item["tvg_name"])]
    after_heidi = [item for item in after_playable if "heidi" in item["name"] or "heidi" in item["tvg_name"]]
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
    print(f"Canales IPTVSV: {len(iptvsv)}; MAGMA: {len(magma)}")
    print(f"Canales TV Chichicasteca clasificados en Guatemala: {len(source_urls)}")
    print(f"Canales Pluto LATAM/ES/MX externo: {len(pluto_latam)}/{len(pluto_es)}/{len(pluto_mx)}")
    print(f"Canales Anime LATAM/MX integrados: {len(allowed_anime_names)}")
    print(f"Canales Heidi conservados: {len(after_heidi)}")
    print(f"Canales Pluto ES Anime exclusivos excluidos: {len(es_only_ids)}")
    print(f"Resumen sincronización: {result}")
    print("Orden existente, alternativas y archivos protegidos: OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--before", type=Path)
    main(parser.parse_args())

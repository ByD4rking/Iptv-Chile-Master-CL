#!/usr/bin/env python3
"""Audita cambios de canales y URLs de todas las fuentes M3U antes de generar playlists.

No publica listas por sí solo: los workflows propietarios ejecutan después sus
generadores habituales. GOD se inspecciona en modo de solo lectura.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from m3u_structure import normalize_m3u_bytes, validate_m3u_bytes
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "reportes" / "fuentes"
MAX_BYTES = 32 * 1024 * 1024
TIMEOUT = 18
RETRIES = 3
WORKERS = 12


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value.lower()).strip()
    return value


def parse_m3u(text: str) -> dict[str, list[str]]:
    """Return stable channel key -> [name, stream URL, group]."""
    result: dict[str, list[str]] = {}
    current = None
    ordinal = 0
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            ordinal += 1
            name = line.rsplit(",", 1)[-1].strip() if "," in line else ""
            name_match = re.search(r'tvg-name="([^"]*)"', line)
            if name_match and name_match.group(1).strip():
                name = name_match.group(1).strip()
            id_match = re.search(r'tvg-id="([^"]*)"', line)
            group_match = re.search(r'group-title="([^"]*)"', line)
            channel_id = id_match.group(1).strip() if id_match else ""
            group = group_match.group(1).strip() if group_match else ""
            identity = channel_id or (normalize(name) + "|" + normalize(group))
            current = (identity or f"entry-{ordinal}", name, group)
        elif current and line.startswith(("http://", "https://")):
            key, name, group = current
            # Preserve duplicates with deterministic suffixes rather than hiding them.
            unique_key = key
            duplicate = 2
            while unique_key in result:
                unique_key = f"{key}#{duplicate}"
                duplicate += 1
            result[unique_key] = [name, line, group]
            current = None
    return result


def compact_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()



def validate_partial_m3u_bytes(data: bytes, source: str = "fuente") -> tuple[int, list[str]]:
    """Acepta pares M3U válidos y reporta líneas defectuosas sin inventar canales.

    Se usa únicamente para auditoría de fuentes M3U.CL. Una fuente parcial nunca
    puede demostrar bajas ni reemplazar el último snapshot completo.
    """
    label = urlparse(str(source)).hostname or "fuente"
    if not data or not data.strip():
        raise ValueError(f"{label}: respuesta vacía")
    text = data.decode("utf-8-sig", errors="replace")
    lowered = text[:4096].casefold()
    if "<!doctype html" in lowered or "<html" in lowered or "<body" in lowered:
        raise ValueError(f"{label}: respuesta HTML, no M3U")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not (lines[0].upper() == "#EXTM3U" or lines[0].upper().startswith("#EXTM3U ")):
        raise ValueError(f"{label}: falta cabecera #EXTM3U")
    entries = 0
    pending = False
    warnings = []
    for number, line in enumerate(lines[1:], start=2):
        upper = line.upper()
        if upper.startswith("#EXTINF"):
            if not upper.startswith("#EXTINF:"):
                warnings.append(f"línea {number}: EXTINF mal formada")
                pending = False
                continue
            if pending:
                warnings.append(f"línea {number}: EXTINF anterior sin URI")
            if "," not in line or not line.rsplit(",", 1)[-1].strip():
                warnings.append(f"línea {number}: EXTINF sin nombre")
                pending = False
                continue
            duration_field = line.split(",", 1)[0][len("#EXTINF:"):].strip()
            duration = duration_field.split(maxsplit=1)[0] if duration_field else ""
            if not re.fullmatch(r"-?\d+(?:\.\d+)?", duration):
                warnings.append(f"línea {number}: duración inválida")
                pending = False
                continue
            pending = True
            continue
        if line.startswith("#"):
            continue
        if not pending:
            warnings.append(f"línea {number}: URL suelta")
            continue
        try:
            parsed = urlparse(line)
            valid = parsed.scheme in {"http", "https", "rtsp", "rtmp", "rtp", "udp", "mms", "mmsh", "mmst", "ftp"} and bool(parsed.hostname)
        except ValueError:
            valid = False
        if not valid:
            warnings.append(f"línea {number}: URI inválida")
            pending = False
            continue
        entries += 1
        pending = False
    if pending:
        warnings.append("última entrada EXTINF sin URI")
    if entries == 0:
        raise ValueError(f"{label}: no contiene pares EXTINF/URI válidos")
    return entries, warnings


def fetch_url(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"URL HTTP(S) inválida: {url}")
    host = (parsed.hostname or "").lower()
    if host == "m3u.cl" or host.endswith(".m3u.cl"):
        variants = [
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
             "Accept": "text/plain, application/vnd.apple.mpegurl, application/x-mpegURL, */*"},
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
             "Accept": "text/plain, application/vnd.apple.mpegurl, application/x-mpegURL, */*",
             "Referer": "https://m3u.cl/"},
            {"User-Agent": "IPTV-Chile-Source-Audit/1.0", "Accept": "*/*", "Referer": "https://m3u.cl/"},
        ]
    else:
        variants = [{"User-Agent": "IPTV-Chile-Source-Audit/1.0", "Accept": "*/*"}]

    last_error = None
    attempts = variants if len(variants) > 1 else variants * RETRIES
    for attempt, headers in enumerate(attempts):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=TIMEOUT) as response:
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError(f"fuente supera límite de {MAX_BYTES} bytes")
            data = normalize_m3u_bytes(data)
            try:
                validate_m3u_bytes(data, source=url)
            except ValueError:
                if host != "m3u.cl" and not host.endswith(".m3u.cl"):
                    raise
                validate_partial_m3u_bytes(data, source=url)
            return data
        except Exception as exc:
            last_error = exc
            if attempt + 1 < len(attempts):
                time.sleep(1.5 * (2 ** min(attempt, 3)))
    # El proveedor publica LATAM en su página HTML, pero el archivo
    # estático /lista/LATAM.m3u está ausente. Usar solo esa página oficial
    # como fallback, reconstruyendo el mismo formato M3U para el diff.
    if host == "m3u.cl" and parsed.path.lower() == "/lista/latam.m3u":
        try:
            from m3ucl_html_fallback import LATAM_PAGE, build_latam_m3u

            page_request = Request(
                LATAM_PAGE,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
                    "Accept": "text/html, */*",
                    "Referer": "https://m3u.cl/",
                },
            )
            with urlopen(page_request, timeout=TIMEOUT) as response:
                page_data = response.read(MAX_BYTES + 1)
            if len(page_data) > MAX_BYTES:
                raise ValueError(f"página LATAM supera límite de {MAX_BYTES} bytes")
            return build_latam_m3u(page_data.decode("utf-8-sig", errors="replace"))
        except Exception as fallback_error:
            last_error = RuntimeError(
                f"endpoint M3U y fallback HTML oficial fallaron: {fallback_error}"
            )
    raise RuntimeError(f"{type(last_error).__name__}: {last_error}")


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def configured_sources(scope: str) -> list[dict]:
    result = []
    if scope == "principal":
        config = load_json(ROOT / "config" / "playlist_sources.json", {})
        principal = config.get("principal", {})
        for item in principal.get("sources", []):
            result.append({"name": "PRINCIPAL/" + item["name"], "url": item["url"], "readonly": False})
        for name, url in principal.get("special_sources", {}).items():
            # IPTVSV y MAGMA ya están en "sources"; se agregan los especiales restantes.
            if name not in {"iptvsv", "magma"}:
                result.append({"name": "PRINCIPAL/SPECIAL-" + name.upper(), "url": url, "readonly": False})
        for section in ("pluto_sources", "pluto_catalog_sources", "legacy_pluto_sources"):
            for item in principal.get(section, []):
                result.append({"name": "PRINCIPAL/" + item["name"], "url": item["url"], "readonly": False})
    elif scope == "generador":
        config = load_json(ROOT / "IPTV-CHILE-GENERADOR" / "config" / "sources.json", {})
        for item in config.get("sources", []):
            result.append({"name": "GENERADOR/" + item["name"], "url": item["url"], "readonly": False})
    else:
        raise ValueError(f"Ámbito M3U no soportado: {scope}")
    names = set()
    for item in result:
        if item["name"] in names:
            raise ValueError(f"Nombre de fuente duplicado: {item['name']}")
        names.add(item["name"])
    return result


def local_pluto_sources() -> list[dict]:
    paths = sorted((ROOT / "pluto" / "output" / "playlists").glob("pluto_*.m3u"))
    return [
        {"name": "PLUTO/" + path.stem.upper(), "path": path, "readonly": False}
        for path in paths
    ]


def snapshot_entry(raw: bytes, label: str, url: str, allow_partial: bool = False) -> dict:
    raw = normalize_m3u_bytes(raw)
    partial = False
    warnings = []
    try:
        validate_m3u_bytes(raw, source=url or label)
    except ValueError:
        if not allow_partial:
            raise
        _, warnings = validate_partial_m3u_bytes(raw, source=url or label)
        partial = bool(warnings)
    text = raw.decode("utf-8-sig", errors="replace")
    parsed = parse_m3u(text)
    if not parsed:
        raise ValueError("M3U sin canales válidos")
    # Never persist signed HLS URLs or query tokens in audit snapshots/reports.
    fingerprint = lambda value: compact_hash(str(value).encode("utf-8"))[:16]
    channels = {
        key: [fingerprint(entry[0]), fingerprint(entry[1]), fingerprint(entry[2])]
        for key, entry in parsed.items()
    }
    return {
        "url": url,
        "sha256": compact_hash(raw),
        "channel_count": len(channels),
        "channels": channels,
        "partial": partial,
        "partial_warnings": warnings[:50],
    }


def diff_source(name: str, old: dict | None, new: dict) -> dict:
    is_partial = bool(new.get("partial", False))
    if old is None:
        return {"source": name, "status": "partial" if is_partial else "baseline", "source_complete": not is_partial, "channels": new["channel_count"], "url": new["url"], "partial_warnings": new.get("partial_warnings", [])}
    old_channels = old.get("channels", {})
    new_channels = new.get("channels", {})
    old_keys, new_keys = set(old_channels), set(new_channels)
    added_keys = set(new_keys - old_keys)
    removed_keys = set(old_keys - new_keys)
    # Una fuente parcial puede demostrar altas/cambios observados, nunca bajas.
    if is_partial:
        removed_keys.clear()
    changed_name = []
    changed_url = []
    changed_group = []

    def compare_pair(key: str, before: list[str], after: list[str]) -> None:
        if before[0] != after[0]:
            changed_name.append({"key": key, "before_fingerprint": before[0], "after_fingerprint": after[0]})
        if before[1] != after[1]:
            changed_url.append({"key": key, "before_fingerprint": before[1], "after_fingerprint": after[1]})
        if before[2] != after[2]:
            changed_group.append({"key": key, "before_fingerprint": before[2], "after_fingerprint": after[2]})

    for key in sorted(old_keys & new_keys):
        compare_pair(key, old_channels[key], new_channels[key])

    # Si una fuente no entrega tvg-id, un cambio de nombre altera la clave.
    # Reconciliar solo por URL cuando esta aparece una única vez en ambos lados:
    # permite detectar renombres y evita emparejamientos ambiguos por duplicados.
    old_by_url: dict[str, list[str]] = {}
    new_by_url: dict[str, list[str]] = {}
    for key in removed_keys:
        old_by_url.setdefault(old_channels[key][1], []).append(key)
    for key in added_keys:
        new_by_url.setdefault(new_channels[key][1], []).append(key)
    for url_fp in sorted(set(old_by_url) & set(new_by_url)):
        before_keys = old_by_url[url_fp]
        after_keys = new_by_url[url_fp]
        if len(before_keys) != 1 or len(after_keys) != 1:
            continue
        before_key, after_key = before_keys[0], after_keys[0]
        compare_pair(before_key, old_channels[before_key], new_channels[after_key])
        removed_keys.discard(before_key)
        added_keys.discard(after_key)

    added = sorted(added_keys)
    removed = sorted(removed_keys)
    url_changed = old.get("url") != new.get("url")
    content_changed = old.get("sha256") != new.get("sha256")
    order_changed = list(old_channels) != list(new_channels)
    return {
        "source": name,
        "status": "partial" if is_partial else ("changed" if (url_changed or added or removed or changed_name or changed_url or changed_group or order_changed) else "unchanged"),
        "source_complete": not is_partial,
        "partial_warnings": new.get("partial_warnings", []),
        "source_url_changed": url_changed,
        "old_source_url": old.get("url"),
        "new_source_url": new.get("url"),
        "added_channels": len(added),
        "removed_channels": len(removed),
        "renamed_channels": len(changed_name),
        "changed_stream_urls": len(changed_url),
        "changed_categories": len(changed_group),
        "content_hash_changed": content_changed,
        "channel_order_changed": order_changed,
        "samples": {
            "added": added[:30],
            "removed": removed[:30],
            "renamed": changed_name[:30],
            "stream_urls": changed_url[:30],
            "categories": changed_group[:30],
        },
    }


def audit(scope: str) -> dict:
    state_path = STATE_DIR / f"estado_{scope}.json"
    report_path = STATE_DIR / f"auditoria_{scope}.json"
    previous = load_json(state_path, {"schema_version": 1, "sources": {}})
    previous_sources = previous.get("sources", {})
    observed: dict[str, dict] = {}
    errors = []
    jobs = []

    if scope in {"principal", "generador"}:
        for source in configured_sources(scope):
            jobs.append((source["name"], source["url"], source.get("readonly", False), None))
    elif scope == "pluto":
        for source in local_pluto_sources():
            path = source["path"]
            if path.is_file() and path.stat().st_size:
                jobs.append((source["name"], "file://" + str(path.relative_to(ROOT)), False, path))
            else:
                errors.append({"source": source["name"], "error": "playlist regional ausente o vacía"})
    else:
        raise ValueError(scope)

    def retrieve(job):
        name, url, readonly, path = job
        if path is not None:
            raw = path.read_bytes()
        else:
            raw = fetch_url(url)
        allow_partial = scope == "principal" and (urlparse(url).hostname or "").lower().endswith("m3u.cl")
        item = snapshot_entry(raw, name, url, allow_partial=allow_partial)
        return name, item, readonly

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(retrieve, job): job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append({"source": job[0], "url": job[1], "error": str(exc)})
                print(f"[AUDIT][ERROR] {job[0]}: {exc}", file=sys.stderr)

    if jobs and not results:
        raise RuntimeError(f"Ninguna fuente de {scope} pudo auditarse; no se permite continuar a generar listas.")

    configured_names = {job[0] for job in jobs}
    configured_url_changes = [
        {"source": job[0], "before": previous_sources[job[0]].get("url"), "after": job[1]}
        for job in jobs
        if job[0] in previous_sources and previous_sources[job[0]].get("url") != job[1]
    ]
    removed_sources = sorted(set(previous_sources) - configured_names)

    changes = []
    for name, item, readonly in sorted(results):
        old = previous_sources.get(name)
        change = diff_source(name, old, item)
        change["readonly"] = readonly
        changes.append(change)
        if not item.get("partial", False):
            observed[name] = item

    # Failed sources retain their last known-good snapshot; a transient outage
    # must not look like mass channel deletion on the next successful run.
    for error in errors:
        name = error["source"]
        if name in previous_sources and name not in observed:
            observed[name] = previous_sources[name]

    writable_changes = [item for item in changes if not item.get("readonly", False)]
    readonly_changes = [item for item in changes if item.get("readonly", False)]
    timestamp = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": 1,
        "scope": scope,
        "checked_at": timestamp,
        "sources_configured": len(jobs) + (len(errors) if scope == "pluto" else 0),
        "sources_unique_urls": len({job[1] for job in jobs}),
        "sources_checked": len(results),
        "sources_failed": len(errors),
        "sources_partial": sum(1 for item in changes if item.get("status") == "partial"),
        "partial_sources": [item["source"] for item in changes if item.get("status") == "partial"],
        "partial_warnings_total": sum(len(item.get("partial_warnings", [])) for item in changes),
        "changed_sources": sum(1 for item in changes if item["status"] == "changed"),
        "new_sources": sum(1 for item in changes if item["status"] == "baseline"),
        "total_added_channels": sum(item.get("added_channels", 0) for item in changes),
        "total_removed_channels": sum(item.get("removed_channels", 0) for item in changes),
        "total_changed_stream_urls": sum(item.get("changed_stream_urls", 0) for item in changes),
        # Separar fuentes publicables de GOD: se audita, pero nunca se transfiere a la principal.
        "writable_changed_sources": sum(1 for item in writable_changes if item["status"] == "changed"),
        "writable_changed_stream_urls": sum(item.get("changed_stream_urls", 0) for item in writable_changes),
        "readonly_changed_sources": sum(1 for item in readonly_changes if item["status"] == "changed"),
        "readonly_changed_stream_urls": sum(item.get("changed_stream_urls", 0) for item in readonly_changes),
        "total_source_url_changes": len(configured_url_changes),
        "configured_source_url_changes": configured_url_changes,
        "removed_sources": removed_sources,
        "errors": errors,
        "changes": changes,
        "god_included": False,
        "scope_description": "solo lista principal; excluye GOD y Generador",
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {"schema_version": 1, "updated_at": timestamp, "sources": observed}
    state_path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[AUDIT][{scope}] fuentes={len(results)} parciales={report['sources_partial']} errores={len(errors)} "
        f"fuentes_con_cambios={report['changed_sources']} "
        f"canales_nuevos={report['total_added_channels']} "
        f"canales_eliminados={report['total_removed_channels']} "
        f"URLs_stream_cambiadas={report['total_changed_stream_urls']} "
        f"(lista_principal={report['writable_changed_stream_urls']}, "
        f"solo_lectura={report['readonly_changed_stream_urls']}) "
        f"URLs_fuente_cambiadas={report['total_source_url_changes']}"
    )
    for item in changes:
        changed_urls = int(item.get("changed_stream_urls", 0))
        if changed_urls or item.get("status") == "partial":
            scope_label = "solo-lectura" if item.get("readonly", False) else "principal"
            print(
                f"[AUDIT][detalle] {scope_label} {item['source']}: "
                f"{changed_urls} URLs; altas={item.get('added_channels', 0)}; "
                f"bajas={item.get('removed_channels', 0)}; "
                f"advertencias={len(item.get('partial_warnings', []))}"
            )
    print(f"[AUDIT] Informe: {report_path.relative_to(ROOT)}")
    print(f"[AUDIT] Estado: {state_path.relative_to(ROOT)}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("principal", "generador", "pluto"), required=True)
    args = parser.parse_args()
    audit(args.scope)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

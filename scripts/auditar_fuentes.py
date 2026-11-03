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


def fetch_url(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"URL HTTP(S) inválida: {url}")
    last_error = None
    for attempt in range(RETRIES):
        try:
            request = Request(url, headers={"User-Agent": "IPTV-Chile-Source-Audit/1.0", "Accept": "*/*"})
            with urlopen(request, timeout=TIMEOUT) as response:
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError(f"fuente supera límite de {MAX_BYTES} bytes")
            if not data.lstrip(b"\xef\xbb\xbf \r\n").startswith(b"#EXTM3U"):
                raise ValueError("respuesta no contiene cabecera #EXTM3U")
            return data
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < RETRIES:
                time.sleep(1.5 * (2 ** attempt))
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
            if name == "pluto_mx_alternatives":
                result.append({"name": "PRINCIPAL/SPECIAL-" + name.upper(), "url": url, "readonly": False})
        for item in principal.get("pluto_sources", []):
            result.append({"name": "PRINCIPAL/" + item["name"], "url": item["url"], "readonly": False})
        # GOD is audited on every Principal run but can never be rewritten by this audit.
        for item in config.get("god", {}).get("sources", []):
            result.append({"name": "GOD/" + item["name"], "url": item["url"], "readonly": True})
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


def snapshot_entry(raw: bytes, label: str, url: str) -> dict:
    text = raw.decode("utf-8-sig", errors="replace")
    parsed = parse_m3u(text)
    if not parsed:
        raise ValueError("M3U sin canales válidos")
    # Never persist signed HLS URLs or query tokens in audit snapshots/reports.
    channels = {
        key: [entry[0], compact_hash(entry[1].encode("utf-8")), entry[2]]
        for key, entry in parsed.items()
    }
    return {
        "url": url,
        "sha256": compact_hash(raw),
        "channel_count": len(channels),
        "channels": channels,
    }


def diff_source(name: str, old: dict | None, new: dict) -> dict:
    if old is None:
        return {"source": name, "status": "baseline", "channels": new["channel_count"], "url": new["url"]}
    old_channels = old.get("channels", {})
    new_channels = new.get("channels", {})
    old_keys, new_keys = set(old_channels), set(new_channels)
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    changed_name = []
    changed_url = []
    changed_group = []
    for key in sorted(old_keys & new_keys):
        before = old_channels[key]
        after = new_channels[key]
        if before[0] != after[0]:
            changed_name.append({"key": key, "before": before[0], "after": after[0]})
        if before[1] != after[1]:
            changed_url.append({"key": key, "name": after[0] or before[0], "before": before[1], "after": after[1]})
        if before[2] != after[2]:
            changed_group.append({"key": key, "before": before[2], "after": after[2]})
    url_changed = old.get("url") != new.get("url")
    content_changed = old.get("sha256") != new.get("sha256")
    return {
        "source": name,
        "status": "changed" if (url_changed or added or removed or changed_name or changed_url or changed_group) else "unchanged",
        "source_url_changed": url_changed,
        "old_source_url": old.get("url"),
        "new_source_url": new.get("url"),
        "added_channels": len(added),
        "removed_channels": len(removed),
        "renamed_channels": len(changed_name),
        "changed_stream_urls": len(changed_url),
        "changed_categories": len(changed_group),
        "content_hash_changed": content_changed,
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
        item = snapshot_entry(raw, name, url)
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

    changes = []
    for name, item, readonly in sorted(results):
        old = previous_sources.get(name)
        change = diff_source(name, old, item)
        change["readonly"] = readonly
        changes.append(change)
        observed[name] = item

    # Failed sources retain their last known-good snapshot; a transient outage
    # must not look like mass channel deletion on the next successful run.
    for error in errors:
        name = error["source"]
        if name in previous_sources and name not in observed:
            observed[name] = previous_sources[name]

    timestamp = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": 1,
        "scope": scope,
        "checked_at": timestamp,
        "sources_configured": len(jobs) + (len(errors) if scope == "pluto" else 0),
        "sources_checked": len(results),
        "sources_failed": len(errors),
        "changed_sources": sum(1 for item in changes if item["status"] == "changed"),
        "new_sources": sum(1 for item in changes if item["status"] == "baseline"),
        "total_added_channels": sum(item.get("added_channels", 0) for item in changes),
        "total_removed_channels": sum(item.get("removed_channels", 0) for item in changes),
        "total_changed_stream_urls": sum(item.get("changed_stream_urls", 0) for item in changes),
        "total_source_url_changes": sum(1 for item in changes if item.get("source_url_changed")),
        "errors": errors,
        "changes": changes,
        "god_read_only": scope == "principal",
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {"schema_version": 1, "updated_at": timestamp, "sources": observed}
    state_path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[AUDIT][{scope}] fuentes={len(results)} errores={len(errors)} "
        f"fuentes_con_cambios={report['changed_sources']} "
        f"canales_nuevos={report['total_added_channels']} "
        f"canales_eliminados={report['total_removed_channels']} "
        f"URLs_stream_cambiadas={report['total_changed_stream_urls']} "
        f"URLs_fuente_cambiadas={report['total_source_url_changes']}"
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

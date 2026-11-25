#!/usr/bin/env python3
"""Comprueba por red los logos candidatos sin exponer URLs ni modificar M3U."""
from __future__ import annotations

import argparse
import json
import socket
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.channel_identity import parse_playlist_text, safe_url_fingerprint

MAX_BYTES = 3 * 1024 * 1024
TIMEOUT = 12
SIGNATURES = {
    "png": lambda b: b.startswith(b"\\x89PNG\\r\\n\\x1a\\n"),
    "jpeg": lambda b: b.startswith(b"\\xff\\xd8\\xff"),
    "gif": lambda b: b.startswith((b"GIF87a", b"GIF89a")),
    "webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}


def _logo_url(record: dict) -> str | None:
    values = {str(v).strip() for v in (record.get("tvg_logo"), record.get("logo")) if v}
    if len(values) != 1:
        return None
    value = next(iter(values))
    try:
        parsed = urlsplit(value)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        return value
    except ValueError:
        return None


def _is_public_host(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            not (ip := __import__("ipaddress").ip_address(item[4][0])).is_private
            and not ip.is_loopback and not ip.is_link_local and not ip.is_reserved
            for item in addresses
        )
    except (OSError, ValueError):
        return False


def inspect_asset(url: str, opener=urllib.request.urlopen) -> dict:
    fingerprint = safe_url_fingerprint(url)
    try:
        parsed = urlsplit(url)
        if not _is_public_host(parsed.hostname or ""):
            return {"fingerprint": fingerprint, "status": "blocked_non_public_host"}
        request = urllib.request.Request(
            url, headers={"User-Agent": "IPTV-Chile-FASE3-LogoAudit/1.0", "Accept": "image/*"}
        )
        with opener(request, timeout=TIMEOUT) as response:
            status = getattr(response, "status", 200)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            data = response.read(MAX_BYTES + 1)
        if status < 200 or status >= 300:
            result = "http_status"
        elif len(data) > MAX_BYTES:
            result = "size_limit"
        elif not data:
            result = "empty_body"
        else:
            fmt = next((name for name, check in SIGNATURES.items() if check(data)), None)
            if not fmt:
                result = "not_an_image"
            elif content_type and not (content_type.startswith("image/") or content_type == "application/octet-stream"):
                result = "content_type_mismatch"
            else:
                result = "valid_" + fmt
        return {"fingerprint": fingerprint, "status": result, "bytes": min(len(data), MAX_BYTES + 1)}
    except urllib.error.HTTPError as exc:
        return {"fingerprint": fingerprint, "status": "http_" + str(exc.code)}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return {"fingerprint": fingerprint, "status": type(exc).__name__}


def collect_candidate_urls(playlist: list[dict], sources: list[tuple[str, list[dict]]]) -> dict[str, str]:
    current_aliases: dict[str, list[int]] = defaultdict(list)
    current_fallback: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(playlist):
        for alias in row.get("aliases", []):
            current_aliases[alias].append(i)
        if row.get("fallback"):
            current_fallback[row["fallback"]].append(i)

    urls: dict[str, str] = {}
    for target in playlist:
        if target.get("tvg_logo") or target.get("logo"):
            continue
        found: dict[str, str] = {}
        ambiguous = False
        for _source_name, records in sources:
            aliases: dict[str, list[int]] = defaultdict(list)
            fallback: dict[str, list[int]] = defaultdict(list)
            for i, row in enumerate(records):
                for alias in row.get("aliases", []):
                    aliases[alias].append(i)
                if row.get("fallback"):
                    fallback[row["fallback"]].append(i)
            matches = set()
            for alias in target.get("aliases", []):
                if len(current_aliases[alias]) != 1:
                    continue
                hits = aliases.get(alias, [])
                if len(hits) > 1:
                    ambiguous = True
                elif len(hits) == 1:
                    matches.add(hits[0])
            if not matches and target.get("fallback") and len(current_fallback[target["fallback"]]) == 1:
                hits = fallback.get(target["fallback"], [])
                if len(hits) > 1:
                    ambiguous = True
                elif len(hits) == 1:
                    matches.add(hits[0])
            for i in matches:
                url = _logo_url(records[i])
                if url:
                    urls[safe_url_fingerprint(url)] = url
        if ambiguous:
            continue
    return urls


def audit(playlist_path: Path, manifest_path: Path) -> dict:
    playlist = parse_playlist_text(playlist_path.read_text(encoding="utf-8-sig", errors="replace"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = []
    for item in manifest.get("sources", []):
        path = Path(str(item.get("path") or ""))
        if path.is_file():
            sources.append((str(item.get("name") or ""), parse_playlist_text(path.read_text(encoding="utf-8-sig", errors="replace"))))
    candidates = collect_candidate_urls(playlist, sources)
    results = [inspect_asset(url) for url in candidates.values()]
    counts: dict[str, int] = defaultdict(int)
    for item in results:
        counts[item["status"]] += 1
    return {
        "candidate_assets_checked": len(results),
        "valid_assets": sum(n for status, n in counts.items() if status.startswith("valid_")),
        "failed_assets": len(results) - sum(n for status, n in counts.items() if status.startswith("valid_")),
        "status_counts": dict(sorted(counts.items())),
        "results": results,
        "policy": "Solo lectura; no registra URLs, no aplica logos y no reemplaza referencias existentes.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist", required=True, type=Path)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.playlist, args.candidate_manifest)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prueba de reproducción conservadora para alternativas IPTV propuestas."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
import urllib.error
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from scripts.channel_identity import parse_playlist_text
from scripts.logo_asset_check import _is_public_host, _safe_open
from scripts.source_recovery import suggest_recoveries

UA = "IPTV-Chile-FASE3-SourceProbe/1.0"
MANIFEST_LIMIT = 256 * 1024
SEGMENT_SAMPLE = 64 * 1024
TIMEOUT = 10


def _fetch(url: str, limit: int) -> tuple[int, str, str, bytes]:
    parsed = urlsplit(url)
    if parsed.scheme.casefold() not in {"http", "https"} or not _is_public_host(parsed.hostname or ""):
        raise ValueError("blocked_non_public_host")
    from urllib.request import Request
    request = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with _safe_open(request, timeout=TIMEOUT) as response:
        status = getattr(response, "status", 200)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        body = response.read(limit + 1)
        final_url = response.geturl()
    if len(body) > limit:
        raise ValueError("response_too_large")
    if status < 200 or status >= 300:
        raise ValueError("http_" + str(status))
    return status, content_type, final_url, body


def _first_uri(lines: list[str]) -> str | None:
    for line in lines:
        value = line.strip()
        if value and not value.startswith("#"):
            return value
    return None


def probe_stream(url: str) -> dict:
    started = time.monotonic()
    try:
        current = url
        for _ in range(3):
            _status, content_type, final_url, body = _fetch(current, MANIFEST_LIMIT)
            text = body.decode("utf-8-sig", errors="replace").lstrip()
            if text.startswith("#EXTM3U"):
                lines = text.splitlines()
                next_uri = None
                for index, line in enumerate(lines):
                    if line.startswith("#EXT-X-STREAM-INF:"):
                        next_uri = _first_uri(lines[index + 1:])
                        break
                if not next_uri:
                    next_uri = _first_uri(lines)
                if not next_uri:
                    return {"ok": False, "status": "manifest_without_media_uri"}
                current = urljoin(final_url, next_uri)
                # A child playlist is fetched on the next iteration; segments
                # are identified by their non-M3U body after the next request.
                continue
            if not body:
                return {"ok": False, "status": "empty_response"}
            if "html" in content_type or text[:256].lower().startswith(("<html", "<!doctype")):
                return {"ok": False, "status": "html_error_page"}
            return {
                "ok": True,
                "status": "segment_or_direct_media_sampled",
                "sample_bytes": len(body),
            }
        return {"ok": False, "status": "playlist_nesting_limit"}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": "http_" + str(exc.code)}
    except Exception as exc:
        reason = str(exc)
        if reason.startswith("http_") or reason in {
            "blocked_non_public_host", "response_too_large"
        }:
            status = reason
        else:
            status = type(exc).__name__
        return {"ok": False, "status": status}


def _probe_with_latency(url: str) -> dict:
    started = time.monotonic()
    result = probe_stream(url)
    result["latency_ms"] = round((time.monotonic() - started) * 1000)
    return result


def audit(playlist_path: Path, health_path: Path, manifest_path: Path, extra_candidates: list[str]) -> dict:
    playlist_bytes = playlist_path.read_bytes()
    current = parse_playlist_text(playlist_bytes.decode("utf-8-sig", errors="replace"))
    health = json.loads(health_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_records = []
    for item in manifest.get("sources", []):
        path = Path(str(item.get("path") or ""))
        if item.get("name") and path.is_file():
            source_records.append((str(item["name"]), parse_playlist_text(path.read_text(encoding="utf-8-sig", errors="replace"))))
    for item in extra_candidates:
        if "=" not in item:
            continue
        name, raw_path = item.split("=", 1)
        path = Path(raw_path)
        if name and path.is_file():
            source_records.append((name, parse_playlist_text(path.read_text(encoding="utf-8-sig", errors="replace"))))

    report = suggest_recoveries(current, source_records, health)
    lookup = {}
    for source_name, records in source_records:
        for record in records:
            if record.get("stream_url"):
                lookup[(source_name, record["stream_fingerprint"])] = record["stream_url"]

    pending = []
    for row in report["recommendations"]:
        for candidate in row["candidates"]:
            url = lookup.get((candidate["source"], candidate["fingerprint"]))
            if url:
                pending.append({
                    "channel": row["channel"],
                    "candidate": candidate["name"],
                    "source": candidate["source"],
                    "confidence": candidate["confidence"],
                    "url": url,
                })

    unique_urls = list(dict.fromkeys(item["url"] for item in pending))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        probed = list(pool.map(_probe_with_latency, unique_urls))
    by_url = dict(zip(unique_urls, probed))
    results = []
    for item in pending:
        result = by_url[item["url"]]
        results.append({
            "channel": item["channel"],
            "candidate": item["candidate"],
            "source": item["source"],
            "confidence": item["confidence"],
            "playback_ok": result["ok"],
            "status": result["status"],
            "latency_ms": result["latency_ms"],
            "sample_bytes": result.get("sample_bytes"),
        })
    return {
        "candidates_tested": len(results),
        "unique_streams_tested": len(unique_urls),
        "playable_candidates": sum(1 for row in results if row["playback_ok"]),
        "failed_candidates": sum(1 for row in results if not row["playback_ok"]),
        "results": results,
        "policy": "Prueba de manifiesto y primera muestra de segmento; no sustituye URL ni modifica playlist.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist", required=True, type=Path)
    parser.add_argument("--health", required=True, type=Path)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.playlist, args.health, args.candidate_manifest, args.candidate)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

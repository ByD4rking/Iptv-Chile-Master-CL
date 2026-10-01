import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from atomic import atomic_write_json

BASE = Path(__file__).resolve().parent.parent
DISCOVERY = BASE / "data" / "teleon_discovery.json"
OUTPUT = BASE / "data" / "teleon_quality.json"

TIMEOUT = 10
WORKERS = 4
RETRIES = 3
BACKOFF = (0.8, 1.8, 3.5)
SEGMENT_LIMIT = 64 * 1024
RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


def fetch(url, accept="*/*", headers=None, limit=256 * 1024):
    merged = {
        "User-Agent": "IPTV-CHILE-GENERADOR/TELEON-QUALITY-1.0",
        "Accept": accept,
    }
    if headers:
        merged.update(headers)
    last = None
    for attempt in range(RETRIES):
        try:
            req = Request(url, headers=merged)
            with urlopen(req, timeout=TIMEOUT) as response:
                data = response.read(limit)
                return response.status, response.headers.get("Content-Type", ""), data, response.geturl()
        except HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in RETRYABLE:
                raise
        except (URLError, TimeoutError) as exc:
            last = str(getattr(exc, "reason", exc))
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF[attempt])
    raise RuntimeError(last or "endpoint no disponible")


def media_segment(text, base_url):
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return urljoin(base_url, line)
    return None


def variants(text, base_url):
    result = []
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    for i, line in enumerate(lines):
        if not line.upper().startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = dict(re.findall(r'([A-Z0-9-]+)=(".*?"|[^,]+)', line.split(":", 1)[1], re.I))
        uri = next((x for x in lines[i + 1:] if not x.startswith("#")), None)
        if not uri:
            continue
        result.append({
            "url": urljoin(base_url, uri),
            "bandwidth": int(re.sub(r"\D", "", attrs.get("BANDWIDTH", "0")) or 0),
            "resolution": attrs.get("RESOLUTION", "").replace('"', "") or None,
        })
    return sorted(result, key=lambda x: (x["bandwidth"], x["resolution"] or ""), reverse=True)


def valid_segment(data, content_type):
    if not data:
        return False
    sample = data[:4096].lower()
    if b"<html" in sample or b"<!doctype" in sample:
        return False
    signatures = (
        data[:3] == b"ID3",
        len(data) >= 8 and data[4:8] == b"ftyp",
        data[:4] == b"\x1a\x45\xdf\xa3",
        len(data) >= 188 and data[0] == 0x47 and (len(data) < 376 or data[188] == 0x47),
    )
    if any(signatures):
        return True
    lowered = (content_type or "").lower()
    return len(data) >= 188 and any(x in lowered for x in ("video/", "audio/", "mp2t", "fmp4", "octet-stream"))


def validate(item):
    url = str(item.get("stream_url") or "").strip()
    headers = item.get("headers") or {}
    result = {
        "page_url": item.get("page_url"),
        "stream_url": url,
        "headers_used": sorted(headers.keys()),
        "playback_checked": True,
        "playback_ok": False,
        "playback_type": None,
        "http_status": None,
        "error": None,
        "validated_url": None,
        "variant_count": 0,
        "variant_index": None,
        "resolution": None,
        "bitrate": None,
        "segment_bytes": None,
    }
    try:
        status, content_type, body, final_url = fetch(
            url,
            accept="application/vnd.apple.mpegurl, application/x-mpegURL, */*",
            headers=headers,
        )
        result["http_status"] = status
        result["validated_url"] = final_url
        if not 200 <= status < 400:
            result["error"] = f"HTTP {status}"
            return result

        text = body.decode("utf-8", "ignore")
        if "#EXTM3U" not in text[:4096]:
            result["error"] = "No es una playlist HLS."
            return result
        result["playback_type"] = "hls"

        candidates = variants(text, final_url)
        if candidates:
            result["variant_count"] = len(candidates)
        else:
            candidates = [{"url": final_url, "bandwidth": 0, "resolution": None}]

        for index, variant in enumerate(candidates, 1):
            try:
                if variant["url"] == final_url:
                    child_text = text
                    child_url = final_url
                else:
                    s, ct, child, child_url = fetch(
                        variant["url"],
                        accept="application/vnd.apple.mpegurl, application/x-mpegURL, */*",
                        headers=headers,
                    )
                    if not 200 <= s < 400:
                        continue
                    child_text = child.decode("utf-8", "ignore")
                segment = media_segment(child_text, child_url)
                if not segment:
                    continue
                s, ct, data, _ = fetch(
                    segment,
                    accept="video/*,audio/*,application/octet-stream,*/*",
                    headers=headers,
                    limit=SEGMENT_LIMIT,
                )
                if 200 <= s < 400 and valid_segment(data, ct):
                    result.update({
                        "playback_ok": True,
                        "variant_index": index,
                        "resolution": variant.get("resolution"),
                        "bitrate": variant.get("bandwidth"),
                        "segment_bytes": len(data),
                    })
                    return result
            except Exception:
                continue

        result["error"] = "Playlist HLS accesible pero ninguna variante/segmento pasó la validación."
    except HTTPError as exc:
        result["http_status"] = exc.code
        result["error"] = f"HTTP {exc.code}"
    except Exception as exc:
        result["error"] = str(exc)
    return result


def main():
    discovery = json.loads(DISCOVERY.read_text(encoding="utf-8-sig"))
    tasks = []
    seen = set()
    for items in discovery.get("profiles", {}).values():
        for item in items:
            for url in item.get("stream_urls") or []:
                if url in seen:
                    continue
                seen.add(url)
                tasks.append({
                    "page_url": item.get("page_url"),
                    "stream_url": url,
                    "headers": item.get("stream_headers") or {"Referer": "https://teleon.tv/"},
                })

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(validate, item) for item in tasks]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda x: (x.get("page_url") or "", x.get("stream_url") or ""))
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "discovery_validation_only",
        "published_automatically": False,
        "total_candidates": len(results),
        "playback_ok": sum(1 for x in results if x["playback_ok"]),
        "playback_failed": sum(1 for x in results if not x["playback_ok"]),
        "results": results,
    }
    atomic_write_json(OUTPUT, output)
    print(f"Teleon HLS candidates: {len(results)}")
    print(f"Reproducción HLS verificada: {output['playback_ok']}")
    print(f"Fallos: {output['playback_failed']}")
    print(f"Salida: {OUTPUT}")


if __name__ == "__main__":
    main()

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from atomic import atomic_write_json, file_sha256

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
QUALITY_FILE = BASE / "data" / "quality.json"
ENDPOINT_HEALTH_FILE = BASE / "data" / "endpoint_health.json"

TIMEOUT = 10
WORKERS = 15
READ_LIMIT = 256 * 1024
SEGMENT_LIMIT = 64 * 1024


def detect_resolution(text):
    if not text:
        return None
    matches = re.findall(r'RESOLUTION=(\d+)x(\d+)', text, re.IGNORECASE)
    if matches:
        width, height = max(
            ((int(w), int(h)) for w, h in matches),
            key=lambda item: (item[1], item[0]),
        )
        return {"width": width, "height": height, "resolution": f"{width}x{height}"}
    match = re.search(r'(\d{3,4})x(\d{3,4})', text, re.IGNORECASE)
    if match:
        width, height = int(match.group(1)), int(match.group(2))
        return {"width": width, "height": height, "resolution": f"{width}x{height}"}
    match = re.search(r'(\d{3,4})p\b', text, re.IGNORECASE)
    if match:
        height = int(match.group(1))
        return {"width": None, "height": height, "resolution": f"{height}p"}
    return None


def detect_bandwidth(text):
    if not text:
        return None
    values = []
    for pattern in (r'BANDWIDTH=(\d+)', r'AVERAGE-BANDWIDTH=(\d+)'):
        values.extend(
            int(match.group(1))
            for match in re.finditer(pattern, text, re.IGNORECASE)
        )
    return max(values) if values else None


def fetch(url, accept="*/*", limit=READ_LIMIT, extra_headers=None):
    headers = {
        "User-Agent": "IPTV-CHILE-GENERADOR/QUALITY-4.0",
        "Accept": accept,
    }
    if extra_headers:
        headers.update(extra_headers)
    request = Request(url, headers=headers)
    with urlopen(request, timeout=TIMEOUT) as response:
        content = response.read(limit)
        return response.status, response.headers.get("Content-Type", ""), content, response.geturl()


def is_hls(text, content_type):
    lowered = (content_type or "").lower()
    return (
        "#EXTM3U" in text[:4096]
        and (
            "#EXT-X-" in text
            or "mpegurl" in lowered
            or "vnd.apple.mpegurl" in lowered
        )
    )


def parse_master_playlist(text, base_url):
    variants = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not line.upper().startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = dict(
            (key.upper(), value)
            for key, value in re.findall(
                r'([A-Z0-9-]+)=(\".*?\"|[^,]+)',
                line.split(":", 1)[1],
                re.IGNORECASE,
            )
        )
        uri = next((x for x in lines[index + 1:] if not x.startswith("#")), None)
        if not uri:
            continue

        resolution = attrs.get("RESOLUTION", "").replace('"', "")
        width = height = 0
        match = re.match(r"(\d+)x(\d+)", resolution)
        if match:
            width, height = int(match.group(1)), int(match.group(2))

        bandwidth = int(re.sub(r"\D", "", attrs.get("BANDWIDTH", "0")) or 0)
        variants.append(
            {
                "url": urljoin(base_url, uri),
                "width": width or None,
                "height": height or None,
                "bandwidth": bandwidth or None,
            }
        )

    # Highest quality first; validation will fall through to the next variant.
    variants.sort(
        key=lambda item: (item["height"] or 0, item["bandwidth"] or 0),
        reverse=True,
    )
    return variants


def first_media_segment(text, base_url):
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-PART:") or line.startswith("#EXT-X-PRELOAD-HINT:"):
            match = re.search(r'URI="([^"]+)"', line, re.IGNORECASE)
            if match:
                return urljoin(base_url, match.group(1))
        if line.startswith("#"):
            continue
        return urljoin(base_url, line)
    return None


def valid_direct_payload(content, content_type):
    if not content:
        return False, "Respuesta vacía."

    lowered = (content_type or "").lower()
    sample = content[:4096].lstrip().lower()

    if "text/html" in lowered or sample.startswith((b"<!doctype html", b"<html", b"<head")):
        return False, "El endpoint respondió HTML."

    if "application/json" in lowered or sample.startswith((b"{", b"[")):
        return False, "El endpoint respondió JSON, no un stream."

    # Common media signatures: MPEG-TS, fMP4/ISO-BMFF, MP3, ID3, AAC/ADTS, Ogg, WebM.
    signatures = (
        len(content) >= 3 and content[:3] == b"ID3",
        len(content) >= 8 and content[4:8] == b"ftyp",
        len(content) >= 3 and content[:3] == b"Ogg",
        len(content) >= 4 and content[:4] == b"\x1a\x45\xdf\xa3",
        (
            len(content) >= 188
            and content[0] == 0x47
            and (
                (len(content) >= 376 and content[188] == 0x47)
                or (len(content) >= 564 and content[376] == 0x47)
            )
        ),
        len(content) >= 2 and content[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
        len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xF6) == 0xF0,
    )
    if any(signatures):
        return True, None

    media_types = (
        "video/",
        "audio/",
        "application/octet-stream",
        "application/mp2t",
        "application/fmp4",
    )
    if any(token in lowered for token in media_types) and len(content) >= 188:
        return True, None

    return False, "No se detectó una firma/formato de medio reproducible."


def validate_hls(url, initial_text, initial_content_type, max_depth=2):
    def attempt(playlist_url, playlist_text, playlist_type, depth):
        if "#EXTM3U" not in playlist_text[:4096]:
            return None, "La respuesta no es una playlist HLS M3U."

        variants = parse_master_playlist(playlist_text, playlist_url)
        if variants and depth < max_depth:
            failures = []
            for index, variant in enumerate(variants, 1):
                try:
                    status, content_type, content, final_url = fetch(
                        variant["url"],
                        accept="application/vnd.apple.mpegurl, application/x-mpegURL, */*",
                    )
                    if not 200 <= status < 400:
                        failures.append(f"variante {index}: HTTP {status}")
                        continue
                    child = content.decode("utf-8", errors="ignore")
                    if parse_master_playlist(child, final_url):
                        nested, error = attempt(final_url, child, content_type, depth + 1)
                        if nested:
                            nested["variant_index"] = index
                            nested["variant_count"] = len(variants)
                            return nested, None
                        failures.append(f"variante {index}: {error}")
                        continue

                    segment_url = first_media_segment(child, final_url)
                    if not segment_url:
                        failures.append(f"variante {index}: sin segmento")
                        continue
                    seg_status, seg_type, segment, _ = fetch(
                        segment_url,
                        accept="video/*,audio/*,application/octet-stream,*/*",
                        limit=SEGMENT_LIMIT,
                        extra_headers={"Range": "bytes=0-65535"},
                    )
                    if 200 <= seg_status < 400 and segment:
                        valid, error = valid_direct_payload(segment, seg_type)
                        if valid:
                            return (
                                {
                                    "playback_checked": True,
                                    "playback_ok": True,
                                    "playback_type": "hls",
                                    "playback_error": None,
                                    "width": variant["width"],
                                    "height": variant["height"],
                                    "resolution": (
                                        f'{variant["width"]}x{variant["height"]}'
                                        if variant["width"] and variant["height"]
                                        else None
                                    ),
                                    "bitrate": variant["bandwidth"],
                                    "segment_bytes": len(segment),
                                    "variant_index": index,
                                    "variant_count": len(variants),
                                    "validated_url": final_url,
                                },
                                None,
                            )
                        failures.append(f"variante {index}: segmento inválido: {error}")
                    else:
                        failures.append(f"variante {index}: segmento HTTP {seg_status}")
                except Exception as error:
                    failures.append(f"variante {index}: {error}")

            return None, "Todas las variantes HLS fallaron: " + "; ".join(failures[:8])

        segment_url = first_media_segment(playlist_text, playlist_url)
        if not segment_url:
            return None, "Playlist HLS válida pero sin segmento reproducible."

        status, content_type, segment, _ = fetch(
            segment_url,
            accept="video/*,audio/*,application/octet-stream,*/*",
            limit=SEGMENT_LIMIT,
            extra_headers={"Range": "bytes=0-65535"},
        )
        if not 200 <= status < 400 or not segment:
            return None, f"Segmento HLS inaccesible (HTTP {status})."

        valid, error = valid_direct_payload(segment, content_type)
        if not valid:
            return None, f"Segmento HLS inválido: {error}"

        resolution = detect_resolution(playlist_text)
        bandwidth = detect_bandwidth(playlist_text)
        return (
            {
                "playback_checked": True,
                "playback_ok": True,
                "playback_type": "hls",
                "playback_error": None,
                "width": resolution["width"] if resolution else None,
                "height": resolution["height"] if resolution else None,
                "resolution": resolution["resolution"] if resolution else None,
                "bitrate": bandwidth,
                "segment_bytes": len(segment),
                "validated_url": playlist_url,
            },
            None,
        )

    result, error = attempt(url, initial_text, initial_content_type, 0)
    if result:
        return result
    return {
        "playback_checked": True,
        "playback_ok": False,
        "playback_type": "hls",
        "playback_error": error or "Validación HLS fallida.",
    }


def inspect_url(item):
    channel = item["channel"]
    source = item["source"]
    url = str(source.get("url") or "").strip()

    result = {
        "channel_id": channel.get("id", ""),
        "channel_name": channel.get("name", ""),
        "url": url,
        "source": source.get("source", ""),
        "source_priority": int(source.get("priority") or 0),
        "width": None,
        "height": None,
        "resolution": None,
        "bitrate": None,
        "quality_score": 0,
        "detected": False,
        "playback_checked": False,
        "playback_ok": False,
        "playback_type": None,
        "playback_error": None,
        "validated_url": None,
        "variant_index": None,
        "variant_count": None,
        "error": None,
    }

    if not url:
        result["error"] = "URL vacía"
        return result

    try:
        status, content_type, content, final_url = fetch(url)
        if not 200 <= status < 400:
            result["error"] = f"HTTP {status}"
            return result

        text = content.decode("utf-8", errors="ignore")
        if is_hls(text, content_type):
            hls = validate_hls(final_url, text, content_type)
            result.update(hls)
        else:
            result["playback_checked"] = True
            result["playback_type"] = "direct"
            valid, error = valid_direct_payload(content, content_type)
            result["playback_ok"] = valid
            result["playback_error"] = error
            result["validated_url"] = final_url

            resolution = detect_resolution(text)
            bitrate = detect_bandwidth(text)
            if resolution:
                result["width"] = resolution["width"]
                result["height"] = resolution["height"]
                result["resolution"] = resolution["resolution"]
            if bitrate:
                result["bitrate"] = bitrate

        result["detected"] = bool(result["height"] or result["bitrate"])
        result["quality_score"] = (
            (result["height"] or 0) * 10000000
            + (result["bitrate"] or 0)
        )
    except HTTPError as error:
        result["error"] = f"HTTP {error.code}"
    except URLError as error:
        result["error"] = str(error.reason)
    except Exception as error:
        result["error"] = str(error)

    return result


def main():
    if not CHANNELS_FILE.exists():
        raise SystemExit("No existe channels.json")

    channels_sha256 = file_sha256(CHANNELS_FILE)
    with CHANNELS_FILE.open("r", encoding="utf-8") as f:
        channels = json.load(f)

    tasks = [
        {"channel": channel, "source": source}
        for channel in channels
        for source in channel.get("sources", [])
    ]
    total = len(tasks)

    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - QUALITY + PLAYBACK SCANNER")
    print("=" * 60)
    print(f"Canales: {len(channels)}")
    print(f"URLs:    {total}")
    print(f"Workers: {WORKERS}")

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(inspect_url, item) for item in tasks]
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)
            if completed == 1 or completed % 100 == 0 or completed == total:
                ok = sum(1 for x in results if x["playback_ok"])
                hls = sum(1 for x in results if x["playback_type"] == "hls")
                fallback = sum(1 for x in results if (x.get("variant_count") or 0) > 1)
                print(
                    f"[{completed}/{total}] reproducibles: {ok} | "
                    f"HLS: {hls} | masters con variantes: {fallback}"
                )

    # Invariantes de entrada: cada candidato debe evaluarse exactamente una vez.\n    task_urls = [str(task["source"].get("url") or "").strip() for task in tasks]\n    if len(task_urls) != len(set(task_urls)):\n        raise SystemExit("INCONSISTENCIA: channels.json contiene URLs candidatas duplicadas.")\n    if any(not str(task["channel"].get("id") or "").strip() for task in tasks):\n        raise SystemExit("INCONSISTENCIA: existe un candidato sin channel_id.")\n\n    endpoint_health = {}
    if ENDPOINT_HEALTH_FILE.exists():
        try:
            with ENDPOINT_HEALTH_FILE.open("r", encoding="utf-8-sig") as f:
                endpoint_health = json.load(f)
        except Exception:
            endpoint_health = {}

    from datetime import datetime, timezone
    checked_at = datetime.now(timezone.utc).isoformat()
    for result in results:
        url = result["url"]
        state = endpoint_health.setdefault(url, {
            "channel_id": result["channel_id"],
            "channel_name": result["channel_name"],
            "source": result["source"],
            "priority": result["source_priority"],
            "checks": 0,
            "successes": 0,
            "failures": 0,
            "consecutive_failures": 0,
            "last_success": None,
            "last_failure": None,
            "last_error": None,
        })
        state.update({
            "channel_id": result["channel_id"],
            "channel_name": result["channel_name"],
            "source": result["source"],
            "priority": result["source_priority"],
            "checks": int(state.get("checks") or 0) + 1,
        })
        if result["playback_ok"]:
            state["successes"] = int(state.get("successes") or 0) + 1
            state["consecutive_failures"] = 0
            state["last_success"] = checked_at
            state["last_error"] = None
        else:
            state["failures"] = int(state.get("failures") or 0) + 1
            state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
            state["last_failure"] = checked_at
            state["last_error"] = result.get("error") or result.get("playback_error")
        result["endpoint_consecutive_failures"] = state["consecutive_failures"]
        result["endpoint_checks"] = int(state.get("checks") or 0)
        result["endpoint_successes"] = int(state.get("successes") or 0)
        result["endpoint_failures"] = int(state.get("failures") or 0)

    atomic_write_json(ENDPOINT_HEALTH_FILE, endpoint_health)

    channels_quality = {}
    for result in results:
        channel = channels_quality.setdefault(
            result["channel_id"],
            {"channel_name": result["channel_name"], "sources": []},
        )
        channel["sources"].append(result)

    for channel in channels_quality.values():
        available = [source for source in channel["sources"] if source["playback_ok"]]
        channel["best"] = (
            max(
                available,
                key=lambda x: (x["height"] or 0, x["bitrate"] or 0),
            )
            if available
            else None
        )

    output = {
        "schema_version": 3,
        "channels_sha256": channels_sha256,
        "total_channels": len(channels),
        "total_urls": total,
        "detected": sum(1 for result in results if result["detected"]),
        "playback_ok": sum(1 for result in results if result["playback_ok"]),
        "playback_failed": sum(
            1 for result in results
            if result["playback_checked"] and not result["playback_ok"]
        ),
        "hls_checked": sum(1 for result in results if result["playback_type"] == "hls"),
        "endpoint_candidates": total,
        "channels_with_multiple_candidates": sum(1 for x in channels_quality.values() if len(x["sources"]) > 1),
        "hls_fallback_successes": sum(
            1 for result in results if (result.get("variant_index") or 0) > 1
        ),
        "results": results,
        "channels": channels_quality,
    }

    atomic_write_json(QUALITY_FILE, output)

    print("=" * 60)
    print("QUALITY + PLAYBACK SCANNER TERMINADO")
    print("=" * 60)
    print(f"URLs analizadas:          {total}")
    print(f"Reproducibles:            {output['playback_ok']}")
    print(f"Fallos de reproducción:   {output['playback_failed']}")
    print(f"HLS comprobados:          {output['hls_checked']}")
    print(f"Fallback HLS exitosos:    {output['hls_fallback_successes']}")
    print(f"Resoluciones detectadas:  {output['detected']}")
    print(f"Snapshot channels.json:   {channels_sha256}")
    print(f"Archivo:                  {QUALITY_FILE}")


if __name__ == "__main__":
    main()

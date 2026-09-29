import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
QUALITY_FILE = BASE / "data" / "quality.json"

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
        values.extend(int(match.group(1)) for match in re.finditer(pattern, text, re.IGNORECASE))

    return max(values) if values else None


def fetch(url, accept="*/*", limit=READ_LIMIT, extra_headers=None):
    headers = {
        "User-Agent": "IPTV-CHILE-GENERADOR/QUALITY-2.0",
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
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = dict(
            (key.upper(), value)
            for key, value in re.findall(
                r'([A-Z0-9-]+)=(".*?"|[^,]+)',
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
        variants.append({
            "url": urljoin(base_url, uri),
            "width": width or None,
            "height": height or None,
            "bandwidth": bandwidth or None,
        })

    variants.sort(key=lambda item: (item["height"] or 0, item["bandwidth"] or 0), reverse=True)
    return variants


def first_media_segment(text, base_url):
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        return urljoin(base_url, line)
    return None


def validate_hls(url, initial_text, initial_content_type):
    playlist_url = url
    playlist_text = initial_text
    playlist_type = initial_content_type
    resolution = detect_resolution(playlist_text)
    bandwidth = detect_bandwidth(playlist_text)

    variants = parse_master_playlist(playlist_text, playlist_url)
    if variants:
        selected = variants[0]
        playlist_url = selected["url"]
        status, playlist_type, content, final_url = fetch(
            playlist_url,
            accept="application/vnd.apple.mpegurl, application/x-mpegURL, */*",
        )
        if status < 200 or status >= 400:
            return {
                "playback_checked": True,
                "playback_ok": False,
                "playback_type": "hls",
                "playback_error": f"HTTP {status} al cargar variante HLS",
                "width": selected["width"],
                "height": selected["height"],
                "resolution": (
                    f'{selected["width"]}x{selected["height"]}'
                    if selected["width"] and selected["height"]
                    else None
                ),
                "bitrate": selected["bandwidth"],
            }
        playlist_text = content.decode("utf-8", errors="ignore")
        playlist_url = final_url
        resolution = resolution or detect_resolution(playlist_text)
        bandwidth = bandwidth or detect_bandwidth(playlist_text)

    if "#EXTM3U" not in playlist_text:
        return {
            "playback_checked": True,
            "playback_ok": False,
            "playback_type": "hls",
            "playback_error": "La respuesta HLS no es una playlist M3U válida.",
        }

    segment_url = first_media_segment(playlist_text, playlist_url)
    if not segment_url:
        return {
            "playback_checked": True,
            "playback_ok": False,
            "playback_type": "hls",
            "playback_error": "Playlist HLS válida pero sin segmento reproducible.",
        }

    try:
        status, content_type, segment, _ = fetch(
            segment_url,
            accept="video/*,audio/*,application/octet-stream,*/*",
            limit=SEGMENT_LIMIT,
            extra_headers={"Range": "bytes=0-65535"},
        )
        if status < 200 or status >= 400 or not segment:
            return {
                "playback_checked": True,
                "playback_ok": False,
                "playback_type": "hls",
                "playback_error": f"Segmento HLS inaccesible (HTTP {status}).",
            }

        return {
            "playback_checked": True,
            "playback_ok": True,
            "playback_type": "hls",
            "playback_error": None,
            "width": resolution["width"] if resolution else None,
            "height": resolution["height"] if resolution else None,
            "resolution": resolution["resolution"] if resolution else None,
            "bitrate": bandwidth,
            "segment_bytes": len(segment),
        }
    except Exception as error:
        return {
            "playback_checked": True,
            "playback_ok": False,
            "playback_type": "hls",
            "playback_error": f"Segmento HLS: {error}",
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
        "error": None,
    }

    if not url:
        result["error"] = "URL vacía"
        return result

    try:
        status, content_type, content, final_url = fetch(url)
        if status < 200 or status >= 400:
            result["error"] = f"HTTP {status}"
            return result

        text = content.decode("utf-8", errors="ignore")
        if is_hls(text, content_type):
            hls = validate_hls(final_url, text, content_type)
            result.update({key: value for key, value in hls.items() if value is not None})
        else:
            result["playback_checked"] = True
            result["playback_type"] = "direct"
            lowered = text[:512].lower()
            if not content or "text/html" in (content_type or "").lower() or "<html" in lowered:
                result["playback_ok"] = False
                result["playback_error"] = "La URL respondió contenido no reproducible."
            else:
                result["playback_ok"] = True
                result["playback_error"] = None

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
                print(f"[{completed}/{total}] reproducibles: {ok} | HLS: {hls}")

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
                key=lambda x: (
                    x["height"] or 0,
                    x["bitrate"] or 0,
                ),
            )
            if available
            else None
        )

    output = {
        "total_channels": len(channels),
        "total_urls": total,
        "detected": sum(1 for result in results if result["detected"]),
        "playback_ok": sum(1 for result in results if result["playback_ok"]),
        "playback_failed": sum(1 for result in results if result["playback_checked"] and not result["playback_ok"]),
        "hls_checked": sum(1 for result in results if result["playback_type"] == "hls"),
        "results": results,
        "channels": channels_quality,
    }

    with QUALITY_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("QUALITY + PLAYBACK SCANNER TERMINADO")
    print("=" * 60)
    print(f"URLs analizadas:       {total}")
    print(f"Reproducibles:         {output['playback_ok']}")
    print(f"Fallos de reproducción:{output['playback_failed']}")
    print(f"HLS comprobados:       {output['hls_checked']}")
    print(f"Resoluciones detectadas: {output['detected']}")
    print(f"Archivo:               {QUALITY_FILE}")


if __name__ == "__main__":
    main()

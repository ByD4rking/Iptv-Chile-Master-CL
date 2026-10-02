import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from atomic import atomic_write_json, file_sha256

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
QUALITY_FILE = BASE / "data" / "quality.json"
STATUS_FILE = BASE / "data" / "status.json"
ENDPOINT_HEALTH_FILE = BASE / "data" / "endpoint_health.json"

TIMEOUT = 10
WORKERS = 15
READ_LIMIT = 256 * 1024
SEGMENT_LIMIT = 64 * 1024
HLS_STABILITY_SEGMENTS = 3
ENDPOINT_QUARANTINE_AFTER = 5
ENDPOINT_QUARANTINE_HOURS = 24
RETRIES = 3
RETRY_BACKOFF_SECONDS = (0.8, 1.8, 3.5)
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


def endpoint_health_key(url, channel_id=None):
    """Clave estable por canal; elimina solo parámetros efímeros de sesión."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
    raw = str(url or "").strip()
    channel = str(channel_id or "").strip()
    if channel and raw.startswith(f"{channel}|"):
        raw = raw[len(channel) + 1 :].strip()
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        normalized = raw
    else:
        ephemeral = {
            "token", "jwt", "access_token", "refresh_token", "session",
            "sessionid", "sid", "deviceid", "clientid", "nimblesessionid",
            "expires", "exp", "signature", "sig", "hmac",
        }
        query = [(k,v) for k,v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in ephemeral]
        normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(sorted(query), doseq=True), ""))
    return f"{channel}|{normalized}" if channel else normalized

def endpoint_health_score(item):
    """Score operativo 0-100 usando historial persistente, sin inventar checks."""
    checks = int(item.get("endpoint_checks") or 0)
    successes = int(item.get("endpoint_successes") or 0)
    failures = int(item.get("endpoint_failures") or 0)
    consecutive = int(item.get("endpoint_consecutive_failures") or 0)
    if checks <= 0:
        base = 50.0
    else:
        base = 100.0 * successes / max(checks, successes + failures, 1)
    penalty = min(50.0, consecutive * 10.0)
    return round(max(0.0, min(100.0, base - penalty)), 2)


def quality_key(item, status_item, source_priority):
    # Debe coincidir con el criterio utilizado por generate.py.
    checks = int(item.get("endpoint_checks") or 0)
    successes = int(item.get("endpoint_successes") or 0)
    reliability = (successes + 1) / (checks + 2)
    return (
        endpoint_health_score(item),
        -int(item.get("endpoint_consecutive_failures") or 0),
        reliability,
        checks,
        int(item.get("height") or 0),
        int(item.get("bitrate") or 0),
        -int(status_item.get("response_time_ms") or 999999),
        int(source_priority or 0),
    )


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
    last_error = None
    for attempt in range(RETRIES):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=TIMEOUT) as response:
                if response.status in RETRYABLE_HTTP:
                    last_error = f"HTTP {response.status}"
                else:
                    content = response.read(limit)
                    return response.status, response.headers.get("Content-Type", ""), content, response.geturl()
        except HTTPError as error:
            last_error = f"HTTP {error.code}"
            if error.code not in RETRYABLE_HTTP:
                raise
        except (URLError, TimeoutError) as error:
            last_error = str(getattr(error, "reason", error))
        if attempt < RETRIES - 1:
            import time
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])
    raise RuntimeError(f"Endpoint no disponible tras {RETRIES} intentos: {last_error}")


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


def media_segment_urls(text, base_url, limit=HLS_STABILITY_SEGMENTS):
    urls = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        candidate = None
        if line.startswith("#EXT-X-PART:") or line.startswith("#EXT-X-PRELOAD-HINT:"):
            continue
        if not line.startswith("#"):
            candidate = line
        if not candidate:
            continue
        absolute = urljoin(base_url, candidate)
        if absolute not in seen:
            seen.add(absolute)
            urls.append(absolute)
        if len(urls) >= limit:
            break

    # LL-HLS puede exponer solo PART/PRELOAD en determinados snapshots.
    # Solo los usamos como fallback cuando no hay suficientes segmentos completos.
    if len(urls) < limit:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("#EXT-X-PART:"):
                continue
            match = re.search(r'URI="([^"]+)"', line, re.IGNORECASE)
            if not match:
                continue
            absolute = urljoin(base_url, match.group(1))
            if absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)
            if len(urls) >= limit:
                break

    return urls


def validate_hls_segments(text, base_url):
    segment_urls = media_segment_urls(text, base_url)
    if len(segment_urls) < HLS_STABILITY_SEGMENTS:
        return False, len(segment_urls), (
            f"Playlist HLS solo expuso {len(segment_urls)} segmento(s); "
            f"se requieren {HLS_STABILITY_SEGMENTS}."
        )

    for index, segment_url in enumerate(segment_urls, 1):
        status, content_type, segment, _ = fetch_segment(segment_url)
        if not 200 <= status < 400 or not segment:
            return False, index - 1, f"Segmento {index} inaccesible (HTTP {status})."
        valid, error = valid_direct_payload(segment, content_type)
        if not valid:
            return False, index - 1, f"Segmento {index} inválido: {error}"

    return True, len(segment_urls), None


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



def fetch_segment(url):
    """Prueba Range primero y reintenta GET completo si el servidor no lo soporta."""
    try:
        return fetch(
            url,
            accept="video/*,audio/*,application/octet-stream,*/*",
            limit=SEGMENT_LIMIT,
            extra_headers={"Range": "bytes=0-65535"},
        )
    except HTTPError as error:
        if error.code not in (400, 405, 416, 501):
            raise
    return fetch(
        url,
        accept="video/*,audio/*,application/octet-stream,*/*",
        limit=SEGMENT_LIMIT,
    )


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

                    stable, segment_count, stability_error = validate_hls_segments(child, final_url)
                    if stable:
                        return (
                            {
                                "playback_checked": True,
                                "playback_ok": True,
                                "playback_type": "hls",
                                "playback_error": None,
                                "stability_checked": True,
                                "stability_ok": True,
                                "stable_segments": segment_count,
                                "width": variant["width"],
                                "height": variant["height"],
                                "resolution": (
                                    f'{variant["width"]}x{variant["height"]}'
                                    if variant["width"] and variant["height"]
                                    else None
                                ),
                                "bitrate": variant["bandwidth"],
                                "segment_bytes": None,
                                "variant_index": index,
                                "variant_count": len(variants),
                                "validated_url": final_url,
                            },
                            None,
                        )
                    failures.append(f"variante {index}: {stability_error}")
                except Exception as error:
                    failures.append(f"variante {index}: {error}")

            return None, "Todas las variantes HLS fallaron: " + "; ".join(failures[:8])

        stable, segment_count, stability_error = validate_hls_segments(playlist_text, playlist_url)
        resolution = detect_resolution(playlist_text)
        bandwidth = detect_bandwidth(playlist_text)
        if not stable:
            return (
                {
                    "playback_checked": True,
                    "playback_ok": False,
                    "playback_type": "hls",
                    "playback_error": stability_error,
                    "stability_checked": True,
                    "stability_ok": False,
                    "stable_segments": segment_count,
                    "width": resolution["width"] if resolution else None,
                    "height": resolution["height"] if resolution else None,
                    "resolution": resolution["resolution"] if resolution else None,
                    "bitrate": bandwidth,
                    "segment_bytes": None,
                    "validated_url": playlist_url,
                },
                None,
            )

        return (
            {
                "playback_checked": True,
                "playback_ok": True,
                "playback_type": "hls",
                "playback_error": None,
                "stability_checked": True,
                "stability_ok": True,
                "stable_segments": segment_count,
                "width": resolution["width"] if resolution else None,
                "height": resolution["height"] if resolution else None,
                "resolution": resolution["resolution"] if resolution else None,
                "bitrate": bandwidth,
                "segment_bytes": None,
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
        "stability_checked": True,
        "stability_ok": False,
        "stable_segments": 0,
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
        "stability_checked": False,
        "stability_ok": False,
        "stable_segments": 0,
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

    endpoint_health = {}
    if ENDPOINT_HEALTH_FILE.exists():
        try:
            with ENDPOINT_HEALTH_FILE.open("r", encoding="utf-8-sig") as f:
                endpoint_health = json.load(f)
        except Exception:
            endpoint_health = {}

    # Migración segura del historial: channels.json es la fuente de verdad.
    # Solo se conservan estados que correspondan al endpoint+canal actuales.
    endpoint_metadata = {}
    for channel in channels:
        channel_id = str(channel.get("id") or "").strip()
        channel_key = str(channel.get("channel_key") or "").strip()
        for source in channel.get("sources", []):
            source_url = str(source.get("url") or "").strip()
            if not source_url:
                continue
            stable_key = endpoint_health_key(source_url, channel_id)
            endpoint_metadata[stable_key] = {
                "channel_id": channel_id,
                "channel_name": str(channel.get("name") or "").strip(),
                "channel_key": channel_key,
                "source": str(source.get("source") or "").strip(),
                "priority": int(source.get("priority") or 0),
            }

    compacted_health = {}
    for stable_key, metadata in endpoint_metadata.items():
        candidates = []
        for old_key, old_state in endpoint_health.items():
            old_channel_id = str(old_state.get("channel_id") or "").strip()
            if old_channel_id != metadata["channel_id"]:
                continue
            if endpoint_health_key(old_key, old_channel_id) == stable_key:
                candidates.append(old_state)

        preferred = None
        for old_state in candidates:
            if preferred is None:
                preferred = dict(old_state)
                continue
            preferred_checks = int(preferred.get("checks") or 0)
            old_checks = int(old_state.get("checks") or 0)
            preferred_recency = max(str(preferred.get("last_success") or ""), str(preferred.get("last_failure") or ""))
            old_recency = max(str(old_state.get("last_success") or ""), str(old_state.get("last_failure") or ""))
            if old_checks > preferred_checks or (old_checks == preferred_checks and old_recency > preferred_recency):
                preferred = dict(old_state)

        if preferred is None:
            preferred = {
                "checks": 0, "successes": 0, "failures": 0,
                "consecutive_failures": 0, "last_success": None,
                "last_failure": None, "last_error": None, "quarantine_until": None,
            }
        preferred.update(metadata)
        checks = max(0, int(preferred.get("checks") or 0))
        successes = max(0, int(preferred.get("successes") or 0))
        failures = max(0, int(preferred.get("failures") or 0))
        if successes + failures != checks:
            successes = min(successes, checks)
            failures = max(0, checks - successes)
        preferred["checks"] = checks
        preferred["successes"] = successes
        preferred["failures"] = failures
        preferred["consecutive_failures"] = max(0, int(preferred.get("consecutive_failures") or 0))
        compacted_health[stable_key] = preferred

    endpoint_health = compacted_health
    if any("|" not in str(key) for key in endpoint_health):
        raise SystemExit("INCONSISTENCIA: endpoint_health contiene una clave no canónica.")
    if any(re.search(r"[?&](?:token|jwt|access_token|session|sessionid|sid|deviceid|clientid|nimblesessionid|signature|sig|hmac)=", str(key), re.IGNORECASE) for key in endpoint_health):
        raise SystemExit("INCONSISTENCIA: endpoint_health conserva un parámetro efímero en su clave.")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    tasks = []
    skipped_quarantine = []
    for channel in channels:
        for source in channel.get("sources", []):
            url = str(source.get("url") or "").strip()
            health_key = endpoint_health_key(url, channel.get("id"))
            state = endpoint_health.get(health_key, {})
            until = str(state.get("quarantine_until") or "").strip()
            quarantined = False
            if until:
                try:
                    quarantined = datetime.fromisoformat(until.replace("Z", "+00:00")) > now
                except ValueError:
                    quarantined = False
            if quarantined:
                skipped_quarantine.append((channel, source, state))
            else:
                tasks.append({"channel": channel, "source": source})
    total = len(tasks) + len(skipped_quarantine)

    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - QUALITY + PLAYBACK SCANNER")
    print("=" * 60)
    print(f"Canales: {len(channels)}")
    print(f"URLs:    {total}")
    print(f"Workers: {WORKERS}")

    # Invariantes de entrada: cada candidato debe evaluarse exactamente una vez.
    task_urls = [str(task["source"].get("url") or "").strip() for task in tasks]
    if any(not url.startswith(("http://", "https://")) for url in task_urls):
        raise SystemExit("INCONSISTENCIA: existe un endpoint candidato no HTTP/HTTPS.")
    if len(task_urls) != len(set(task_urls)):
        raise SystemExit("INCONSISTENCIA: channels.json contiene URLs candidatas duplicadas.")
    if any(not str(task["channel"].get("id") or "").strip() for task in tasks):
        raise SystemExit("INCONSISTENCIA: existe un candidato sin channel_id.")

    results = []
    for channel, source, state in skipped_quarantine:
        results.append({
            "channel_id": channel.get("id", ""), "channel_name": channel.get("name", ""),
            "url": str(source.get("url") or "").strip(), "source": source.get("source", ""),
            "source_priority": int(source.get("priority") or 0), "width": None, "height": None,
            "resolution": None, "bitrate": None, "quality_score": 0, "detected": False,
            "playback_checked": False, "playback_ok": False, "playback_type": None,
            "playback_error": "Endpoint en cuarentena por fallos persistentes.",
            "stability_checked": False, "stability_ok": False, "stable_segments": 0,
            "validated_url": None, "variant_index": None, "variant_count": None,
            "error": None, "quarantined": True, "quarantine_until": state.get("quarantine_until"),
            "endpoint_consecutive_failures": int(state.get("consecutive_failures") or 0),
            "endpoint_checks": int(state.get("checks") or 0), "endpoint_successes": int(state.get("successes") or 0),
            "endpoint_failures": int(state.get("failures") or 0),
            "health_score": endpoint_health_score({
                "endpoint_checks": state.get("checks"),
                "endpoint_successes": state.get("successes"),
                "endpoint_failures": state.get("failures"),
                "endpoint_consecutive_failures": state.get("consecutive_failures"),
            }),
        })
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

    from datetime import datetime, timezone, timedelta
    checked_at = datetime.now(timezone.utc).isoformat()
    for result in results:
        url = result["url"]
        health_key = endpoint_health_key(url, result.get("channel_id"))
        state = endpoint_health.setdefault(health_key, {
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
            "quarantine_until": None,
        })
        existing_channel_id = str(state.get("channel_id") or "").strip()
        if existing_channel_id and existing_channel_id != result["channel_id"]:
            raise SystemExit(
                f"INCONSISTENCIA: endpoint {url} cambió de canal "
                f"({existing_channel_id} -> {result['channel_id']})."
            )

        state.update({
            "channel_id": result["channel_id"],
            "channel_name": result["channel_name"],
            "source": result["source"],
            "priority": result["source_priority"],
        })
        # Una fuente en cuarentena no fue comprobada en esta ejecución.
        # No incrementamos checks para evitar falsificar el histórico y para
        # mantener siempre: checks == successes + failures.
        if result.get("quarantined"):
            continue
        state["checks"] = int(state.get("checks") or 0) + 1
        if result["playback_ok"]:
            state["successes"] = int(state.get("successes") or 0) + 1
            state["consecutive_failures"] = 0
            state["last_success"] = checked_at
            state["last_error"] = None
            state["quarantine_until"] = None
        else:
            state["failures"] = int(state.get("failures") or 0) + 1
            state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
            state["last_failure"] = checked_at
            state["last_error"] = result.get("error") or result.get("playback_error")
            if state["consecutive_failures"] >= ENDPOINT_QUARANTINE_AFTER:
                state["quarantine_until"] = (datetime.now(timezone.utc) + timedelta(hours=ENDPOINT_QUARANTINE_HOURS)).isoformat()
        result["endpoint_consecutive_failures"] = state["consecutive_failures"]
        result["endpoint_checks"] = int(state.get("checks") or 0)
        result["endpoint_successes"] = int(state.get("successes") or 0)
        result["endpoint_failures"] = int(state.get("failures") or 0)
        result["health_score"] = endpoint_health_score(result)

    atomic_write_json(ENDPOINT_HEALTH_FILE, endpoint_health)
    if skipped_quarantine:
        print(f"Endpoints en cuarentena: {len(skipped_quarantine)} (se reintentaran al vencer la cuarentena).")

    status_data = {}
    if STATUS_FILE.exists():
        try:
            with STATUS_FILE.open("r", encoding="utf-8-sig") as f:
                status_data = json.load(f)
        except Exception:
            status_data = {}
    status_by_url = {
        str(item.get("url") or "").strip(): item
        for item in status_data.get("results", [])
    }

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
                key=lambda x: quality_key(
                    x,
                    status_by_url.get(str(x.get("url") or "").strip(), {}),
                    x.get("source_priority") or 0,
                ),
            )
            if available
            else None
        )

    output = {
        "schema_version": 4,
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
        "hls_stable": sum(1 for result in results if result["playback_type"] == "hls" and result.get("stability_ok")),
        "hls_stability_segments_required": HLS_STABILITY_SEGMENTS,
        "health_score_average": round(
            sum(float(x.get("health_score") or 0) for x in results) / max(len(results), 1), 2
        ),
        "health_score_healthy": sum(
            1 for x in results if float(x.get("health_score") or 0) >= 80
        ),
        "health_score_degraded": sum(
            1 for x in results if 40 <= float(x.get("health_score") or 0) < 80
        ),
        "health_score_unhealthy": sum(
            1 for x in results if float(x.get("health_score") or 0) < 40
        ),
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

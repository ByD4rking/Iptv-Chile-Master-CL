from __future__ import annotations

"""Independent health/scoring engine for IPTV-CHILE-MAESTRA_CORREGIDO.

This module is diagnostic-first: it never rewrites the playlist and never shares
state with Pluto. It records bounded per-URL history, exponential retry,
cooldown/circuit-breaker state and a deterministic 0-100 score.
"""

import json
import re
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "scripts" / "health"
STATE_FILE = STATE_DIR / "principal_health.json"
MAX_RECORDS = 5000
MAX_HISTORY_SAMPLES = 5
TIMEOUT = (2, 3)
ATTEMPTS = 2
MAX_PROBES_PER_RUN = 600
MAX_VARIANT_CHECKS = 2
FFPROBE_TIMEOUT = 4
MIN_THROUGHPUT_BPS = 128_000
MAX_PLAYLIST_BYTES = 256_000
DEFAULT_WORKERS = 48
COOLDOWN_THRESHOLD = 5
MAX_COOLDOWN = 6 * 60 * 60
UA = "IPTV-Chile-Principal-Health/1.0"


def parse_m3u(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith("#"):
            j += 1
        if j >= len(lines) or not lines[j].startswith(("http://", "https://")):
            continue
        mid = re.search(r'tvg-id="([^"]*)"', line)
        name = re.search(r'tvg-name="([^"]*)"', line)
        group = re.search(r'group-title="([^"]*)"', line)
        out.append({
            "id": mid.group(1).strip() if mid else "",
            "name": name.group(1).strip() if name else "",
            "group": group.group(1).strip() if group else "",
            "url": lines[j].strip(),
        })
    return out


def _read_limited(response: requests.Response, limit: int = MAX_PLAYLIST_BYTES) -> str:
    """Read only a bounded prefix; never download an entire media response."""
    chunks = []
    total = 0
    try:
        for chunk in response.iter_content(16_384):
            if not chunk:
                continue
            remaining = limit - total
            chunks.append(chunk[:remaining])
            total += min(len(chunk), remaining)
            if total >= limit:
                break
    finally:
        response.close()
    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "tls"
    if isinstance(exc, requests.exceptions.ConnectionError):
        if isinstance(getattr(exc, "__cause__", None), socket.gaierror) or "Name or service not known" in str(exc):
            return "dns"
        return "connection"
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return {403:"http-403",404:"http-404",410:"http-410",429:"http-429"}.get(status, f"http-{status}" if status else "http-error")
    return type(exc).__name__


def _ffprobe(url: str) -> dict:
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height,r_frame_rate,bit_rate",
             "-of", "json", url],
            capture_output=True, text=True, timeout=FFPROBE_TIMEOUT, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}
    if proc.returncode != 0:
        return {"ffprobe_error": "decoder-error"}
    try:
        streams = json.loads(proc.stdout).get("streams", [])
        if not streams:
            return {}
        s = streams[0]
        fps = None
        rate = s.get("r_frame_rate")
        if rate and "/" in rate:
            a, b = rate.split("/", 1)
            if float(b):
                fps = round(float(a) / float(b), 3)
        return {
            "codec_observed": s.get("codec_name"),
            "resolution_observed": f'{s["width"]}x{s["height"]}' if s.get("width") and s.get("height") else None,
            "fps_observed": fps,
            "bitrate_observed": int(s["bit_rate"]) if str(s.get("bit_rate", "")).isdigit() else None,
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"ffprobe_error": "decoder-error"}


def _probe_once(url: str) -> dict:
    started = time.monotonic()
    try:
        with requests.Session() as s:
            r = s.get(
                url,
                headers={"User-Agent": UA, "Accept": "*/*"},
                timeout=TIMEOUT,
                stream=True,
            )
            status = r.status_code
            final_url = r.url
            if status >= 400:
                error = {403:"http-403",404:"http-404",410:"http-410",429:"http-429"}.get(status, f"http-{status}" if status >= 500 else "http-error")
                r.close()
                return {"ok": False, "status": status, "latency_ms": round((time.monotonic()-started)*1000), "error": error}
            initial_limit = MAX_PLAYLIST_BYTES if (".m3u8" in url.lower() or "mpegurl" in (r.headers.get("Content-Type", "").lower())) else 16_384
            body = _read_limited(r, initial_limit)

            # Direct media/HTTP sources are validated with only a bounded prefix.
            # The previous implementation could download the entire response,
            # making one slow source stall the whole batch.
            if ".m3u8" not in url.lower() and "#EXTM3U" not in body:
                return {
                    "ok": True,
                    "status": status,
                    "latency_ms": round((time.monotonic()-started)*1000),
                    "kind": "http",
                }
            if "#EXTM3U" not in body:
                return {
                    "ok": False,
                    "status": status,
                    "latency_ms": round((time.monotonic()-started)*1000),
                    "error": "no-m3u8",
                }

            variants = []
            master_lines = body.splitlines()
            for idx, line in enumerate(master_lines):
                if not line.startswith("#EXT-X-STREAM-INF:") or idx + 1 >= len(master_lines):
                    continue
                uri = master_lines[idx + 1].strip()
                if not uri or uri.startswith("#"):
                    continue
                attrs = line.split(":", 1)[1]
                rm = re.search(r"RESOLUTION=(\d+x\d+)", attrs)
                bm = re.search(r"BANDWIDTH=(\d+)", attrs)
                cm = re.search(r'CODECS="([^"]+)"', attrs)
                fm = re.search(r"FRAME-RATE=([0-9.]+)", attrs)
                variants.append({
                    "resolution": rm.group(1) if rm else None,
                    "bandwidth": int(bm.group(1)) if bm else None,
                    "codecs": cm.group(1) if cm else None,
                    "fps": float(fm.group(1)) if fm else None,
                    "url": urljoin(final_url, uri),
                })

            variants.sort(key=lambda x: (x.get("bandwidth") or 0), reverse=True)
            variants = variants[:MAX_VARIANT_CHECKS] or [{
                "resolution": None, "bandwidth": None, "codecs": None,
                "fps": None, "url": final_url,
            }]

            last_variant_error = "no-segment"
            for variant_meta in variants:
                variant = variant_meta["url"]
                vbody = body
                if variant != final_url:
                    try:
                        vr = s.get(variant, headers={"User-Agent": UA}, timeout=TIMEOUT, stream=True)
                        vr.raise_for_status()
                        vbody = _read_limited(vr)
                    except Exception as exc:
                        last_variant_error = _classify_error(exc)
                        continue

                segment = next(
                    (
                        urljoin(variant, x.strip())
                        for x in vbody.splitlines()
                        if x.strip() and not x.startswith("#")
                    ),
                    None,
                )
                if not segment:
                    last_variant_error = "no-segment"
                    continue

                sr_started = time.monotonic()
                try:
                    sr = s.get(segment, headers={"User-Agent": UA}, timeout=TIMEOUT, stream=True)
                    if sr.status_code >= 400:
                        last_variant_error = {403:"http-403",404:"http-404",410:"http-410",429:"http-429"}.get(
                            sr.status_code, f"http-{sr.status_code}" if sr.status_code >= 500 else "http-error"
                        )
                        sr.close()
                        continue
                    sample = next(sr.iter_content(64 * 1024), b"")
                    elapsed = max(time.monotonic() - sr_started, 0.001)
                    throughput_bps = round(len(sample) * 8 / elapsed)
                    sr.close()
                except Exception as exc:
                    last_variant_error = _classify_error(exc)
                    continue

                if not sample:
                    last_variant_error = "empty-segment"
                    continue
                if throughput_bps < MIN_THROUGHPUT_BPS:
                    last_variant_error = "low-throughput"
                    continue

                observed = _ffprobe(variant)
                variant_meta = {k: v for k, v in variant_meta.items() if k != "url"}
                return {
                    "ok": True,
                    "status": status,
                    "latency_ms": round((time.monotonic()-started)*1000),
                    "kind": "hls",
                    **variant_meta,
                    "throughput_bps": throughput_bps,
                    "variants_checked": len(variants),
                    **observed,
                }

            return {
                "ok": False,
                "status": status,
                "latency_ms": round((time.monotonic()-started)*1000),
                "error": last_variant_error,
                "variants_checked": len(variants),
            }

    except Exception as exc:
        return {"ok": False, "latency_ms": None, "error": _classify_error(exc)}


def _probe(url: str) -> dict:
    last = {"ok": False, "latency_ms": None, "error": "sin intento"}
    for attempt in range(1, ATTEMPTS + 1):
        last = _probe_once(url)
        if last.get("ok"):
            last["attempts"] = attempt
            return last
        if attempt < ATTEMPTS:
            time.sleep(min(8.0, 1.0 * (2 ** (attempt - 1))))
    last["attempts"] = ATTEMPTS
    return last


def _score(result: dict, previous: dict, failures: int) -> int:
    availability = 100 if result.get("ok") else 0
    history = previous.get("history", []) if isinstance(previous, dict) else []
    recent = [x for x in history[-MAX_HISTORY_SAMPLES:] if isinstance(x, dict)]
    stability = round(sum(1 for x in recent if x.get("ok") is True) / len(recent) * 100) if recent else (100 if result.get("ok") else 0)
    if not result.get("ok"):
        stability = min(stability, max(0, 100 - min(100, failures * 20)))
    latency = result.get("latency_ms")
    latency_score = 100 if latency is None and result.get("ok") else (0 if latency is None else 100 if latency <= 250 else 85 if latency <= 500 else 70 if latency <= 1000 else 50 if latency <= 2000 else 25)
    continuity = 100 if result.get("kind") == "hls" else 80 if result.get("ok") else 20
    resolution = result.get("resolution_observed") or result.get("resolution") or ""
    quality = {"3840x2160":100,"2560x1440":95,"1920x1080":90,"1280x720":75,"854x480":55}.get(resolution, 45 if resolution else 20)
    bitrate = result.get("bitrate_observed") or result.get("bandwidth") or 0
    if bitrate >= 5_000_000: quality += 10
    elif bitrate >= 2_500_000: quality += 5
    if result.get("fps_observed") is not None and result["fps_observed"] >= 25: quality += 5
    if result.get("throughput_bps") is not None:
        if result["throughput_bps"] < MIN_THROUGHPUT_BPS * 2: quality -= 15
        elif result["throughput_bps"] >= 2_000_000: quality += 5
    if result.get("codec_observed") in {"h264", "hevc", "av1", "vp9"}: quality += 5
    quality = max(0, min(100, quality))
    return max(0, min(100, round(availability * 0.25 + stability * 0.30 + continuity * 0.15 + latency_score * 0.15 + quality * 0.15)))


def _cooldown(failures: int) -> int:
    if failures < COOLDOWN_THRESHOLD:
        return 0
    return min(MAX_COOLDOWN, 60 * (2 ** min(8, failures - COOLDOWN_THRESHOLD)))


def _cooldown_active(previous: dict, now: int) -> bool:
    if not isinstance(previous, dict):
        return False
    try:
        return int(previous.get("cooldown_until", 0) or 0) > now
    except (TypeError, ValueError):
        return False


def _aggregate(history: list[dict]) -> dict:
    rows = [x for x in history if isinstance(x, dict)]
    latencies = sorted(x["latency_ms"] for x in rows if isinstance(x.get("latency_ms"), (int, float)))
    successes = sum(1 for x in rows if x.get("ok") is True)
    def pct(p):
        if not latencies:
            return None
        idx = min(len(latencies)-1, max(0, round((p/100)*(len(latencies)-1))))
        return latencies[idx]
    current = longest = 0
    for x in rows:
        if x.get("ok") is True:
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return {
        "total_checks": len(rows),
        "successful_checks": successes,
        "failed_checks": len(rows) - successes,
        "uptime_ratio": round(successes / len(rows) * 100, 2) if rows else None,
        "latency_p50_ms": pct(50),
        "latency_p95_ms": pct(95),
        "latency_p99_ms": pct(99),
        "current_failure_streak": current,
        "longest_failure_streak": longest,
    }


def run(path: Path | None = None, workers: int = DEFAULT_WORKERS) -> dict:
    playlist = path or ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
    entries = parse_m3u(playlist)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    except Exception:
        state = {}

    now = int(time.time())
    results = {}
    unique = {}
    for e in entries:
        if e["url"] not in unique:
            unique[e["url"]] = e

    candidates = []
    skipped_cooldown = 0
    for url, entry in unique.items():
        previous = state.get(url, {})
        if _cooldown_active(previous, now):
            results[url] = {
                **previous,
                "channel": entry["name"],
                "channel_id": entry["id"],
                "state": "COOLDOWN",
                "skipped_cooldown": True,
            }
            skipped_cooldown += 1
            continue

        try:
            failures = int(previous.get("consecutive_failures", 0) or 0)
        except (TypeError, ValueError):
            failures = 0
        try:
            last_checked = int(previous.get("checked_at", 0) or 0)
        except (TypeError, ValueError):
            last_checked = 0

        # Prioridad: fuentes con fallos primero, después fuentes nunca
        # comprobadas y finalmente las más antiguas. Esto convierte el
        # Health Score en un muestreo rotativo y evita bloquear el workflow
        # intentando comprobar miles de URLs en una sola ejecución.
        priority = 0 if failures > 0 else 1 if last_checked == 0 else 2
        candidates.append((priority, last_checked, url, entry))

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = candidates[:MAX_PROBES_PER_RUN]
    to_probe = {url: entry for _, _, url, entry in selected}
    deferred = len(candidates) - len(selected)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_probe, url): url for url in to_probe}
        completed = 0
        for future in as_completed(futures):
            url = futures[future]
            result = future.result()
            previous = state.get(url, {})
            failures = 0 if result.get("ok") else int(previous.get("consecutive_failures", 0)) + 1
            cooldown = _cooldown(failures)
            samples = list(previous.get("history", [])) if isinstance(previous.get("history", []), list) else []
            samples.append({"checked_at": now, "ok": bool(result.get("ok")), "latency_ms": result.get("latency_ms"), "health_score": _score(result, previous, failures)})
            samples = samples[-MAX_HISTORY_SAMPLES:]
            aggregate = _aggregate(samples)
            previous_failures = int(previous.get("consecutive_failures", 0) or 0)
            previous_successes = int(previous.get("consecutive_successes", 0) or 0)
            successes = previous_successes + 1 if result.get("ok") else 0
            if result.get("ok") and previous_failures > 0:
                state_name = "RECOVERING"
            elif result.get("ok"):
                state_name = "HEALTHY"
            elif failures >= COOLDOWN_THRESHOLD:
                state_name = "DEAD"
            elif failures >= 2:
                state_name = "SUSPECT"
            else:
                state_name = "DEGRADED"
            results[url] = {
                **result,
                "channel": unique[url]["name"],
                "channel_id": unique[url]["id"],
                "consecutive_failures": failures,
                "consecutive_successes": successes,
                "health_score": _score(result, previous, failures),
                "history": samples,
                "aggregate": aggregate,
                "state": "COOLDOWN" if cooldown else state_name,
                "cooldown_until": now + cooldown if cooldown else 0,
                "checked_at": now,
            }
            completed += 1
            if completed % 100 == 0 or completed == len(to_probe):
                print(f"Health Score progreso: {completed}/{len(to_probe)} sondeos completados", flush=True)

    # Persistencia completa y acotada: las fuentes diferidas NO se pierden.
    # El muestreo rotativo conserva memoria real entre ejecuciones.
    for url, entry in unique.items():
        if url not in results:
            previous = state.get(url, {})
            if not isinstance(previous, dict):
                previous = {}
            results[url] = {
                **previous,
                "channel": entry["name"],
                "channel_id": entry["id"],
                "state": "COOLDOWN" if _cooldown_active(previous, now) else previous.get("state", "UNTESTED"),
            }

    if len(results) > MAX_RECORDS:
        results = dict(sorted(
            results.items(),
            key=lambda kv: (kv[1].get("checked_at", 0), kv[0]),
            reverse=True,
        )[:MAX_RECORDS])

    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)

    ok = sum(1 for x in results.values() if x.get("ok") is True)
    failed = sum(1 for x in results.values() if x.get("ok") is False)
    cooldown = sum(1 for x in results.values() if x.get("state") == "COOLDOWN")
    return {
        "total_unique": len(unique),
        "checked": len(results),
        "probed": len(to_probe),
        "deferred": deferred,
        "skipped_cooldown": skipped_cooldown,
        "ok": ok,
        "failed": failed,
        "cooldown": cooldown,
        "state": str(STATE_FILE),
    }


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(run(target), ensure_ascii=False, indent=2))

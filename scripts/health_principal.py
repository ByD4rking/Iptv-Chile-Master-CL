from __future__ import annotations

"""Independent health/scoring engine for IPTV-CHILE-MAESTRA_CORREGIDO.

This module is diagnostic-first: it never rewrites the playlist and never shares
state with Pluto. It records bounded per-URL history, exponential retry,
cooldown/circuit-breaker state and a deterministic 0-100 score.
"""

import json
import re
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


def _probe_once(url: str) -> dict:
    started = time.monotonic()
    try:
        with requests.Session() as s:
            r = s.get(url, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=TIMEOUT)
            status = r.status_code
            r.raise_for_status()
            body = r.text[:1_000_000]
            if ".m3u8" not in url.lower() and "#EXTM3U" not in body:
                return {"ok": True, "status": status, "latency_ms": round((time.monotonic()-started)*1000), "kind": "http"}
            if "#EXTM3U" not in body:
                return {"ok": False, "status": status, "latency_ms": round((time.monotonic()-started)*1000), "error": "no-m3u8"}
            variant = r.url
            vbody = body
            best_variant = {"resolution": None, "bandwidth": None, "codecs": None, "fps": None, "url": None}
            master_lines = vbody.splitlines()
            for idx, line in enumerate(master_lines):
                if line.startswith("#EXT-X-STREAM-INF:") and idx + 1 < len(master_lines):
                    attrs = line.split(":", 1)[1]
                    rm = re.search(r"RESOLUTION=(\d+x\d+)", attrs)
                    bm = re.search(r"BANDWIDTH=(\d+)", attrs)
                    cm = re.search(r'CODECS="([^"]+)"', attrs)
                    fm = re.search(r"FRAME-RATE=([0-9.]+)", attrs)
                    candidate = {"resolution": rm.group(1) if rm else None, "bandwidth": int(bm.group(1)) if bm else None, "codecs": cm.group(1) if cm else None, "fps": float(fm.group(1)) if fm else None}
                    candidate["url"] = urljoin(r.url, master_lines[idx + 1].strip())
                    if (candidate["bandwidth"] or 0) > (best_variant["bandwidth"] or 0):
                        best_variant = candidate
            if best_variant.get("url"):
                variant = best_variant["url"]
                vr = s.get(variant, headers={"User-Agent": UA}, timeout=TIMEOUT)
                vr.raise_for_status()
                vbody = vr.text[:1_000_000]
            segment = next((urljoin(variant, x.strip()) for x in vbody.splitlines()
                            if x.strip() and not x.startswith("#")), None)
            if not segment:
                return {"ok": False, "status": status, "latency_ms": round((time.monotonic()-started)*1000), "error": "no-segment"}
            sr = s.get(segment, headers={"User-Agent": UA}, timeout=TIMEOUT, stream=True)
            sr.raise_for_status()
            sample = next(sr.iter_content(4096), b"")
            sr.close()
            if not sample:
                return {"ok": False, "status": status, "latency_ms": round((time.monotonic()-started)*1000), "error": "empty-segment"}
            best_variant.pop("url", None)
            return {"ok": True, "status": status, "latency_ms": round((time.monotonic()-started)*1000), "kind": "hls", **best_variant}
    except Exception as exc:
        return {"ok": False, "latency_ms": None, "error": type(exc).__name__}


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

    # Historical stability uses bounded recent history instead of only the
    # current consecutive-failure counter. This prevents a single recovery
    # probe from immediately restoring a perfect stability score.
    history = previous.get("history", []) if isinstance(previous, dict) else []
    recent = [x for x in history[-MAX_HISTORY_SAMPLES:] if isinstance(x, dict)]
    if recent:
        success_count = sum(1 for x in recent if x.get("ok") is True)
        stability = round((success_count / len(recent)) * 100)
    else:
        stability = 100 if result.get("ok") else 0

    if not result.get("ok"):
        stability = min(stability, max(0, 100 - min(100, failures * 20)))
    latency = result.get("latency_ms")
    latency_score = 100 if latency is None and result.get("ok") else (
        0 if latency is None else
        100 if latency <= 250 else 85 if latency <= 500 else 70 if latency <= 1000 else 50 if latency <= 2000 else 25
    )
    continuity = 100 if result.get("kind") == "hls" else 80 if result.get("ok") else 20
    quality = 20
    resolution = result.get("resolution") or ""
    if "3840x2160" == resolution: quality = 100
    elif "2560x1440" == resolution: quality = 95
    elif "1920x1080" == resolution: quality = 90
    elif "1280x720" == resolution: quality = 75
    elif "854x480" == resolution: quality = 55
    elif resolution: quality = 45
    if result.get("bandwidth"):
        quality = min(100, quality + (10 if result["bandwidth"] >= 5000000 else 5 if result["bandwidth"] >= 2500000 else 0))
    return max(0, min(100, round(
        availability * 0.25 + stability * 0.30 + continuity * 0.15 + latency_score * 0.15 + quality * 0.15
    )))


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
            results[url] = {
                **result,
                "channel": unique[url]["name"],
                "channel_id": unique[url]["id"],
                "consecutive_failures": failures,
                "health_score": _score(result, previous, failures),
                "history": samples,
                "state": "COOLDOWN" if cooldown else ("HEALTHY" if result.get("ok") else "DEGRADED"),
                "cooldown_until": now + cooldown if cooldown else 0,
                "checked_at": now,
            }
            completed += 1
            if completed % 100 == 0 or completed == len(to_probe):
                print(f"Health Score progreso: {completed}/{len(to_probe)} sondeos completados", flush=True)

    # Bounded persistence: current URLs only, capped deterministically.
    if len(results) > MAX_RECORDS:
        results = dict(sorted(results.items(), key=lambda kv: kv[1].get("checked_at", 0), reverse=True)[:MAX_RECORDS])
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

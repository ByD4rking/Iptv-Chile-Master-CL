from __future__ import annotations

"""Real HLS playback probe for Pluto streams.

The probe is deliberately conservative: failures are recorded, not used to
delete previously published channels. A transient outage therefore cannot
erase the catalog.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests


OUTPUT = Path(__file__).resolve().parent.parent / "output" / "health"
HISTORY = OUTPUT / "streams.json"
TIMEOUT = (8, 15)
ATTEMPTS = 3
USER_AGENT = "Mozilla/5.0 Pluto-HLS-Health/1.0"


def _uri_attribute(line: str) -> str:
    match = re.search(r'URI="([^"]+)"', line)
    return match.group(1).strip() if match else ""


def _playlist_uri_candidates(body: str, base_url: str) -> list[str]:
    candidates = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("#EXT-X-PART:", "#EXT-X-PRELOAD-HINT:", "#EXT-X-MAP:")):
            uri = _uri_attribute(line)
            if uri:
                candidates.append(urljoin(base_url, uri))
            continue
        if not line.startswith("#"):
            candidates.append(urljoin(base_url, line))
    return candidates


def _segment_signature_ok(sample: bytes, content_type: str) -> bool:
    if not sample:
        return False
    if len(sample) > 1 and sample[0] == 0x47:
        return True
    if len(sample) >= 8 and sample[4:8] in {b"ftyp", b"styp", b"moof"}:
        return True
    if len(sample) >= 2 and sample[0] == 0xFF and (sample[1] & 0xF6) == 0xF0:
        return True
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    return media_type in {
        "video/mp2t", "video/mp4", "audio/aac", "audio/mp4",
        "application/mp4", "application/octet-stream",
    }


def _probe_once(url: str) -> tuple[bool, str, float]:
    started = time.monotonic()
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    with requests.Session() as session:
        response = session.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        body = response.text[:2_000_000]
        if "#EXTM3U" not in body:
            return False, "respuesta no es M3U8", time.monotonic() - started
        if "#EXT-X-" not in body:
            return False, "M3U8 sin etiquetas HLS", time.monotonic() - started

        variant = response.url
        vbody = body
        for _ in range(3):
            lines = vbody.splitlines()
            nested = []
            for i, line in enumerate(lines):
                if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                    candidate = lines[i + 1].strip()
                    if candidate and not candidate.startswith("#"):
                        nested.append(urljoin(variant, candidate))
            if not nested:
                break
            variant = nested[0]
            vr = session.get(variant, headers=headers, timeout=TIMEOUT)
            vr.raise_for_status()
            vbody = vr.text[:2_000_000]

        candidates = _playlist_uri_candidates(vbody, variant)
        if not candidates:
            return False, "playlist sin segmento", time.monotonic() - started

        segment = candidates[0]
        if not segment.lower().startswith(("http://", "https://")):
            return False, "segmento con esquema no permitido", time.monotonic() - started

        sr = session.get(segment, headers=headers, timeout=TIMEOUT, stream=True)
        sr.raise_for_status()
        sample = next(sr.iter_content(8192), b"")
        content_type = sr.headers.get("Content-Type", "")
        sr.close()
        if not sample:
            return False, "segmento vacío", time.monotonic() - started
        if not _segment_signature_ok(sample, content_type):
            return (
                False,
                f"segmento no reconocible (Content-Type={content_type or 'desconocido'})",
                time.monotonic() - started,
            )
        return True, "master+variant+segment+media OK", time.monotonic() - started


def _safe_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        return f"HTTP {status}"
    return type(exc).__name__


def probe(url: str) -> dict:
    last = "sin intento"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            ok, message, latency = _probe_once(url)
            if ok:
                return {"ok": True, "message": message, "latency_ms": round(latency * 1000), "attempts": attempt}
            last = message
        except Exception as exc:
            last = _safe_error(exc)
        if attempt < ATTEMPTS:
            time.sleep(1.5 * attempt)
    return {"ok": False, "message": last, "latency_ms": None, "attempts": ATTEMPTS}


def audit(channels: list[dict], workers: int = 12) -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    old = {}
    if HISTORY.exists():
        try:
            old = json.loads(HISTORY.read_text(encoding="utf-8"))
        except Exception:
            old = {}

    now = int(time.time())
    results = {}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(probe, str(ch.get("stream") or "")): str(ch.get("health_key") or ch.get("id") or ch.get("name") or "")
            for ch in channels
            if ch.get("stream")
        }
        for future in as_completed(futures):
            key = futures[future]
            result = future.result()
            previous = old.get(key, {})
            failures = 0 if result["ok"] else int(previous.get("consecutive_failures", 0)) + 1
            if result["ok"]:
                failures = 0
            results[key] = {
                **result,
                "consecutive_failures": failures,
                "checked_at": now,
            }

    # Bound the persisted history so it cannot grow without limit. Keep only
    # the latest record per currently audited channel; consecutive failures are
    # carried forward from the previous run.
    tmp = HISTORY.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(HISTORY)
    ok = sum(1 for x in results.values() if x.get("ok"))
    failed = len(results) - ok
    return {"checked": len(results), "ok": ok, "failed": failed, "history": str(HISTORY)}


if __name__ == "__main__":
    print("health.py debe invocarse desde el generador con un catálogo.")

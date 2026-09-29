from __future__ import annotations

"""Real HLS playback probe for Pluto streams.

The probe is deliberately conservative: failures are recorded, not used to
delete previously published channels. A transient outage therefore cannot
erase the catalog.
"""

import json
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

        variants = []
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                candidate = lines[i + 1].strip()
                if candidate and not candidate.startswith("#"):
                    variants.append(urljoin(response.url, candidate))

        if variants:
            variant = variants[0]
            vr = session.get(variant, headers=headers, timeout=TIMEOUT)
            vr.raise_for_status()
            vbody = vr.text[:2_000_000]
        else:
            variant = response.url
            vbody = body

        if "#EXTINF:" not in vbody:
            # A nested master is acceptable; follow its first variant once.
            nested = []
            vlines = vbody.splitlines()
            for i, line in enumerate(vlines):
                if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(vlines):
                    candidate = vlines[i + 1].strip()
                    if candidate and not candidate.startswith("#"):
                        nested.append(urljoin(variant, candidate))
            if nested:
                nr = session.get(nested[0], headers=headers, timeout=TIMEOUT)
                nr.raise_for_status()
                vbody = nr.text[:2_000_000]
                variant = nr.url

        segment = None
        for line in vbody.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                segment = urljoin(variant, line)
                break
        if not segment:
            return False, "playlist sin segmento", time.monotonic() - started
        segment_lower = segment.lower()
        if not segment_lower.startswith(("http://", "https://")):
            return False, "segmento con esquema no permitido", time.monotonic() - started

        sr = session.get(segment, headers=headers, timeout=TIMEOUT, stream=True)
        sr.raise_for_status()
        sample = next(sr.iter_content(8192), b"")
        sr.close()
        if not sample:
            return False, "segmento vacío", time.monotonic() - started
        # MPEG-TS commonly starts with sync byte 0x47; fMP4 starts with an ISO BMFF box.
        looks_ts = len(sample) > 1 and sample[0] == 0x47
        looks_mp4 = len(sample) >= 8 and sample[4:8] in {b"ftyp", b"styp", b"moof"}
        if not (looks_ts or looks_mp4):
            return False, "segmento sin firma TS/fMP4 reconocible", time.monotonic() - started

        return True, "master+variant+segment+firma OK", time.monotonic() - started


def probe(url: str) -> dict:
    last = "sin intento"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            ok, message, latency = _probe_once(url)
            if ok:
                return {"ok": True, "message": message, "latency_ms": round(latency * 1000), "attempts": attempt}
            last = message
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
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

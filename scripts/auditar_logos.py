#!/usr/bin/env python3
"""Audita logos de la playlist principal sin modificarlos ni borrar canales.

La auditoría separa imágenes accesibles, fallos confirmados y errores transitorios.
Nunca cambia tvg-logo/logo: una respuesta de red no prueba que el televisor pueda
renderizar la imagen y no debe provocar sustituciones automáticas.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PLAYLIST = Path("IPTV-CHILE-MAESTRA_CORREGIDO.m3u")
REPORT = Path("logo-audit-report.json")
USER_AGENT = "Mozilla/5.0 (compatible; IPTVLogoAudit/1.0)"
TIMEOUT = 12
RETRIES = 2
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"RIFF", "webp"),
)

def parse_playlist(text: str):
    rows = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.startswith("#EXTINF"):
            continue
        name = line.split(",", 1)[1].strip() if "," in line else "(sin nombre)"
        group = re.search(r'group-title="([^"]*)"', line, re.I)
        logo = re.search(r'(?:tvg-logo|(?<![\w-])logo)="([^"]*)"', line, re.I)
        rows.append({
            "line": line_no,
            "name": name,
            "group": group.group(1) if group else "(sin categoría)",
            "logo": logo.group(1).strip() if logo else "",
        })
    return rows

def _check_once(url: str):
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return {"status": "invalid_url", "detail": "URL no HTTP(S)"}
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Range": "bytes=0-8191",
    })
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            status = getattr(response, "status", 200)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            data = response.read(8192)
            if status not in (200, 206):
                return {"status": "inconclusive", "detail": f"HTTP {status}"}
            if not data:
                return {"status": "broken", "detail": "respuesta vacía"}
            if content_type.startswith("image/"):
                fmt = "svg" if "svg" in content_type else content_type.removeprefix("image/")
                return {"status": "ok", "detail": f"{status} {content_type}", "format": fmt}
            if any(data.startswith(sig) for sig, _ in IMAGE_SIGNATURES):
                fmt = next(fmt for sig, fmt in IMAGE_SIGNATURES if data.startswith(sig))
                if fmt == "webp" and data[8:12] != b"WEBP":
                    return {"status": "broken", "detail": "RIFF no es WebP"}
                return {"status": "ok", "detail": f"{status} firma {fmt}", "format": fmt}
            return {"status": "broken", "detail": f"contenido no imagen ({content_type or 'sin MIME'})"}
    except HTTPError as exc:
        if exc.code in (404, 410):
            return {"status": "broken", "detail": f"HTTP {exc.code}"}
        if exc.code in (401, 403):
            return {"status": "inconclusive", "detail": f"HTTP {exc.code} (bloqueo de acceso; no confirma que la imagen esté rota)"}
        return {"status": "inconclusive", "detail": f"HTTP {exc.code}"}
    except (URLError, TimeoutError, OSError) as exc:
        return {"status": "inconclusive", "detail": str(exc)[:180]}

def check_url(url: str):
    last = None
    for attempt in range(RETRIES + 1):
        last = _check_once(url)
        if last["status"] != "inconclusive" or attempt == RETRIES:
            return last
        time.sleep(1.5 * (attempt + 1))
    return last

def audit(text: str, checker=check_url):
    rows = parse_playlist(text)
    missing = [r for r in rows if not r["logo"]]
    by_url = {}
    for row in rows:
        if row["logo"]:
            by_url.setdefault(row["logo"], []).append(row)
    results = []
    urls = list(by_url)
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(checker, url): url for url in urls}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"status": "inconclusive", "detail": str(exc)[:180]}
            results.append({
                "url": url,
                "channels": [{"name": r["name"], "group": r["group"], "line": r["line"]} for r in by_url[url]],
                **result,
            })
    results.sort(key=lambda x: (x["status"], x["url"]))
    counts = Counter(item["status"] for item in results)
    return {
        "playlist": str(PLAYLIST),
        "channels": len(rows),
        "unique_logo_urls": len(urls),
        "missing_logo_entries": missing,
        "logo_urls": dict(counts),
        "results": results,
        "policy": "Solo auditoría: no modifica M3U, logos, nombres, categorías ni streams.",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", default=str(PLAYLIST))
    parser.add_argument("--report", default=str(REPORT))
    args = parser.parse_args()
    path = Path(args.playlist)
    if not path.is_file():
        print(f"[LOGOS] No existe la playlist: {path}", file=sys.stderr)
        return 2
    result = audit(path.read_text(encoding="utf-8", errors="replace"))
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = result["logo_urls"]
    print(
        f"[LOGOS] canales={result['channels']} URLs únicas={result['unique_logo_urls']} "
        f"accesibles={counts.get('ok', 0)} rotas_confirmadas={counts.get('broken', 0)} "
        f"sin_confirmar={counts.get('inconclusive', 0)} "
        f"sin_logo={len(result['missing_logo_entries'])}"
    )
    print(f"[LOGOS] Informe: {args.report}; la M3U no fue modificada.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audita accesibilidad real de los logos M3U sin modificar ni borrar canales."""
from __future__ import annotations
import argparse, concurrent.futures, re, time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit
import requests

ATTR = re.compile(r'\b(tvg-logo|logo)="([^"]*)"')
USER_AGENT = "IPTV-Chile-Master-LogoAudit/1.0"

def parse_playlist(path: Path):
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        if not line.startswith("#EXTINF:"):
            continue
        attrs = {key: value for key, value in ATTR.findall(line)}
        logo = attrs.get("tvg-logo") or attrs.get("logo") or ""
        group = re.search(r'\bgroup-title="([^"]*)"', line)
        name = line.split(",", 1)[1].strip() if "," in line else "(sin nombre)"
        rows.append({"line": number, "name": name, "group": group.group(1) if group else "(sin categoría)", "logo": logo})
    return rows

def probe(url: str):
    host = urlsplit(url).netloc.lower()
    if host in ("dummyimage.com", "placehold.co", "via.placeholder.com"):
        return ("PLACEHOLDER", 200, "image/png", host, "imagen genérica, no es el logo del canal")
    last = None
    for attempt in range(2):
        try:
            headers = {"User-Agent": USER_AGENT}
            if attempt == 0:
                headers["Range"] = "bytes=0-2047"
            with requests.get(url, headers=headers,
                             timeout=(6, 12), allow_redirects=True, stream=True) as response:
                status = response.status_code
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                final_host = urlsplit(response.url).netloc
                if status in (404, 410):
                    last = ("BROKEN", status, content_type, final_host, "HTTP no encontrado")
                    if attempt == 0:
                        time.sleep(0.35)
                        continue
                    return last
                if status in (401, 403, 408, 425, 429) or status >= 500:
                    return ("INCONCLUSIVE", status, content_type, final_host, "bloqueo, límite o error temporal")
                if status not in (200, 206):
                    return ("INCONCLUSIVE", status, content_type, final_host, "respuesta HTTP no concluyente")
                if content_type.startswith("image/") or content_type in ("application/octet-stream", "binary/octet-stream"):
                    return ("OK", status, content_type, final_host, "")
                return ("INCONCLUSIVE", status, content_type, final_host, "el servidor no declara contenido de imagen")
        except requests.RequestException as exc:
            last = ("INCONCLUSIVE", "ERROR", "", urlsplit(url).netloc, type(exc).__name__)
            if attempt == 0:
                time.sleep(0.35)
    return last

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--m3u", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    rows = parse_playlist(Path(args.m3u))
    by_url = defaultdict(list)
    missing = []
    for row in rows:
        if row["logo"].startswith(("http://", "https://")):
            by_url[row["logo"]].append(row)
        else:
            missing.append(row)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, 24))) as pool:
        futures = {pool.submit(probe, url): url for url in by_url}
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
    counts = Counter(result[0] for result in results.values())
    category_counts = defaultdict(Counter)
    broken_rows, inconclusive_rows, placeholder_rows = [], [], []
    for url, linked_rows in by_url.items():
        status = results[url][0]
        for row in linked_rows:
            category_counts[row["group"]][status] += 1
            if status == "BROKEN":
                broken_rows.append((row, results[url]))
            elif status == "INCONCLUSIVE":
                inconclusive_rows.append((row, results[url]))
            elif status == "PLACEHOLDER":
                placeholder_rows.append((row, results[url]))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = [
        "# Auditoría de logos de la playlist principal", "",
        f"- Canales: **{len(rows)}**",
        f"- URLs únicas revisadas: **{len(by_url)}**",
        f"- Canales sin URL de logo: **{len(missing)}**",
        f"- URLs correctas: **{counts['OK']}**",
        f"- URLs confirmadas como rotas (404/410 repetido): **{counts['BROKEN']}**",
        f"- URLs no concluyentes (403, 429, 5xx, bloqueo o tipo ambiguo): **{counts['INCONCLUSIVE']}**", "",
        "> Esta auditoría no modifica ni elimina logos. Los fallos temporales o bloqueos no se clasifican como enlaces rotos.", "",
        "## Resultado por categoría", "",
        "| Categoría | OK | Rotas confirmadas | No concluyentes |",
        "|---|---:|---:|---:|",
    ]
    for group, values in sorted(category_counts.items()):
        report.append(f"| {group} | {values['OK']} | {values['BROKEN']} | {values['INCONCLUSIVE']} |")
    report += ["", "## Enlaces confirmados como rotos", ""]
    if not broken_rows:
        report.append("No se detectaron respuestas 404/410 repetidas.")
    else:
        for row, result in sorted(broken_rows, key=lambda item: (item[0]["group"], item[0]["name"])):
            report.append(f"- **{row['group']} / {row['name']}** — HTTP {result[1]} — {row['logo']}")
    report += ["", "## Enlaces no concluyentes (no reemplazar automáticamente)", ""]
    if not inconclusive_rows:
        report.append("No hay enlaces no concluyentes.")
    else:
        for row, result in sorted(inconclusive_rows, key=lambda item: (item[0]["group"], item[0]["name"])):
            report.append(f"- **{row['group']} / {row['name']}** — {result[1]} {result[2]} ({result[4]}) — {row['logo']}")
    report += ["", "## Canales sin URL de logo", ""]
    if not missing:
        report.append("Todos los canales tienen una URL de logo.")
    else:
        for row in missing:
            report.append(f"- **{row['group']} / {row['name']}** (línea {row['line']})")
    output.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Canales: {len(rows)} | URLs únicas: {len(by_url)} | OK: {counts['OK']} | rotas confirmadas: {counts['BROKEN']} | no concluyentes: {counts['INCONCLUSIVE']} | sin logo: {len(missing)}")
    print(f"Reporte: {output}")

if __name__ == "__main__":
    main()

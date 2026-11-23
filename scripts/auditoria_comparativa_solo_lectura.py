#!/usr/bin/env python3
"""Comparación M3U de solo lectura: logos y clasificación de errores.

No modifica playlists, no realiza peticiones de red y no publica resultados.
El informe se escribe en stdout salvo que se indique --output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.casefold()).strip()


def attr(line: str, name: str) -> str:
    match = re.search(r"(?<![\w-])" + re.escape(name) + r'="([^"]*)"', line, re.I)
    return match.group(1).strip() if match else ""


def parse_playlist(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    current = None
    duplicates = defaultdict(int)
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            name = line.rsplit(",", 1)[-1].strip() if "," in line else ""
            tvg_name = attr(line, "tvg-name") or name
            tvg_id = attr(line, "tvg-id")
            channel_id = attr(line, "channelId")
            group = attr(line, "group-title")
            identity = (
                "tvg-id:" + norm(tvg_id) if tvg_id else
                "channel-id:" + norm(channel_id) if channel_id else
                "name-group:" + norm(tvg_name) + "|" + norm(group)
            )
            duplicates[identity] += 1
            key = identity if duplicates[identity] == 1 else f"{identity}#{duplicates[identity]}"
            current = {
                "key": key, "name": name, "tvg_name": tvg_name, "group": group,
                "tvg_logo": attr(line, "tvg-logo"), "legacy_logo": attr(line, "logo"),
                "line": line_no,
            }
        elif current and line and not line.startswith("#"):
            current["stream_url"] = line
            records[current["key"]] = current
            current = None
    return records


def compare(before: dict[str, dict], after: dict[str, dict]) -> dict:
    common = sorted(set(before) & set(after))
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = []
    for key in common:
        old, new = before[key], after[key]
        changes = {}
        for field in ("tvg_logo", "legacy_logo"):
            if old.get(field, "") != new.get(field, ""):
                changes[field] = {"before": old.get(field, ""), "after": new.get(field, "")}
        if changes:
            changed.append({
                "identity": key, "name_before": old["name"], "name_after": new["name"],
                "group_before": old["group"], "group_after": new["group"],
                "logo_changes": changes,
            })
    return {
        "channels_before": len(before), "channels_after": len(after),
        "matched": len(common), "added": len(added), "removed": len(removed),
        "logo_changed_channels": len(changed),
        "logo_changes": changed,
        "added_identities": added, "removed_identities": removed,
    }


def classify_error(value: str) -> str:
    message = (value or "").casefold()
    if re.search(r"\b(404|410)\b", message):
        return "permanente_confirmado"
    if re.search(r"\b(401|403)\b|forbidden|unauthorized", message):
        return "restriccion_acceso"
    if re.search(r"timeout|timed out|ssl|tls|connection reset|temporar|\b5\d\d\b", message):
        return "transitorio"
    if "extm3u" in message or "html" in message or "content-type" in message or "formato" in message:
        return "respuesta_invalida"
    return "sin_verificar"


def classify_report(report: dict) -> list[dict]:
    rows = []
    for item in report.get("errors", []):
        detail = str(item.get("error", item.get("detail", "")))
        rows.append({
            "source": item.get("source", "desconocida"),
            "classification": classify_error(detail),
            "detail": detail,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="M3U anterior")
    parser.add_argument("--after", type=Path, required=True, help="M3U posterior")
    parser.add_argument("--source-report", type=Path, help="JSON opcional de auditoría de fuentes")
    parser.add_argument("--output", type=Path, help="Ruta opcional para guardar el informe JSON")
    args = parser.parse_args()

    for path in (args.before, args.after):
        if not path.is_file():
            parser.error(f"No existe el archivo: {path}")

    report = {
        "mode": "read_only",
        "before": str(args.before),
        "after": str(args.after),
        "playlist_comparison": compare(parse_playlist(args.before), parse_playlist(args.after)),
        "source_errors": [],
        "policy": "No modifica archivos ni hace peticiones de red.",
    }
    if args.source_report:
        if not args.source_report.is_file():
            parser.error(f"No existe el reporte: {args.source_report}")
        data = json.loads(args.source_report.read_text(encoding="utf-8"))
        report["source_errors"] = classify_report(data)

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

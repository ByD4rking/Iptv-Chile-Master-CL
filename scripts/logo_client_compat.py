#!/usr/bin/env python3
"""Auditoría estática de referencias de logos para revisión multi-reproductor.

No descarga imágenes, no presupone compatibilidad de un reproductor y nunca
reescribe ni sustituye tvg-logo/logo.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.channel_identity import parse_playlist_text, safe_url_fingerprint

KNOWN_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".gif": "gif", ".webp": "webp", ".svg": "svg"}


def audit_logo_compatibility(records: list[dict]) -> dict:
    missing = []
    references: dict[str, dict] = {}
    conflicts = []

    for index, record in enumerate(records, 1):
        tvg_logo = (record.get("tvg_logo") or "").strip()
        logo = (record.get("logo") or "").strip()
        if not tvg_logo and not logo:
            missing.append({"index": index, "name": record.get("name", "")})
            continue
        if tvg_logo and logo and tvg_logo != logo:
            conflicts.append({
                "index": index,
                "name": record.get("name", ""),
                "tvg_logo_fingerprint": safe_url_fingerprint(tvg_logo),
                "logo_fingerprint": safe_url_fingerprint(logo),
            })
        for field, value in (("tvg-logo", tvg_logo), ("logo", logo)):
            if not value:
                continue
            fingerprint = safe_url_fingerprint(value)
            item = references.setdefault(fingerprint, {
                "fingerprint": fingerprint,
                "fields": set(),
                "channels": [],
                "format": "unknown",
                "transport": "unknown",
                "status": "review",
                "warnings": set(),
            })
            item["fields"].add(field)
            item["channels"].append(record.get("name", ""))
            try:
                parsed = urlsplit(value)
                extension = Path(parsed.path).suffix.casefold()
                fmt = KNOWN_FORMATS.get(extension, "unknown")
                item["format"] = fmt
                if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
                    item["status"] = "invalid_reference"
                    item["warnings"].add("not_absolute_http_url")
                elif parsed.username or parsed.password:
                    item["status"] = "invalid_reference"
                    item["warnings"].add("embedded_credentials")
                else:
                    item["transport"] = parsed.scheme.casefold()
                    item["status"] = "candidate"
                    if parsed.scheme.casefold() == "http":
                        item["warnings"].add("insecure_http")
                    if fmt == "svg":
                        item["warnings"].add("svg_requires_client_validation")
                    elif fmt == "unknown":
                        item["warnings"].add("unknown_image_format")
            except ValueError:
                item["status"] = "invalid_reference"
                item["warnings"].add("malformed_url")

    rendered = []
    for item in references.values():
        rendered.append({
            **item,
            "fields": sorted(item["fields"]),
            "channels": sorted(set(item["channels"])),
            "warnings": sorted(item["warnings"]),
        })
    rendered.sort(key=lambda item: (item["status"], item["fingerprint"]))
    return {
        "channels": len(records),
        "missing_logo_channels": missing,
        "unique_logo_references": len(rendered),
        "invalid_references": sum(item["status"] == "invalid_reference" for item in rendered),
        "references_requiring_review": sum(bool(item["warnings"]) for item in rendered),
        "field_conflicts": conflicts,
        "references": rendered,
        "client_validation": (
            "El análisis estático no certifica renderizado en Televizo ni SS IPTV. "
            "Las referencias candidatas requieren prueba real en ambos reproductores."
        ),
        "policy": "Solo lectura: no descarga, cambia, elimina ni reemplaza logos.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = parse_playlist_text(args.playlist.read_text(encoding="utf-8-sig", errors="replace"))
    report = audit_logo_compatibility(records)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

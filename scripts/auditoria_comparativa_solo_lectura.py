#!/usr/bin/env python3
"""Auditoría comparativa M3U de solo lectura para logos y errores de fuentes.

No descarga streams, no modifica playlists y no realiza peticiones de red.
Solo lee los archivos indicados y escribe JSON en stdout o en --output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

SENSITIVE_QUERY_KEYS = {"jwt", "token", "access_token", "auth", "authorization", "signature", "sig", "key"}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value.casefold()).strip()


def attribute(line: str, name: str) -> str:
    match = re.search(r"(?<![\w-])" + re.escape(name) + r'="([^"]*)"', line, re.I)
    return match.group(1).strip() if match else ""


def parse_playlist(path: Path) -> dict[str, dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    if not any(line.strip().startswith("#EXTM3U") for line in lines[:5]):
        raise ValueError(f"{path}: no contiene cabecera #EXTM3U")
    records: dict[str, dict] = {}
    occurrences: defaultdict[str, int] = defaultdict(int)
    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line.startswith("#EXTINF:"):
            continue
        name = line.rsplit(",", 1)[-1].strip() if "," in line else ""
        tvg_name = attribute(line, "tvg-name") or name
        tvg_id = attribute(line, "tvg-id")
        channel_id = attribute(line, "channelId")
        group = attribute(line, "group-title")
        identity = (
            "tvg-id:" + normalize(tvg_id) if tvg_id else
            "channel-id:" + normalize(channel_id) if channel_id else
            "name-group:" + normalize(tvg_name) + "|" + normalize(group)
        )
        occurrences[identity] += 1
        key = identity if occurrences[identity] == 1 else f"{identity}#{occurrences[identity]}"
        records[key] = {
            "identity": key,
            "name": name,
            "tvg_name": tvg_name,
            "group": group,
            "tvg_logo": attribute(line, "tvg-logo"),
            "logo": attribute(line, "logo"),
            "line": line_no,
        }
    return records


def compare_playlists(before: dict[str, dict], after: dict[str, dict]) -> dict:
    old_keys, new_keys = set(before), set(after)
    changed = []
    for key in sorted(old_keys & new_keys):
        old, new = before[key], after[key]
        logo_changes = {}
        for field in ("tvg_logo", "logo"):
            old_value, new_value = old.get(field, ""), new.get(field, "")
            if old_value != new_value:
                logo_changes[field] = {"before": old_value, "after": new_value}
        if logo_changes:
            changed.append({
                "identity": key,
                "name_before": old.get("name", ""),
                "name_after": new.get("name", ""),
                "group_before": old.get("group", ""),
                "group_after": new.get("group", ""),
                "logo_changes": logo_changes,
            })
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    return {
        "channels_before": len(before),
        "channels_after": len(after),
        "matched": len(old_keys & new_keys),
        "added": len(added),
        "removed": len(removed),
        "logo_changed_channels": len(changed),
        "logo_changes": changed,
        "added_identities": added,
        "removed_identities": removed,
    }


def classify_error(detail: str, observations: int = 1) -> str:
    message = (detail or "").casefold()
    status_match = re.search(r"\b(?:http\s*)?(\d{3})\b", message)
    status = int(status_match.group(1)) if status_match else None
    if status in {401, 403} or "forbidden" in message or "unauthorized" in message:
        return "restriccion_acceso"
    if status in {404, 410}:
        return "permanente_confirmado" if observations >= 2 else "permanente_candidato"
    if status is not None and 500 <= status <= 599:
        return "transitorio"
    if re.search(r"timeout|timed out|ssl|tls|connection reset|temporar|dns|name resolution|\b429\b", message):
        return "transitorio"
    if any(token in message for token in ("#extm3u", "html", "content-type", "formato", "respuesta vacía", "respuesta vacia")):
        return "respuesta_invalida"
    return "sin_verificar"


def redact_sensitive_values(value: str) -> str:
    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.netloc or not parts.query:
            return value
        query = [
            (key, "***" if key.casefold() in SENSITIVE_QUERY_KEYS else val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    except ValueError:
        return value


def classify_source_report(report: dict) -> list[dict]:
    rows = []
    for item in report.get("errors", []):
        detail = str(item.get("error", item.get("detail", "")))
        observations = item.get("observations", item.get("attempts", 1))
        try:
            observations = max(1, int(observations))
        except (TypeError, ValueError):
            observations = 1
        rows.append({
            "source": str(item.get("source", "desconocida")),
            "classification": classify_error(detail, observations),
            "observations": observations,
            "detail": redact_sensitive_values(detail),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="Playlist anterior")
    parser.add_argument("--after", type=Path, required=True, help="Playlist posterior")
    parser.add_argument("--source-report", type=Path, help="JSON opcional de auditoría de fuentes")
    parser.add_argument("--output", type=Path, help="Ruta opcional del informe JSON")
    args = parser.parse_args()

    try:
        comparison = compare_playlists(parse_playlist(args.before), parse_playlist(args.after))
        source_errors = []
        if args.source_report:
            data = json.loads(args.source_report.read_text(encoding="utf-8-sig"))
            source_errors = classify_source_report(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    report = {
        "mode": "read_only",
        "playlist_comparison": comparison,
        "source_errors": source_errors,
        "policy": [
            "No modifica playlists ni archivos de configuración.",
            "No realiza peticiones de red ni valida la reproducción de streams.",
            "Un 404/410 aislado es candidato; requiere al menos dos observaciones para confirmarse.",
            "No autoriza reemplazar logos ni retirar canales.",
        ],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

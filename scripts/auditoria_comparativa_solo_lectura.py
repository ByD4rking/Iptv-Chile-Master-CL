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
    exact = old_keys & new_keys
    pairs = [(key, before[key], after[key]) for key in sorted(exact)]
    matched_old, matched_new = set(exact), set(exact)

    # Fallback conservador: si cambió tvg-id, empareja solo por nombre+categoría
    # cuando la clave es única en ambos snapshots. Nunca adivina entre duplicados.
    def fallback_key(record: dict) -> str:
        name = normalize(record.get("tvg_name") or record.get("name", ""))
        group = normalize(record.get("group", ""))
        return name + "|" + group if name else ""

    old_fallback: defaultdict[str, list[str]] = defaultdict(list)
    new_fallback: defaultdict[str, list[str]] = defaultdict(list)
    for key in old_keys - matched_old:
        fallback = fallback_key(before[key])
        if fallback:
            old_fallback[fallback].append(key)
    for key in new_keys - matched_new:
        fallback = fallback_key(after[key])
        if fallback:
            new_fallback[fallback].append(key)

    for fallback in sorted(set(old_fallback) & set(new_fallback)):
        old_matches, new_matches = old_fallback[fallback], new_fallback[fallback]
        if len(old_matches) == 1 and len(new_matches) == 1:
            old_key, new_key = old_matches[0], new_matches[0]
            pairs.append((old_key, before[old_key], after[new_key]))
            matched_old.add(old_key)
            matched_new.add(new_key)

    changed = []
    for identity, old, new in pairs:
        logo_changes = {}
        for field in ("tvg_logo", "logo"):
            old_value, new_value = old.get(field, ""), new.get(field, "")
            if old_value != new_value:
                logo_changes[field] = {"before": old_value, "after": new_value}
        if logo_changes:
            changed.append({
                "identity": identity,
                "name_before": old.get("name", ""),
                "name_after": new.get("name", ""),
                "group_before": old.get("group", ""),
                "group_after": new.get("group", ""),
                "logo_changes": logo_changes,
            })

    added = sorted(new_keys - matched_new)
    removed = sorted(old_keys - matched_old)
    return {
        "channels_before": len(before),
        "channels_after": len(after),
        "matched": len(pairs),
        "added": len(added),
        "removed": len(removed),
        "logo_changed_channels": len(changed),
        "logo_changes": changed,
        "added_identities": added,
        "removed_identities": removed,
    }


def extract_http_status(detail: str) -> int | None:
    """Extrae solo códigos HTTP explícitos, evitando números arbitrarios de URLs."""
    message = (detail or "").strip()
    patterns = (
        r"\bHTTP(?:\s+ERROR)?\s*[:#]?\s*([1-5]\d{2})\b",
        r"\bstatus(?:\s+code)?\s*[:=]?\s*([1-5]\d{2})\b",
        r"^([1-5]\d{2})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, message, re.I)
        if match:
            return int(match.group(1))
    return None


def classify_error(
    detail: str,
    observations: int = 1,
    independent_observations: int = 1,
) -> str:
    message = (detail or "").casefold()
    status = extract_http_status(detail)
    if status in {401, 403} or "forbidden" in message or "unauthorized" in message:
        return "restriccion_acceso"
    if status in {404, 410}:
        return "permanente_confirmado" if independent_observations >= 2 else "permanente_candidato"
    if status == 429 or (status is not None and 500 <= status <= 599):
        return "transitorio"
    if re.search(r"timeout|timed out|ssl|tls|connection reset|temporar|dns|name resolution", message):
        return "transitorio"
    if any(token in message for token in ("#extm3u", "html", "content-type", "formato", "respuesta vacía", "respuesta vacia")):
        return "respuesta_invalida"
    return "sin_verificar"


def redact_sensitive_values(value: str) -> str:
    url_pattern = re.compile(r"https?://[^\s\"'<>]+", re.I)

    def redact_url(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        try:
            parts = urlsplit(raw_url)
            query = [
                (key, "***" if key.casefold() in SENSITIVE_QUERY_KEYS else val)
                for key, val in parse_qsl(parts.query, keep_blank_values=True)
            ]
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        except ValueError:
            return "[URL omitida por formato inválido]"

    return url_pattern.sub(redact_url, value)


def redact_report_values(value):
    """Redacta URLs sensibles en todos los campos textuales del informe."""
    if isinstance(value, str):
        return redact_sensitive_values(value)
    if isinstance(value, list):
        return [redact_report_values(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_report_values(item) for key, item in value.items()}
    return value


def redact_report_values(value):
    """Redacta URLs sensibles en todos los campos textuales del informe."""
    if isinstance(value, str):
        return redact_sensitive_values(value)
    if isinstance(value, list):
        return [redact_report_values(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_report_values(item) for key, item in value.items()}
    return value



def protected_logo_changes(comparison: dict) -> list[dict]:
    """Devuelve cambios que reemplazan o eliminan un logo previamente existente."""
    protected = []
    for channel in comparison.get("logo_changes", []):
        for field, values in channel.get("logo_changes", {}).items():
            before = str(values.get("before", "")).strip()
            after = str(values.get("after", "")).strip()
            if before and before != after:
                protected.append({
                    "identity": channel.get("identity", ""),
                    "name": channel.get("name_before", ""),
                    "field": field,
                    "before": before,
                    "after": after,
                })
    return protected


def classify_source_report(report: dict) -> list[dict]:
    rows = []
    for item in report.get("errors", []):
        detail = str(item.get("error", item.get("detail", "")))
        observations = item.get("observations", item.get("attempts", 1))
        try:
            observations = max(1, int(observations))
        except (TypeError, ValueError):
            observations = 1

        # Reintentos de una misma ejecución no cuentan como evidencia independiente.
        independent = item.get("independent_observations")
        run_ids = item.get("observation_run_ids", [])
        if isinstance(run_ids, list):
            independent_count = len({str(value) for value in run_ids if value is not None})
        else:
            try:
                independent_count = max(1, int(independent or 1))
            except (TypeError, ValueError):
                independent_count = 1

        rows.append({
            "source": str(item.get("source", "desconocida")),
            "classification": classify_error(detail, observations, independent_count),
            "observations": observations,
            "independent_observations": independent_count,
            "detail": redact_sensitive_values(detail),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True, help="Playlist anterior")
    parser.add_argument("--after", type=Path, required=True, help="Playlist posterior")
    parser.add_argument("--source-report", type=Path, help="JSON opcional de auditoría de fuentes")
    parser.add_argument("--output", type=Path, help="Ruta opcional del informe JSON")
    parser.add_argument(
        "--fail-on-existing-logo-change",
        action="store_true",
        help="Devuelve código 2 si un logo no vacío fue reemplazado o eliminado",
    )
    args = parser.parse_args()

    try:
        comparison = compare_playlists(parse_playlist(args.before), parse_playlist(args.after))
        source_errors = []
        if args.source_report:
            data = json.loads(args.source_report.read_text(encoding="utf-8-sig"))
            source_errors = classify_source_report(data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    existing_logo_changes = protected_logo_changes(comparison)
    report = {
        "mode": "read_only",
        "playlist_comparison": comparison,
        "existing_logo_changes": existing_logo_changes,
        "source_errors": source_errors,
        "policy": [
            "No modifica playlists ni archivos de configuración.",
            "No realiza peticiones de red ni valida la reproducción de streams.",
            "Un 404/410 aislado es candidato; requiere al menos dos observaciones para confirmarse.",
            "No autoriza reemplazar logos ni retirar canales.",
        ],
    }
    report = redact_report_values(report)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    if args.fail_on_existing_logo_change and existing_logo_changes:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Identidad estable y comparación conservadora de canales M3U (solo lectura).

Prioriza identificadores explícitos y del proveedor. El nombre/categoría solo se
usa como último recurso cuando la coincidencia es única en ambos snapshots.
Nunca modifica playlists ni decide borrar, mover o reemplazar canales.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_QUERY_KEYS = {
    "jwt", "token", "access_token", "auth", "authorization", "signature",
    "sig", "key", "api_key", "apikey", "password", "passwd", "secret",
    "session", "hdnea", "auth_key", "x-amz-signature", "x-amz-security-token",
}
PLACEHOLDER_IDS = {"", "-1", "0", "none", "null", "undefined", "unknown", "n/a", "na"}
OPTION_SUFFIX = re.compile(
    r"(?:\[\s*|\(\s*)?(?:opci[oó]n|option|opc)\s*#?\s*(\d+)\s*(?:\]|\))?\s*$",
    re.I,
)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value.casefold()).strip()


def attribute(line: str, name: str) -> str:
    match = re.search(
        r"(?<![\w-])" + re.escape(name) + r'\s*=\s*(?:"([^"]*)"|([^\s,]+))',
        line,
        re.I,
    )
    return (match.group(1) if match and match.group(1) is not None else
            match.group(2) if match else "").strip()


def _valid_identifier(value: str) -> str:
    normalized = normalize(value)
    return "" if normalized in PLACEHOLDER_IDS else normalized


def _option_variant(name: str) -> str:
    match = OPTION_SUFFIX.search(name or "")
    return f"option-{match.group(1)}" if match else ""


def url_provider_alias(url: str) -> str:
    """Extrae solo IDs de rutas conocidas; evita usar tokens como identidad."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return ""
    patterns = (
        r"/(?:vod/)?channel/([a-f0-9]{16,64})(?:/|$)",
        r"/plu-([a-f0-9]{16,64})(?:\.[a-z0-9]+)?$",
    )
    for pattern in patterns:
        match = re.search(pattern, parsed.path, re.I)
        if match:
            return f"provider-channel:{match.group(1).casefold()}"
    return ""


def safe_url_fingerprint(url: str) -> str:
    """Fingerprint sin credenciales ni parámetros de autenticación efímeros."""
    try:
        parsed = urlsplit(url.strip())
        query = [
            (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in SENSITIVE_QUERY_KEYS
        ]
        safe = urlunsplit((
            parsed.scheme.casefold(), (parsed.netloc or "").casefold(),
            parsed.path, urlencode(query), "",
        ))
    except ValueError:
        safe = "invalid-url"
    return hashlib.sha256(safe.encode("utf-8")).hexdigest()[:16]


def parse_playlist_text(text: str) -> list[dict]:
    lines = text.lstrip("\ufeff").splitlines()
    records: list[dict] = []
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line.upper().startswith("#EXTINF:"):
            continue
        name = line.rsplit(",", 1)[-1].strip() if "," in line else ""
        tvg_name = attribute(line, "tvg-name") or name
        tvg_id = _valid_identifier(attribute(line, "tvg-id"))
        channel_id = _valid_identifier(attribute(line, "channel-id") or attribute(line, "channelId"))
        provider_id = _valid_identifier(attribute(line, "provider-channel-id"))
        variant = _option_variant(name)
        group = attribute(line, "group-title")
        tvg_logo = attribute(line, "tvg-logo")
        logo = attribute(line, "logo")
        stream = ""
        for candidate in lines[index + 1:]:
            candidate = candidate.strip()
            if not candidate:
                continue
            if candidate.upper().startswith("#EXTINF:"):
                break
            if candidate.startswith("#"):
                continue
            stream = candidate
            break
        aliases = []
        if tvg_id:
            aliases.append("tvg-id:" + tvg_id)
        if channel_id:
            aliases.append("channel-id:" + channel_id)
        if provider_id:
            aliases.append("provider-id:" + provider_id)
        provider_alias = url_provider_alias(stream)
        if provider_alias:
            aliases.append(provider_alias)
        # Los IDs placeholder (p. ej. channelId="-1") no son identidad.
        # Las alternativas con un tvg-id compartido se distinguen por su sufijo
        # explícito [Opción N], sin confundirlas ni colapsarlas.
        base_aliases = tuple(aliases)
        if base_aliases:
            # Cuando un proveedor reutiliza un ID para varias señales/opciones,
            # añade alias secundarios que distinguen cada variante sin perder
            # el ID principal. La huella de stream solo desambigua si la URL
            # sigue siendo la misma; nunca fuerza una coincidencia por sí sola.
            disambiguator = (
                normalize(tvg_name) + "|" + normalize(group) + "|" + variant
                if variant else normalize(name) + "|" + normalize(group)
            )
            for alias in base_aliases:
                aliases.append(f"variant:{alias}:{disambiguator}")
                if stream:
                    aliases.append(f"stream:{alias}:{safe_url_fingerprint(stream)}")
        fallback = normalize(tvg_name) + "|" + normalize(group) + "|" + variant
        stable_id = aliases[0] if aliases else ("name-group:" + fallback if fallback != "|" else "")
        records.append({
            "name": name,
            "tvg_name": tvg_name,
            "group": group,
            "tvg_logo": tvg_logo,
            "logo": logo,
            "tvg_id": tvg_id,
            "channel_id": channel_id,
            "provider_id": provider_id,
            "option_variant": variant,
            "stream_fingerprint": safe_url_fingerprint(stream) if stream else "",
            "aliases": aliases,
            "stable_id": stable_id,
            "fallback": fallback,
        })
    return records


def _unique_alias_map(records: list[dict], unmatched: set[int]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = defaultdict(list)
    for index in unmatched:
        for alias in records[index]["aliases"]:
            result[alias].append(index)
    return result


def compare_snapshots(before: list[dict], after: list[dict]) -> dict:
    unmatched_old, unmatched_new = set(range(len(before))), set(range(len(after)))
    pairs: list[tuple[int, int, str, str]] = []
    ambiguous: list[dict] = []

    # Un par solo se acepta si todos los alias compartidos apuntan al mismo canal.
    while True:
        old_aliases = _unique_alias_map(before, unmatched_old)
        new_aliases = _unique_alias_map(after, unmatched_new)
        pair_aliases: dict[tuple[int, int], set[str]] = defaultdict(set)
        for alias in set(old_aliases) & set(new_aliases):
            if len(old_aliases[alias]) == 1 and len(new_aliases[alias]) == 1:
                pair = (old_aliases[alias][0], new_aliases[alias][0])
                pair_aliases[pair].add(alias)
        old_partners: dict[int, set[int]] = defaultdict(set)
        new_partners: dict[int, set[int]] = defaultdict(set)
        for old_index, new_index in pair_aliases:
            old_partners[old_index].add(new_index)
            new_partners[new_index].add(old_index)
        safe_pairs = [
            (old_index, new_index)
            for old_index, new_index in pair_aliases
            if len(old_partners[old_index]) == 1 and len(new_partners[new_index]) == 1
        ]
        if not safe_pairs:
            break
        for old_index, new_index in safe_pairs:
            alias = sorted(pair_aliases[(old_index, new_index)])[0]
            pairs.append((old_index, new_index, alias, "strong"))
        unmatched_old -= {old_index for old_index, _ in safe_pairs}
        unmatched_new -= {new_index for _, new_index in safe_pairs}

    # No rebajar a nombre/categoría cuando existen alias fuertes cruzados
    # pero contradictorios o duplicados: el caso queda para revisión.
    blocked_old = {
        old_index for old_index in unmatched_old
        if any(set(before[old_index]["aliases"]) & set(after[new_index]["aliases"])
               for new_index in unmatched_new)
    }
    blocked_new = {
        new_index for new_index in unmatched_new
        if any(set(after[new_index]["aliases"]) & set(before[old_index]["aliases"])
               for old_index in unmatched_old)
    }

    # Fallback débil: nombre+categoría, único en ambos snapshots y sin conflicto.
    old_fallback: dict[str, list[int]] = defaultdict(list)
    new_fallback: dict[str, list[int]] = defaultdict(list)
    for index in unmatched_old - blocked_old:
        key = before[index]["fallback"]
        if key and key != "|":
            old_fallback[key].append(index)
    for index in unmatched_new - blocked_new:
        key = after[index]["fallback"]
        if key and key != "|":
            new_fallback[key].append(index)
    for key in sorted(set(old_fallback) & set(new_fallback)):
        if len(old_fallback[key]) == 1 and len(new_fallback[key]) == 1:
            old_index, new_index = old_fallback[key][0], new_fallback[key][0]
            pairs.append((old_index, new_index, "name-group:" + key, "fallback"))
            unmatched_old.discard(old_index)
            unmatched_new.discard(new_index)

    changes = []
    for old_index, new_index, identity, confidence in pairs:
        old, new = before[old_index], after[new_index]
        changed = []
        if normalize(old["name"]) != normalize(new["name"]):
            changed.append("name")
        if normalize(old["group"]) != normalize(new["group"]):
            changed.append("group")
        if old["stream_fingerprint"] != new["stream_fingerprint"]:
            changed.append("stream")
        if old["tvg_logo"] != new["tvg_logo"] or old["logo"] != new["logo"]:
            changed.append("logo")
        changes.append({
            "identity": identity,
            "confidence": confidence,
            "before_name": old["name"],
            "after_name": new["name"],
            "before_group": old["group"],
            "after_group": new["group"],
            "before_tvg_logo": old["tvg_logo"],
            "after_tvg_logo": new["tvg_logo"],
            "before_logo": old["logo"],
            "after_logo": new["logo"],
            "changed_fields": changed,
            "stream_changed": "stream" in changed,
        })

    for side, indices, records, opposite in (
        ("before", unmatched_old, before, after),
        ("after", unmatched_new, after, before),
    ):
        for index in sorted(indices):
            record = records[index]
            duplicate_alias = any(
                other_index != index
                and set(record["aliases"]) & set(other["aliases"])
                for other_index, other in enumerate(records)
            )
            conflicting_alias = any(
                set(record["aliases"]) & set(other["aliases"])
                for other in opposite
            )
            if duplicate_alias or conflicting_alias:
                ambiguous.append({
                    "side": side,
                    "name": record["name"],
                    "reason": "aliases duplicados o contradictorios; no se emparejó automáticamente",
                })

    return {
        "before_count": len(before),
        "after_count": len(after),
        "matched": len(pairs),
        "added": len(unmatched_new),
        "removed": len(unmatched_old),
        "added_channels": [
            {
                "name": after[index]["name"],
                "group": after[index]["group"],
                "tvg_id": after[index]["tvg_id"] or None,
                "stream_fingerprint": after[index]["stream_fingerprint"],
            }
            for index in sorted(unmatched_new)
        ],
        "removed_channels": [
            {
                "name": before[index]["name"],
                "group": before[index]["group"],
                "tvg_id": before[index]["tvg_id"] or None,
                "stream_fingerprint": before[index]["stream_fingerprint"],
            }
            for index in sorted(unmatched_old)
        ],
        "renamed_or_moved": sum(bool(set(row["changed_fields"]) & {"name", "group"}) for row in changes),
        "stream_changes": sum(row["stream_changed"] for row in changes),
        "ambiguous": ambiguous,
        "changes": changes,
        "policy": "Solo diagnóstico; ninguna playlist, URL, categoría o logo fue modificada.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    before = parse_playlist_text(args.before.read_text(encoding="utf-8-sig", errors="replace"))
    after = parse_playlist_text(args.after.read_text(encoding="utf-8-sig", errors="replace"))
    report = compare_snapshots(before, after)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

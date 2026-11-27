#!/usr/bin/env python3
"""Propone logos solo para canales sin tvg-logo ni logo; nunca modifica playlists."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from scripts.channel_identity import normalize, parse_playlist_text, safe_url_fingerprint

SUPPORTED_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".gif": "gif"}


def _logo_candidate(record: dict) -> tuple[str, str] | None:
    tvg_logo = (record.get("tvg_logo") or "").strip()
    logo = (record.get("logo") or "").strip()
    values = {value for value in (tvg_logo, logo) if value}
    if len(values) != 1:
        return None
    value = next(iter(values))
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    fmt = SUPPORTED_FORMATS.get(Path(parsed.path).suffix.casefold())
    if not fmt:
        return None
    return safe_url_fingerprint(value), fmt


def propose_missing_logos(records: list[dict], candidate_sources: list[tuple[str, list[dict]]]) -> dict:
    missing = [index for index, row in enumerate(records) if not row.get("tvg_logo") and not row.get("logo")]
    current_aliases: dict[str, list[int]] = defaultdict(list)
    current_fallback: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(records):
        for alias in row.get("aliases", []):
            current_aliases[alias].append(index)
        if row.get("fallback"):
            current_fallback[row["fallback"]].append(index)

    proposals, ambiguous, unmatched = [], [], []
    for index in missing:
        target = records[index]
        found: list[dict] = []
        ambiguous_hits: list[tuple[str, dict]] = []
        for source_name, source_records in candidate_sources:
            source_aliases: dict[str, list[int]] = defaultdict(list)
            source_fallback: dict[str, list[int]] = defaultdict(list)
            for candidate_index, candidate in enumerate(source_records):
                for alias in candidate.get("aliases", []):
                    source_aliases[alias].append(candidate_index)
                if candidate.get("fallback"):
                    source_fallback[candidate["fallback"]].append(candidate_index)

            matches: dict[int, str] = {}
            for alias in target.get("aliases", []):
                if len(current_aliases[alias]) != 1:
                    continue
                candidates = source_aliases.get(alias, [])
                if len(candidates) == 1:
                    matches[candidates[0]] = "strong"
                elif len(candidates) > 1:
                    ambiguous_hits.extend((source_name, source_records[candidate_index]) for candidate_index in candidates)
            if not matches and target.get("fallback"):
                key = target["fallback"]
                if len(current_fallback[key]) == 1:
                    candidates = source_fallback.get(key, [])
                    if len(candidates) == 1:
                        matches[candidates[0]] = "fallback"
                    elif len(candidates) > 1:
                        ambiguous_hits.extend((source_name, source_records[candidate_index]) for candidate_index in candidates)

            for candidate_index, confidence in matches.items():
                candidate = source_records[candidate_index]
                logo = _logo_candidate(candidate)
                if not logo:
                    continue
                fingerprint, fmt = logo
                found.append({
                    "source": source_name,
                    "candidate_name": candidate.get("name", ""),
                    "candidate_group": candidate.get("group", ""),
                    "logo_fingerprint": fingerprint,
                    "format": fmt,
                    "confidence": confidence,
                })

        for source_name, candidate in ambiguous_hits:
            logo = _logo_candidate(candidate)
            if logo:
                fingerprint, fmt = logo
                found.append({
                    "source": source_name,
                    "candidate_name": candidate.get("name", ""),
                    "candidate_group": candidate.get("group", ""),
                    "logo_fingerprint": fingerprint,
                    "format": fmt,
                    "confidence": "ambiguous",
                })
        distinct = {item["logo_fingerprint"] for item in found}
        if len(distinct) == 1 and not any(x["confidence"] == "ambiguous" for x in found):
            best_confidence = "strong" if any(x["confidence"] == "strong" for x in found) else "fallback"
            proposals.append({
                "index": target.get("index", index + 1),
                "channel": target.get("name", ""),
                "group": target.get("group", ""),
                "logo_fingerprint": next(iter(distinct)),
                "format": found[0]["format"],
                "confidence": best_confidence,
                "sources": sorted({x["source"] for x in found}),
            })
        elif len(distinct) > 1 or ambiguous_hits:
            ambiguous.append({
                "index": target.get("index", index + 1),
                "channel": target.get("name", ""),
                "candidate_logo_count": len(distinct),
                "sources": sorted({x["source"] for x in found}),
            })
        else:
            unmatched.append({
                "index": target.get("index", index + 1),
                "channel": target.get("name", ""),
                "group": target.get("group", ""),
            })

    return {
        "channels": len(records),
        "missing_logo_channels": len(missing),
        "proposals": proposals,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "policy": (
            "Solo propone referencias para entradas sin tvg-logo y sin logo. "
            "No modifica playlists, no sustituye logos existentes y omite SVG, "
            "formatos desconocidos, URLs inseguras y candidatos conflictivos."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist", required=True, type=Path)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    records = parse_playlist_text(args.playlist.read_text(encoding="utf-8-sig", errors="replace"))
    manifest = json.loads(args.candidate_manifest.read_text(encoding="utf-8"))
    sources = []
    for item in manifest.get("sources", []):
        name, path = str(item.get("name") or "").strip(), Path(str(item.get("path") or ""))
        if name and path.is_file():
            sources.append((name, parse_playlist_text(path.read_text(encoding="utf-8-sig", errors="replace"))))
    report = propose_missing_logos(records, sources)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

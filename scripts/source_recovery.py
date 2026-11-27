#!/usr/bin/env python3
"""Propone fuentes alternativas para canales con fallos persistentes (solo lectura)."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from scripts.channel_identity import parse_playlist_text, safe_url_fingerprint
from scripts.m3u_structure import validate_m3u_bytes


def _index_aliases(records: list[dict]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = defaultdict(list)
    for position, record in enumerate(records):
        for alias in record["aliases"]:
            index[alias].append(position)
    return index


def suggest_recoveries(
    current: list[dict],
    candidate_sources: list[tuple[str, list[dict]]],
    health: dict,
    *,
    min_failures: int = 3,
) -> dict:
    health_by_fingerprint = {}
    for url, state in health.items():
        if not isinstance(state, dict):
            continue
        fingerprint = safe_url_fingerprint(str(url))
        previous = health_by_fingerprint.get(fingerprint)
        if previous is None or int(state.get("checked_at", 0) or 0) >= int(previous.get("checked_at", 0) or 0):
            health_by_fingerprint[fingerprint] = state

    all_candidates = []
    for source_name, records in candidate_sources:
        for record in records:
            all_candidates.append((source_name, record))

    candidate_aliases: dict[str, list[int]] = defaultdict(list)
    current_aliases = _index_aliases(current)
    for index, (_, record) in enumerate(all_candidates):
        for alias in record["aliases"]:
            candidate_aliases[alias].append(index)

    recommendations = []
    skipped_ambiguous = 0
    for channel in current:
        state = health_by_fingerprint.get(channel["stream_fingerprint"], {})
        try:
            failures = int(state.get("consecutive_failures", 0) or 0)
        except (TypeError, ValueError):
            failures = 0
        if state.get("ok") is not False or failures < min_failures:
            continue

        strong_candidates = {}
        for alias in channel["aliases"]:
            if len(current_aliases.get(alias, [])) != 1:
                continue
            matches = candidate_aliases.get(alias, [])
            if len(matches) != 1:
                if matches:
                    skipped_ambiguous += 1
                continue
            source_name, candidate = all_candidates[matches[0]]
            if candidate["stream_fingerprint"] == channel["stream_fingerprint"]:
                continue
            key = candidate["stream_fingerprint"]
            strong_candidates[key] = {
                "source": source_name,
                "name": candidate["name"],
                "group": candidate["group"],
                "fingerprint": key,
                "confidence": "strong",
                "matched_alias": alias,
            }

        proposed = list(strong_candidates.values())
        if not proposed:
            # Nombre+categoría es fallback débil: solo si el canal no tiene
            # alias fuertes y la pareja es única en todo el catálogo candidato.
            fallback = channel["fallback"]
            if not channel["aliases"] and fallback and fallback != "|":
                target_matches = [
                    item for item in current
                    if item["fallback"] == fallback
                ]
                possible = [
                    (source_name, record)
                    for source_name, record in all_candidates
                    if not record["aliases"] and record["fallback"] == fallback
                ]
                if len(target_matches) == 1 and len(possible) == 1:
                    source_name, candidate = possible[0]
                    if candidate["stream_fingerprint"] != channel["stream_fingerprint"]:
                        proposed.append({
                            "source": source_name,
                            "name": candidate["name"],
                            "group": candidate["group"],
                            "fingerprint": candidate["stream_fingerprint"],
                            "confidence": "fallback",
                            "matched_alias": "name+group",
                        })

        recommendations.append({
            "channel": channel["name"],
            "group": channel["group"],
            "state": state.get("state", "UNKNOWN"),
            "consecutive_failures": failures,
            "candidate_count": len(proposed),
            "candidates": proposed,
            "action": "review_only" if proposed else "no_verified_alternative",
        })

    return {
        "current_channels": len(current),
        "candidate_channels": len(all_candidates),
        "channels_needing_recovery": len(recommendations),
        "channels_with_candidates": sum(bool(row["candidates"]) for row in recommendations),
        "ambiguous_candidates_skipped": skipped_ambiguous,
        "recommendations": recommendations,
        "policy": (
            "Solo propone alternativas por identidad; no prueba ni sustituye URLs, "
            "no modifica M3U y no retira canales. Una alternativa requiere validación "
            "de reproducción antes de cualquier cambio."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--playlist", required=True, type=Path)
    parser.add_argument("--health", required=True, type=Path)
    parser.add_argument(
        "--candidate", action="append", default=[], metavar="SOURCE=PATH",
        help="Fuente candidata M3U; se puede repetir.",
    )
    parser.add_argument(
        "--candidate-manifest", type=Path,
        help="JSON con sources [{name,path}] descargadas y validadas en auditoría.",
    )
    parser.add_argument("--min-failures", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.min_failures < 1:
        parser.error("--min-failures debe ser al menos 1")
    if not args.candidate and not args.candidate_manifest:
        parser.error("se requiere --candidate o --candidate-manifest")
    current_bytes = args.playlist.read_bytes()
    validate_m3u_bytes(current_bytes, str(args.playlist))
    current = parse_playlist_text(current_bytes.decode("utf-8-sig"))
    health = json.loads(args.health.read_text(encoding="utf-8"))
    sources = []
    if args.candidate_manifest:
        manifest = json.loads(args.candidate_manifest.read_text(encoding="utf-8"))
        for item in manifest.get("sources", []):
            source_name = str(item.get("name") or "").strip()
            path = Path(str(item.get("path") or ""))
            if not source_name or not path.is_file():
                continue
            source_bytes = path.read_bytes()
            validate_m3u_bytes(source_bytes, source_name)
            records = parse_playlist_text(source_bytes.decode("utf-8-sig"))
            sources.append((source_name, records))
    for item in args.candidate:
        if "=" not in item:
            parser.error("--candidate debe usar SOURCE=PATH")
        source_name, raw_path = item.split("=", 1)
        path = Path(raw_path)
        source_bytes = path.read_bytes()
        validate_m3u_bytes(source_bytes, str(path))
        records = parse_playlist_text(source_bytes.decode("utf-8-sig"))
        sources.append((source_name, records))
    report = suggest_recoveries(current, sources, health, min_failures=args.min_failures)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

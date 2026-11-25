#!/usr/bin/env python3
"""Detector conservador de regresiones entre dos snapshots M3U (solo lectura)."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.channel_identity import compare_snapshots, parse_playlist_text
from scripts.m3u_structure import validate_m3u_bytes


def evaluate_regressions(
    before: list[dict],
    after: list[dict],
    *,
    max_removed: int = 0,
    max_category_changes: int = 0,
    max_logo_replacements: int = 0,
    fail_on_stream_change: bool = False,
) -> dict:
    comparison = compare_snapshots(before, after)
    category_changes = sum(
        "group" in row["changed_fields"] for row in comparison["changes"]
    )
    logo_replacements = sum(
        (
            bool(row["before_tvg_logo"]) and row["before_tvg_logo"] != row["after_tvg_logo"]
        ) or (
            bool(row["before_logo"]) and row["before_logo"] != row["after_logo"]
        )
        for row in comparison["changes"]
    )
    stream_changes = comparison["stream_changes"]

    fingerprints = [
        row["stream_fingerprint"] for row in after if row["stream_fingerprint"]
    ]
    duplicate_streams = sum(count - 1 for count in Counter(fingerprints).values() if count > 1)
    duplicate_groups: dict[str, list[dict]] = {}
    for row in after:
        fingerprint = row["stream_fingerprint"]
        if fingerprint:
            duplicate_groups.setdefault(fingerprint, []).append({
                "name": row["name"],
                "group": row["group"],
            })
    duplicate_stream_details = [
        {"fingerprint": fingerprint, "channels": rows}
        for fingerprint, rows in duplicate_groups.items() if len(rows) > 1
    ]

    violations = []
    if comparison["removed"] > max_removed:
        violations.append({
            "rule": "unexpected_removals",
            "actual": comparison["removed"],
            "allowed": max_removed,
        })
    if category_changes > max_category_changes:
        violations.append({
            "rule": "category_changes",
            "actual": category_changes,
            "allowed": max_category_changes,
        })
    if logo_replacements > max_logo_replacements:
        violations.append({
            "rule": "existing_logo_replacements",
            "actual": logo_replacements,
            "allowed": max_logo_replacements,
        })
    if fail_on_stream_change and stream_changes:
        violations.append({
            "rule": "stream_url_changes",
            "actual": stream_changes,
            "allowed": 0,
        })

    return {
        "passed": not violations,
        "before_count": len(before),
        "after_count": len(after),
        "added": comparison["added"],
        "removed": comparison["removed"],
        "matched": comparison["matched"],
        "category_changes": category_changes,
        "logo_replacements": logo_replacements,
        "stream_changes": stream_changes,
        "duplicate_stream_fingerprints": duplicate_streams,
        "duplicate_stream_details": duplicate_stream_details,
        "stream_change_samples": [
            {
                "before_name": row["before_name"],
                "after_name": row["after_name"],
                "before_group": row["before_group"],
                "after_group": row["after_group"],
            }
            for row in comparison["changes"] if row["stream_changed"]
        ][:40],
        "ambiguous_matches": len(comparison["ambiguous"]),
        "added_channels": comparison["added_channels"],
        "removed_channels": comparison["removed_channels"],
        "ambiguous_details": comparison["ambiguous"],
        "violations": violations,
        "details": comparison["changes"],
        "policy": (
            "Solo lectura. No modifica ni publica listas. Los cambios de URL y "
            "duplicados se informan; solo bloquean si se solicita expresamente."
        ),
    }


def audit_files(
    before_path: Path,
    after_path: Path,
    **policy,
) -> dict:
    before_bytes = before_path.read_bytes()
    after_bytes = after_path.read_bytes()
    validate_m3u_bytes(before_bytes, str(before_path))
    validate_m3u_bytes(after_bytes, str(after_path))
    before = parse_playlist_text(before_bytes.decode("utf-8-sig"))
    after = parse_playlist_text(after_bytes.decode("utf-8-sig"))
    return evaluate_regressions(before, after, **policy)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-removed", type=int, default=0)
    parser.add_argument("--max-category-changes", type=int, default=0)
    parser.add_argument("--max-logo-replacements", type=int, default=0)
    parser.add_argument("--fail-on-stream-change", action="store_true")
    args = parser.parse_args()
    if min(args.max_removed, args.max_category_changes, args.max_logo_replacements) < 0:
        parser.error("los límites no pueden ser negativos")
    report = audit_files(
        args.before,
        args.after,
        max_removed=args.max_removed,
        max_category_changes=args.max_category_changes,
        max_logo_replacements=args.max_logo_replacements,
        fail_on_stream_change=args.fail_on_stream_change,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

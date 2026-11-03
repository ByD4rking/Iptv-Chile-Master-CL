from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime
from typing import Callable


BAD_NAME = re.compile(
    r"user.?agent|mozilla|like gecko|vlc/|libvlc|group-title|http/|safari/|chrome/|firefox/|player=",
    re.I,
)


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed
    except ValueError:
        return None


def _same_run(value, run_started_at):
    left = _parse_time(value)
    right = _parse_time(run_started_at)
    if not left or not right:
        return False
    if left.tzinfo is None and right.tzinfo is not None:
        left = left.replace(tzinfo=right.tzinfo)
    if right.tzinfo is None and left.tzinfo is not None:
        right = right.replace(tzinfo=left.tzinfo)
    return abs((left - right).total_seconds()) <= 5


def _stable_name(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"\s*\[(?:opc(?:ion)?\.?\s*\d+|v\d+)\]\s*$", "", text, flags=re.I)
    text = re.sub(r"\s*\((?:4k|uhd|fhd|hd|sd|\d{3,4}p)\)\s*$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _candidate_identity(candidate, normalize_label):
    tvg_id = str(candidate.get("tvg_id") or "").strip()
    if tvg_id:
        return "tvgid:" + normalize_label(tvg_id)
    group = normalize_label(candidate.get("group") or "")
    name = _stable_name(candidate.get("name") or "")
    if not name:
        return ""
    return f"name:{group}|{name}"


def _source_status(health, run_started_at):
    successful = set()
    unavailable = set()
    for name, state in (health or {}).items():
        last_success = state.get("last_success")
        last_failure = state.get("last_failure")
        last_skip = state.get("last_skip")
        if _same_run(last_success, run_started_at) and not _same_run(last_failure, run_started_at):
            successful.add(name)
        elif _same_run(last_failure, run_started_at) or _same_run(last_skip, run_started_at):
            unavailable.add(name)
        else:
            unavailable.add(name)
    return successful, unavailable


def merge_auto_catalog(
    discovery,
    health,
    previous_state,
    catalog_channels,
    normalize_label: Callable[[str], str],
):
    """Build a persistent auto-discovered catalog with 3-run disappearance confirmation."""
    run_started_at = discovery.get("run_started_at")
    successful_sources, unavailable_sources = _source_status(health, run_started_at)
    health_names = set((health or {}).keys())

    catalog_names = set()
    catalog_urls = set()
    for channel in catalog_channels or []:
        catalog_names.update(
            normalize_label(value)
            for value in [channel.get("name"), *(channel.get("aliases") or [])]
            if normalize_label(value)
        )
        for source in channel.get("sources") or []:
            url = str(source.get("url") or "").strip()
            if url:
                catalog_urls.add(url)

    current = {}
    for profile, entries in (discovery.get("profiles") or {}).items():
        for candidate in entries or []:
            name = str(candidate.get("name") or "").strip()
            group = str(candidate.get("group") or "").strip() or str(profile)
            url = str(candidate.get("url") or "").strip()
            source_name = str(candidate.get("source") or "").strip()
            if (
                len(name) < 3
                or len(name) > 100
                or BAD_NAME.search(name)
                or not url.startswith(("http://", "https://"))
                or not source_name
            ):
                continue
            if normalize_label(name) in catalog_names or url in catalog_urls:
                continue

            identity = _candidate_identity(candidate, normalize_label)
            if not identity:
                continue
            channel_id = "auto-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
            channel_key = "auto:" + identity
            priority = int((health or {}).get(source_name, {}).get("priority") or 0)
            item = current.setdefault(
                channel_id,
                {
                    "id": channel_id,
                    "channel_key": channel_key,
                    "name": name,
                    "group": group,
                    "logo": str(candidate.get("logo") or "").strip(),
                    "aliases": [],
                    "profiles": [],
                    "sources": [],
                    "missing_runs": 0,
                    "last_seen": discovery.get("generated_at"),
                    "_priority": priority,
                },
            )
            if priority > item.get("_priority", 0):
                if item["name"] != name and item["name"] not in item["aliases"]:
                    item["aliases"].append(item["name"])
                item["name"] = name
                item["group"] = group
                if candidate.get("logo"):
                    item["logo"] = str(candidate["logo"]).strip()
                item["_priority"] = priority
            elif name != item["name"] and name not in item["aliases"]:
                item["aliases"].append(name)
            if profile not in item["profiles"]:
                item["profiles"].append(profile)

            source_record = {
                "url": url,
                "source": source_name,
                "priority": priority,
                "match": "automatic_discovery",
                "channel_key": channel_key,
            }
            existing = next((entry for entry in item["sources"] if entry["url"] == url), None)
            if existing is None:
                item["sources"].append(source_record)
            elif priority > int(existing.get("priority") or 0):
                existing.update(source_record)

    previous_channels = {
        str(item.get("id") or ""): dict(item)
        for item in (previous_state or {}).get("channels", [])
        if item.get("id")
    }
    merged = {}
    removed_confirmed = 0

    for channel_id, current_item in current.items():
        previous = previous_channels.pop(channel_id, None)
        sources = {entry["url"]: dict(entry) for entry in current_item["sources"]}
        if previous:
            for old_source in previous.get("sources") or []:
                source_name = str(old_source.get("source") or "")
                if source_name in unavailable_sources or source_name not in health_names:
                    sources.setdefault(str(old_source.get("url") or ""), dict(old_source))
        current_item["sources"] = sorted(
            [entry for url, entry in sources.items() if url],
            key=lambda entry: (-int(entry.get("priority") or 0), entry["url"]),
        )
        current_item["missing_runs"] = 0
        current_item["last_seen"] = discovery.get("generated_at")
        current_item.pop("_priority", None)
        merged[channel_id] = current_item

    for channel_id, previous in previous_channels.items():
        owners = {
            str(source.get("source") or "")
            for source in previous.get("sources") or []
            if source.get("source")
        }
        removed_from_config = owners - health_names
        if owners and owners.issubset(successful_sources | removed_from_config):
            missing_runs = int(previous.get("missing_runs") or 0) + 1
        else:
            missing_runs = int(previous.get("missing_runs") or 0)

        if missing_runs >= 3:
            removed_confirmed += 1
            continue

        previous["missing_runs"] = missing_runs
        merged[channel_id] = previous

    channels = sorted(
        merged.values(),
        key=lambda item: (
            str(item.get("group") or "").casefold(),
            str(item.get("name") or "").casefold(),
            str(item.get("id") or ""),
        ),
    )

    auto_channels = []
    for item in channels:
        auto_channels.append({
            "id": item["id"],
            "name": item["name"],
            "group": item["group"],
            "logo": item.get("logo") or "",
            "aliases": list(item.get("aliases") or []),
            "channel_key": item["channel_key"],
            "sources": list(item.get("sources") or []),
            "auto_discovered": True,
            "source_profiles": list(item.get("profiles") or []),
        })

    state = {
        "schema_version": 1,
        "generated_at": discovery.get("generated_at"),
        "channels": channels,
    }
    stats = {
        "current_candidates": len(current),
        "auto_catalog_channels": len(channels),
        "removed_after_three_successful_runs": removed_confirmed,
        "successful_sources": len(successful_sources),
        "unavailable_sources": len(unavailable_sources),
    }
    return auto_channels, state, stats

from __future__ import annotations

import json
import re
from pathlib import Path

from channels import GROUPS, normalize_channel
from client import PlutoClient
from regions import REGIONS, Region


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
PLAYLIST_DIR = OUTPUT_DIR / "playlists"
REGIONAL_DATA_DIR = OUTPUT_DIR / "regional"

# Do not replace a known-good playlist with a catastrophic partial response.
# A normal Pluto change can still reduce the count; this only protects against
# empty/very-low responses that commonly happen during transient API failures.
MIN_PREVIOUS_RATIO = 0.50

# No maximum channel count: every valid channel returned by Pluto is eligible.



def fetch_region(region: Region) -> list[dict]:
    client = PlutoClient(region)
    print(f"[{region.code.upper()}] Obteniendo canales...")
    raw = client.get_channels()
    print(f"[{region.code.upper()}] Canales devueltos por Pluto: {len(raw)}")

    normalized = []
    rejected = 0
    seen_ids = set()

    for channel in raw:
        channel_id = channel.get("id")
        if not channel_id or channel_id in seen_ids:
            continue
        try:
            item = normalize_channel(client, channel)
            normalized.append(item)
            seen_ids.add(channel_id)
        except Exception as exc:
            rejected += 1
            print(f"[{region.code.upper()}] No se pudo procesar {channel_id}: {exc}")

    print(f"[{region.code.upper()}] Canales válidos incorporables: {len(normalized)}; rechazados: {rejected}")
    return normalized


def valid_stream(stream: str) -> bool:
    return bool(
        stream
        and stream.startswith(("http://", "https://"))
        and ".m3u8" in stream
    )


def esc(value) -> str:
    return "" if value is None else str(value).replace('"', "'").strip()


def channel_to_m3u(channel: dict, region: Region) -> str:
    channel_id = esc(channel.get("id"))
    name = esc(channel.get("name"))
    stream = esc(channel.get("stream"))
    logo = esc(channel.get("logo"))
    group = esc(channel.get("category")) or "Otros"

    if not channel_id or not name or not valid_stream(stream):
        return ""

    return (
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" '
        f'tvg-logo="{logo}" group-title="{group}",{name}\n'
        f'{stream}\n'
    )


def sort_key(channel: dict) -> tuple:
    group = channel.get("category") or "Otros"
    group_index = GROUPS.index(group) if group in GROUPS else len(GROUPS)
    try:
        number = int(channel.get("number"))
    except (TypeError, ValueError):
        number = 999999
    return (group_index, number, str(channel.get("name") or "").lower())


def previous_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        text = path.read_text(encoding="utf-8-sig")
        return len(re.findall(r"^#EXTINF:", text, flags=re.MULTILINE))
    except Exception:
        return 0


def build_playlist(channels: list[dict], region: Region) -> str:
    ordered = sorted(channels, key=sort_key)
    lines = ["#EXTM3U"]
    seen = set()

    for channel in ordered:
        stream = channel.get("stream") or ""
        channel_id = channel.get("id") or ""
        # Prefer stable channel identity, then stream URL as fallback.
        key = channel_id or stream
        if key in seen:
            continue
        entry = channel_to_m3u(channel, region)
        if entry:
            lines.append(entry.rstrip())
            seen.add(key)

    if len(seen) == 0:
        raise RuntimeError(f"{region.code.upper()}: no hay canales válidos.")

    return "\n".join(lines) + "\n"


def write_if_safe(region: Region, channels: list[dict]) -> tuple[Path, int, bool]:
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
    REGIONAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    playlist_path = PLAYLIST_DIR / f"pluto_{region.code}.m3u"
    data_path = REGIONAL_DATA_DIR / f"channels_{region.code}.json"

    content = build_playlist(channels, region)
    new_count = content.count("#EXTINF:")
    old_count = previous_count(playlist_path)

    if old_count and new_count < max(1, int(old_count * MIN_PREVIOUS_RATIO)):
        print(
            f"[{region.code.upper()}] BLOQUEADO: {new_count} canales nuevos "
            f"frente a {old_count} anteriores. Se conserva la lista anterior."
        )
        return playlist_path, old_count, False

    tmp_playlist = playlist_path.with_suffix(".m3u.tmp")
    tmp_data = data_path.with_suffix(".json.tmp")

    tmp_playlist.write_text(content, encoding="utf-8")
    tmp_data.write_text(
        json.dumps(channels, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    tmp_playlist.replace(playlist_path)
    tmp_data.replace(data_path)

    print(f"[{region.code.upper()}] {new_count} canales -> {playlist_path}")
    return playlist_path, new_count, True


def build_all() -> Path:
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

    paths = [PLAYLIST_DIR / f"pluto_{code}.m3u" for code in REGIONS]
    lines = ["#EXTM3U"]
    seen_ids = set()
    total = 0

    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig")
        chunks = re.split(r"(?=^#EXTINF:)", text, flags=re.MULTILINE)

        for chunk in chunks:
            if not chunk.startswith("#EXTINF:"):
                continue

            lines_chunk = chunk.strip().splitlines()
            if len(lines_chunk) < 2:
                continue

            match = re.search(r'tvg-id="([^"]+)"', lines_chunk[0])
            key = match.group(1) if match else lines_chunk[1]

            if key in seen_ids:
                continue

            lines.extend(lines_chunk[:2])
            seen_ids.add(key)
            total += 1

    if total == 0:
        raise RuntimeError("No hay listas regionales válidas para construir pluto_all.m3u.")

    output = PLAYLIST_DIR / "pluto_all.m3u"
    tmp = output.with_suffix(".m3u.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(output)

    # Backward compatibility: pluto.m3u remains the MX-compatible legacy entry.
    mx = PLAYLIST_DIR / "pluto_mx.m3u"
    legacy = PLAYLIST_DIR / "pluto.m3u"
    if mx.exists():
        legacy.write_text(mx.read_text(encoding="utf-8-sig"), encoding="utf-8")

    print(f"[ALL] {total} canales únicos -> {output}")
    return output


def main() -> None:
    print("================================")
    print("PLUTO TV MULTIRREGIONAL")
    print("================================")

    results = {}
    for code, region in REGIONS.items():
        try:
            channels = fetch_region(region)
            path, count, updated = write_if_safe(region, channels)
            results[code] = (count, updated)
        except Exception as exc:
            # A single regional failure must not stop the other regions.
            print(f"[{code.upper()}] ERROR: {exc}")
            results[code] = (0, False)

    build_all()

    print()
    print("RESUMEN")
    for code, (count, updated) in results.items():
        state = "actualizada" if updated else "conservada/no actualizada"
        print(f"{code.upper()}: {count} canales - {state}")


if __name__ == "__main__":
    main()

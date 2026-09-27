from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from channels import GROUPS


BASE_DIR = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE_DIR / "output" / "channels.json"
PLAYLIST_DIR = BASE_DIR / "output" / "playlists"


def esc(value) -> str:
    if value is None:
        return ""
    return str(value).replace('"', "'").strip()


def valid_stream(stream: str) -> bool:
    if not stream:
        return False

    try:
        parsed = urlparse(stream)
        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
            and ".m3u8" in parsed.path
        )
    except Exception:
        return False


def channel_to_m3u(channel: dict) -> str:
    channel_id = esc(channel.get("id"))
    name = esc(channel.get("name"))
    stream = esc(channel.get("stream"))
    logo = esc(channel.get("logo"))
    group = esc(channel.get("category")) or "Otros"

    if not channel_id or not name or not valid_stream(stream):
        return ""

    return (
        f'#EXTINF:-1 tvg-id="{channel_id}" '
        f'tvg-name="{name}" tvg-logo="{logo}" '
        f'group-title="{group}",{name}\n'
        f'{stream}\n'
    )


def channel_sort_key(channel: dict) -> tuple:
    group = channel.get("category") or "Otros"
    group_index = GROUPS.index(group) if group in GROUPS else len(GROUPS)
    number = channel.get("number")
    try:
        number_key = int(number)
    except (TypeError, ValueError):
        number_key = 999999

    return (group_index, number_key, str(channel.get("name") or "").lower())


def generate_all(channels: list[dict]) -> Path:
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)

    lines = ["#EXTM3U"]
    valid_count = 0
    seen_streams = set()
    ordered = sorted(channels, key=channel_sort_key)

    for channel in ordered:
        stream = channel.get("stream") or ""
        if stream in seen_streams:
            continue

        entry = channel_to_m3u(channel)
        if not entry:
            continue

        lines.append(entry.rstrip())
        seen_streams.add(stream)
        valid_count += 1

    if valid_count == 0:
        raise RuntimeError("No se pudo generar ningún canal válido.")

    output = PLAYLIST_DIR / "pluto.m3u"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("================================")
    print("PLAYLIST PLUTO GENERADA")
    print("================================")
    print(f"Canales recibidos: {len(channels)}")
    print(f"Canales válidos: {valid_count}")
    print(f"Duplicados por URL omitidos: {len(ordered) - valid_count}")
    print(f"Archivo: {output}")
    print(f"Tamaño: {output.stat().st_size:,} bytes")
    print()
    print("DISTRIBUCIÓN POR CARPETA")

    for group in GROUPS:
        count = sum(
            1 for channel in ordered
            if (channel.get("category") or "Otros") == group
        )
        if count:
            print(f"{group}: {count}")

    return output


def main() -> None:
    print("Cargando canales...")

    if not CHANNELS_FILE.exists():
        raise FileNotFoundError(f"No existe: {CHANNELS_FILE}")

    channels = json.loads(
        CHANNELS_FILE.read_text(encoding="utf-8-sig")
    )

    if not isinstance(channels, list):
        raise RuntimeError("channels.json no contiene una lista válida.")

    generate_all(channels)


if __name__ == "__main__":
    main()

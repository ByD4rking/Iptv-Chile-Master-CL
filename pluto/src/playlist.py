from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


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
    group = esc(channel.get("category")) or "Pluto TV"

    if not channel_id:
        return ""

    if not name:
        return ""

    if not valid_stream(stream):
        return ""

    return (
        f'#EXTINF:-1 '
        f'tvg-id="{channel_id}" '
        f'tvg-name="{name}" '
        f'tvg-logo="{logo}" '
        f'group-title="{group}",{name}\n'
        f'{stream}\n'
    )


def generate_all(channels: list[dict]) -> Path:
    PLAYLIST_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = ["#EXTM3U"]

    valid_count = 0

    for channel in channels:
        entry = channel_to_m3u(channel)

        if not entry:
            continue

        lines.append(entry.rstrip())
        valid_count += 1

    if valid_count == 0:
        raise RuntimeError(
            "No se pudo generar ningún canal válido."
        )

    output = PLAYLIST_DIR / "pluto.m3u"

    output.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print()
    print("================================")
    print("PLAYLIST PLUTO GENERADA")
    print("================================")
    print(f"Canales recibidos: {len(channels)}")
    print(f"Canales válidos: {valid_count}")
    print(f"Archivo: {output}")
    print(f"Tamaño: {output.stat().st_size:,} bytes")

    return output


def main() -> None:
    print("Cargando canales...")

    if not CHANNELS_FILE.exists():
        raise FileNotFoundError(
            f"No existe: {CHANNELS_FILE}"
        )

    channels = json.loads(
        CHANNELS_FILE.read_text(
            encoding="utf-8-sig"
        )
    )

    if not isinstance(channels, list):
        raise RuntimeError(
            "channels.json no contiene una lista válida."
        )

    generate_all(channels)


if __name__ == "__main__":
    main()

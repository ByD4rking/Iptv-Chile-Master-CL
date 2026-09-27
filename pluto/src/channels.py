from __future__ import annotations

import json
from pathlib import Path

from client import PlutoClient


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"


def normalize_channel(client: PlutoClient, channel: dict) -> dict:
    channel_id = channel.get("id", "")

    return {
        "id": channel_id,
        "name": channel.get("name", ""),
        "slug": channel.get("slug", ""),
        "description": channel.get("description", ""),
        "number": channel.get("number"),
        "category": channel.get("category"),
        "country": channel.get("country"),
        "region": channel.get("region"),
        "language": channel.get("language"),
        "logo": channel.get("logo", ""),
        "stream": client.build_stream_url(channel_id),
    }


def fetch_channels() -> list[dict]:
    client = PlutoClient()

    print("Obteniendo canales de Pluto...")
    channels = client.get_channels()

    normalized = []

    for channel in channels:
        channel_id = channel.get("id")

        if not channel_id:
            continue

        try:
            normalized.append(
                normalize_channel(client, channel)
            )
        except Exception as exc:
            print(
                f"No se pudo procesar "
                f"{channel_id}: {exc}"
            )

    return normalized


def save_channels(channels: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = OUTPUT_DIR / "channels.json"

    output_file.write_text(
        json.dumps(
            channels,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return output_file


if __name__ == "__main__":
    channels = fetch_channels()

    output_file = save_channels(channels)

    print()
    print("================================")
    print("GENERACIÓN DE CANALES COMPLETA")
    print("================================")
    print(f"Canales válidos: {len(channels)}")
    print(f"Archivo: {output_file}")

    if channels:
        print()
        print("Ejemplo:")

        first = channels[0]

        print("ID:", first["id"])
        print("Nombre:", first["name"])
        print("Slug:", first["slug"])
        print("Stream generado: SÍ")

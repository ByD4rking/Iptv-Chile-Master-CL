from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, Response, jsonify, abort, redirect

from client import PlutoClient


BASE_DIR = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE_DIR / "output" / "channels.json"

app = Flask(__name__)
client = PlutoClient()


def load_channels() -> list[dict]:
    if not CHANNELS_FILE.exists():
        raise RuntimeError(
            f"No existe el archivo: {CHANNELS_FILE}"
        )

    return json.loads(
        CHANNELS_FILE.read_text(
            encoding="utf-8-sig"
        )
    )


def find_channel(channel_id: str) -> dict | None:
    for channel in load_channels():
        if channel.get("id") == channel_id:
            return channel

    return None


@app.get("/")
def index():
    return jsonify(
        {
            "name": "Pluto Local API",
            "status": "ok",
            "endpoints": [
                "/channels",
                "/playlist.m3u",
                "/stream/<channel_id>",
            ],
        }
    )


@app.get("/channels")
def channels():
    return jsonify(load_channels())


@app.get("/playlist.m3u")
def playlist():
    channels_data = load_channels()

    lines = ["#EXTM3U"]

    for channel in channels_data:
        channel_id = channel.get("id", "")
        name = channel.get("name", "")
        logo = channel.get("logo", "")
        category = channel.get("category") or "Pluto TV"

        if not channel_id:
            continue

        lines.append(
            f'#EXTINF:-1 '
            f'tvg-id="{channel_id}" '
            f'tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{category}",'
            f'{name}'
        )

        lines.append(
            f'http://127.0.0.1:5000/stream/{channel_id}'
        )

    body = "\n".join(lines) + "\n"

    return Response(
        body,
        status=200,
        mimetype="audio/x-mpegurl",
        headers={
            "Content-Disposition": 'inline; filename="pluto.m3u"',
            "Cache-Control": "no-cache",
        },
    )


@app.get("/stream/<channel_id>")
def stream(channel_id: str):
    channel = find_channel(channel_id)

    if not channel:
        abort(
            404,
            description="Canal no encontrado"
        )

    try:
        stream_url = client.build_stream_url(channel_id)

        return redirect(
            stream_url,
            code=302,
        )

    except Exception:
        try:
            client.boot()

            stream_url = client.build_stream_url(
                channel_id
            )

            return redirect(
                stream_url,
                code=302,
            )

        except Exception as exc:
            abort(
                502,
                description=str(exc),
            )


if __name__ == "__main__":
    print("================================")
    print("PLUTO LOCAL SERVER")
    print("================================")
    print()
    print("API:")
    print("  http://127.0.0.1:5000/")
    print("  http://127.0.0.1:5000/channels")
    print("  http://127.0.0.1:5000/playlist.m3u")
    print()
    print("Iniciando servidor...")
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )

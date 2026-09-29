from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from flask import Flask, Response, abort, jsonify

from client import PlutoClient


BASE_DIR = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE_DIR / "output" / "channels.json"

app = Flask(__name__)
client = PlutoClient()

PROXY_TIMEOUT = (5, 20)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)


def load_channels() -> list[dict]:
    if not CHANNELS_FILE.exists():
        raise RuntimeError(f"No existe el archivo: {CHANNELS_FILE}")
    return json.loads(CHANNELS_FILE.read_text(encoding="utf-8-sig"))


def find_channel(channel_id: str) -> dict | None:
    for channel in load_channels():
        if channel.get("id") == channel_id:
            return channel
    return None


def _encode_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_url(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")


def _allowed_upstream(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower().endswith(".pluto.tv")
        and parsed.path.endswith((".m3u8", ".ts", ".m4s", ".mp4", ".aac", ".mp3"))
    )


def _upstream_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.apple.mpegurl, video/*, audio/*, */*",
        "Origin": "https://pluto.tv",
        "Referer": "https://pluto.tv/",
    }


def _fetch(url: str) -> requests.Response:
    response = client.session.get(
        url,
        headers=_upstream_headers(),
        timeout=PROXY_TIMEOUT,
        stream=False,
    )
    if response.status_code in (401, 403, 404, 410, 429, 500, 502, 503, 504):
        client.boot()
        raise requests.HTTPError(
            f"upstream transient/auth failure: {response.status_code}",
            response=response,
        )
    response.raise_for_status()
    return response


def _rewrite_playlist(text: str, base_url: str, channel_id: str) -> str:
    output: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            output.append(line)
            continue

        absolute = urljoin(base_url, stripped)
        if _allowed_upstream(absolute):
            output.append(
                f"/pluto-proxy/{channel_id}/{_encode_url(absolute)}"
            )
        else:
            output.append(line)

    return "\n".join(output) + "\n"


@app.get("/")
def index():
    return jsonify(
        {
            "name": "Pluto Local API",
            "status": "ok",
            "reconnect": "enabled",
            "endpoints": [
                "/channels",
                "/playlist.m3u",
                "/stream/<channel_id>",
                "/pluto-proxy/<channel_id>/<encoded_url>",
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
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="{category}",{name}'
        )
        lines.append(f"http://127.0.0.1:5000/stream/{channel_id}")

    body = "\n".join(lines) + "\n"
    return Response(
        body,
        status=200,
        mimetype="audio/x-mpegurl",
        headers={
            "Content-Disposition": 'inline; filename="pluto.m3u"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.get("/stream/<channel_id>")
def stream(channel_id: str):
    channel = find_channel(channel_id)
    if not channel:
        abort(404, description="Canal no encontrado")

    # Return a local URL rather than a one-time Pluto URL. The local proxy owns
    # session renewal, so the player can keep using the same M3U entry.
    return Response(
        f"#EXTM3U\n"
        f"#EXT-X-STREAM-INF:BANDWIDTH=1\n"
        f"/pluto-master/{channel_id}.m3u8\n",
        mimetype="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/pluto-master/<channel_id>.m3u8")
def pluto_master(channel_id: str):
    channel = find_channel(channel_id)
    if not channel:
        abort(404, description="Canal no encontrado")

    last_error: Exception | None = None
    for _ in range(3):
        try:
            upstream = client.build_stream_url(channel_id)
            response = _fetch(upstream)
            text = _rewrite_playlist(response.text, upstream, channel_id)
            return Response(
                text,
                mimetype="application/vnd.apple.mpegurl",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        except Exception as exc:
            last_error = exc
            try:
                client.boot()
            except Exception as boot_exc:
                last_error = boot_exc

    abort(502, description=f"Pluto no disponible tras 3 intentos: {last_error}")


@app.get("/pluto-proxy/<channel_id>/<encoded_url>")
def pluto_proxy(channel_id: str, encoded_url: str):
    channel = find_channel(channel_id)
    if not channel:
        abort(404, description="Canal no encontrado")

    try:
        upstream = _decode_url(encoded_url)
    except Exception:
        abort(400, description="URL proxy inválida")

    if not _allowed_upstream(upstream):
        abort(403, description="Origen no permitido")

    last_error: Exception | None = None
    for _ in range(3):
        try:
            response = _fetch(upstream)
            content_type = response.headers.get("content-type", "").lower()

            if ".m3u8" in upstream or "mpegurl" in content_type:
                body = _rewrite_playlist(response.text, upstream, channel_id)
                return Response(
                    body,
                    status=200,
                    mimetype="application/vnd.apple.mpegurl",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                )

            return Response(
                response.content,
                status=200,
                content_type=response.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except Exception as exc:
            last_error = exc
            try:
                client.boot()
            except Exception as boot_exc:
                last_error = boot_exc

    abort(502, description=f"Reconexion Pluto agotada: {last_error}")


if __name__ == "__main__":
    print("================================")
    print("PLUTO LOCAL SERVER")
    print("RECONEXION AUTOMATICA HABILITADA")
    print("================================")
    print()
    app.run(host="127.0.0.1", port=5000, debug=False)

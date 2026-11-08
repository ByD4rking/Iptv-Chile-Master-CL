"""Filtro estricto de calidad para canales MAGMA de Cine / Películas.

Solo se aceptan señales verificadas como 1920x1080 progresivas y 16:9.
Los errores de red/sondeo se clasifican como no verificados y nunca provocan
borrados: solo una medición explícita de otra calidad permite excluir el canal.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from urllib.parse import urljoin

import requests

UA = "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
TIMEOUT = 10
MAX_PLAYLIST_BYTES = 512 * 1024
CINE_CATEGORIES = {
    "cine / peliculas", "cine / películas",
    "cine / peliculas premium", "cine / películas premium",
}


def _ratio(value: str | None) -> tuple[int, int] | None:
    if not value or ":" not in value:
        return None
    try:
        left, right = value.split(":", 1)
        a, b = int(left), int(right)
        return (a, b) if a > 0 and b > 0 else None
    except (TypeError, ValueError):
        return None


def _probe_variant(url: str) -> dict:
    if not shutil.which("ffprobe"):
        return {"status": "unknown", "reason": "ffprobe-no-instalado"}
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-user_agent", UA,
                "-rw_timeout", str(TIMEOUT * 1_000_000),
                "-select_streams", "v:0",
                "-show_entries",
                "stream=width,height,field_order,display_aspect_ratio,sample_aspect_ratio",
                "-of", "json", url,
            ],
            capture_output=True, text=True, timeout=TIMEOUT + 2, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unknown", "reason": "sondeo-no-disponible"}
    if proc.returncode != 0:
        return {"status": "unknown", "reason": "ffprobe-sin-datos"}
    try:
        streams = json.loads(proc.stdout).get("streams", [])
        if not streams:
            return {"status": "unknown", "reason": "sin-video"}
        stream = streams[0]
        width, height = stream.get("width"), stream.get("height")
        field_order = str(stream.get("field_order") or "").lower()
        dar = _ratio(stream.get("display_aspect_ratio"))
        sar = _ratio(stream.get("sample_aspect_ratio"))
        if dar is None and width and height and sar:
            dar = (width * sar[0], height * sar[1])
        details = {
            "resolution": f"{width}x{height}" if width and height else None,
            "display_aspect_ratio": f"{dar[0]}:{dar[1]}" if dar else None,
            "field_order": field_order or None,
        }
        if width != 1920 or height != 1080:
            return {"status": "reject", "reason": "resolucion-distinta-de-1920x1080", **details}
        if dar is None:
            return {"status": "unknown", "reason": "aspect-ratio-no-verificable", **details}
        if dar[0] * 9 != dar[1] * 16:
            return {"status": "reject", "reason": "aspect-ratio-distinto-de-16:9", **details}
        if field_order != "progressive":
            if field_order in {"tt", "bb", "tb", "bt"}:
                return {"status": "reject", "reason": "video-entrelazado", **details}
            return {"status": "unknown", "reason": "progresivo-no-verificable", **details}
        return {"status": "accept", "reason": "1920x1080p-16:9-verificado", **details}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"status": "unknown", "reason": "respuesta-ffprobe-invalida"}


def probe_stream(url: str, session: requests.Session | None = None) -> dict:
    """Inspecciona HLS master/media y verifica la señal real con ffprobe."""
    own_session = session is None
    client = session or requests.Session()
    try:
        response = client.get(
            url, headers={"User-Agent": UA, "Accept": "*/*"},
            timeout=TIMEOUT, stream=True,
        )
        if response.status_code >= 400:
            response.close()
            return {"status": "unknown", "reason": f"http-{response.status_code}"}
        content_type = response.headers.get("Content-Type", "").lower()
        is_playlist = ".m3u8" in url.lower() or "mpegurl" in content_type
        if not is_playlist:
            response.close()
            return _probe_variant(url)
        body = response.raw.read(MAX_PLAYLIST_BYTES + 1)
        final_url = response.url
        response.close()
        if len(body) > MAX_PLAYLIST_BYTES:
            return {"status": "unknown", "reason": "playlist-demasiado-grande"}
        text = body.decode("utf-8", errors="replace")
        if "#EXTM3U" not in text:
            return {"status": "unknown", "reason": "respuesta-no-es-m3u8"}
        lines = text.splitlines()
        variants = []
        for index, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF:"):
                continue
            attrs = line.split(":", 1)[1]
            resolution = re.search(r"RESOLUTION=(\d+x\d+)", attrs, re.I)
            if index + 1 >= len(lines):
                continue
            variant_url = lines[index + 1].strip()
            if variant_url and not variant_url.startswith("#"):
                variants.append({
                    "resolution": resolution.group(1) if resolution else None,
                    "url": urljoin(final_url, variant_url),
                })
        if variants:
            hd_variants = [item for item in variants if item["resolution"] == "1920x1080"]
            if not hd_variants:
                return {
                    "status": "reject",
                    "reason": "master-sin-variante-1920x1080",
                    "variants": [item["resolution"] for item in variants],
                }
            results = [_probe_variant(item["url"]) for item in hd_variants]
            accepted = next((item for item in results if item["status"] == "accept"), None)
            if accepted:
                return accepted
            rejected = next((item for item in results if item["status"] == "reject"), None)
            return rejected or {"status": "unknown", "reason": "variante-1080-no-verificable"}
        return _probe_variant(final_url)
    except requests.RequestException:
        return {"status": "unknown", "reason": "error-de-red"}
    finally:
        if own_session:
            client.close()


def _is_cinema(channel: dict) -> bool:
    category = str(channel.get("categoria", "")).strip().lower()
    return category in CINE_CATEGORIES


_QUALITY_CACHE: dict[str, dict] = {}


def clear_probe_cache() -> None:
    _QUALITY_CACHE.clear()


def audit_and_filter_channels(channels: list[dict], probe=probe_stream) -> tuple[list[dict], list[dict], list[dict]]:
    """Devuelve canales permitidos, rechazados y no verificados."""
    allowed, rejected, unverified = [], [], []
    for channel in channels:
        if not _is_cinema(channel):
            allowed.append(channel)
            continue
        url = str(channel.get("url", "")).strip()
        if url not in _QUALITY_CACHE:
            _QUALITY_CACHE[url] = probe(url)
        result = dict(_QUALITY_CACHE[url])
        item = {"channel": channel, **result}
        if result.get("status") == "accept":
            allowed.append(channel)
        elif result.get("status") == "reject":
            rejected.append(item)
        else:
            unverified.append(item)
    return allowed, rejected, unverified


def remove_rejected_cinema_blocks(lines: list[str], rejected_urls: set[str]) -> list[str]:
    """Elimina solo bloques Cine/Películas cuya URL fue rechazada por calidad."""
    if not rejected_urls:
        return list(lines)
    output = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("#EXTINF"):
            output.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and (not lines[end].strip() or lines[end].startswith("#")):
            end += 1
        url = lines[end].strip() if end < len(lines) else ""
        category = re.search(r'group-title="([^"]*)"', lines[index], re.I)
        normalized = (category.group(1).strip().lower() if category else "")
        if url in rejected_urls and normalized in CINE_CATEGORIES:
            index = end + 1
            continue
        output.extend(lines[index:end + 1])
        index = end + 1
    return output

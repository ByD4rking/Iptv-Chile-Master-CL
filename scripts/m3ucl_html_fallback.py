"""Fallback de solo lectura para la lista LATAM de M3U.CL cuando falta el archivo M3U."""
from __future__ import annotations

import base64
import binascii
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

LATAM_PAGE = "https://m3u.cl/lista-iptv-latam.php"


class _ChannelParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.channels: dict[tuple[str, str], dict[str, str]] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "td":
            return
        item = {str(k).lower(): str(v or "").strip() for k, v in attrs if k}
        encoded = item.get("reproducir_canal", "")
        channel_id = item.get("id_canal", "")
        if not encoded or not channel_id or item.get("nombre_lista", "").upper() != "LATAM":
            return
        try:
            decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True).decode("utf-8").strip()
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return
        parsed = urlparse(decoded)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return

        name = item.get("reproducir_nombre_canal", "").strip()
        if not name:
            return
        logo = item.get("reproducir_logo_canal", "").strip()
        if logo:
            logo = urljoin("https://m3u.cl/", logo)
        category = item.get("nombre_categoria", "").strip() or "Sin categoría"
        self.channels.setdefault((channel_id, decoded), {
            "name": name,
            "url": decoded,
            "logo": logo,
            "category": category,
        })


def build_latam_m3u(html: str) -> bytes:
    """Reconstruye M3U desde los datos públicos de la página oficial LATAM."""
    parser = _ChannelParser()
    parser.feed(str(html or ""))
    parser.close()
    if not parser.channels:
        raise ValueError("La página oficial M3U.CL LATAM no contiene canales utilizables")

    lines = ["#EXTM3U"]
    for (channel_id, _stream_url), channel in parser.channels.items():
        attrs = [
            f'tvg-id="m3ucl-latam-{escape(channel_id, quote=True)}"',
            f'tvg-name="{escape(channel["name"], quote=True)}"',
        ]
        if channel["logo"]:
            attrs.append(f'tvg-logo="{escape(channel["logo"], quote=True)}"')
        attrs.append(f'group-title="{escape(channel["category"], quote=True)}"')
        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{channel["name"]}')
        lines.append(channel["url"])
    return ("\n".join(lines) + "\n").encode("utf-8")

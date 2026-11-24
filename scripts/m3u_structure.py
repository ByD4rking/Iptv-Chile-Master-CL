"""Validación estructural estricta de listas M3U remotas antes de auditarlas."""
from __future__ import annotations

import re

ALLOWED_STREAM_SCHEMES = {
    "http", "https", "rtsp", "rtmp", "rtp", "udp", "mms", "mmsh", "mmst",
    "ftp", "acestream", "sop", "pvr", "plugin",
}


def normalize_m3u_bytes(data: bytes) -> bytes:
    """Normaliza solo BOM, saltos de línea y espacios periféricos; no inventa datos."""
    if not data:
        return data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("la fuente no contiene UTF-8 válido") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return b""
    return ("\n".join(lines) + "\n").encode("utf-8")


def validate_m3u_bytes(data: bytes, source: str = "fuente") -> int:
    """Valida cabecera y pares EXTINF/URI; devuelve el número de canales válidos.

    No intenta reparar HTML, respuestas parciales ni URLs. Ante ambigüedad falla
    de forma cerrada para impedir que una fuente inválida alimente una playlist.
    """
    if not data or not data.strip():
        raise ValueError(f"{source}: respuesta vacía")
    text = data.decode("utf-8-sig", errors="replace")
    lowered = text[:4096].casefold()
    if "<!doctype html" in lowered or "<html" in lowered or "<body" in lowered:
        raise ValueError(f"{source}: el servidor devolvió HTML, no una playlist M3U")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = lines[0].upper() if lines else ""
    if not (header == "#EXTM3U" or header.startswith("#EXTM3U ")):
        raise ValueError(f"{source}: falta cabecera #EXTM3U al inicio")

    entries = 0
    pending_extinf = False
    for line in lines[1:]:
        if line.upper().startswith("#EXTINF:"):
            if pending_extinf:
                raise ValueError(f"{source}: entrada #EXTINF sin URI antes de la siguiente entrada")
            if "," not in line or not line.rsplit(",", 1)[-1].strip():
                raise ValueError(f"{source}: línea #EXTINF mal formada o sin nombre")
            pending_extinf = True
            continue
        if line.startswith("#"):
            continue
        if pending_extinf:
            uri = re.match(r"^([a-z][a-z0-9+.-]*)://([^\s]+)$", line, re.I)
            if not uri or uri.group(1).casefold() not in ALLOWED_STREAM_SCHEMES:
                raise ValueError(f"{source}: URI de canal inválida: {line[:120]}")
            entries += 1
            pending_extinf = False

    if pending_extinf:
        raise ValueError(f"{source}: última entrada #EXTINF no tiene URI")
    if entries == 0:
        raise ValueError(f"{source}: no contiene pares #EXTINF/URI válidos")
    return entries

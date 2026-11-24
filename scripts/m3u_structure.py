"""Validación estructural estricta de listas M3U remotas antes de auditarlas."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

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


def _safe_source_label(source: str) -> str:
    """Evita incluir credenciales o query strings en mensajes de error."""
    try:
        parsed = urlsplit(str(source))
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.hostname or 'host remoto'}"
    except ValueError:
        pass
    return str(source).rsplit("/", 1)[-1][:80] or "fuente"

def validate_m3u_bytes(data: bytes, source: str = "fuente") -> int:
    """Valida cabecera y pares EXTINF/URI; devuelve el número de canales válidos.

    No intenta reparar HTML, respuestas parciales ni URLs. Ante ambigüedad falla
    de forma cerrada para impedir que una fuente inválida alimente una playlist.
    """
    source_label = _safe_source_label(source)
    if not data or not data.strip():
        raise ValueError(f"{source_label}: respuesta vacía")
    text = data.decode("utf-8-sig", errors="replace")
    lowered = text[:4096].casefold()
    if "<!doctype html" in lowered or "<html" in lowered or "<body" in lowered:
        raise ValueError(f"{source_label}: el servidor devolvió HTML, no una playlist M3U")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = lines[0].upper() if lines else ""
    if not (header == "#EXTM3U" or header.startswith("#EXTM3U ")):
        raise ValueError(f"{source_label}: falta cabecera #EXTM3U al inicio")

    entries = 0
    pending_extinf = False
    for line in lines[1:]:
        if line.upper().startswith("#EXTINF:"):
            if pending_extinf:
                raise ValueError(f"{source_label}: entrada #EXTINF sin URI antes de la siguiente entrada")
            if "," not in line or not line.rsplit(",", 1)[-1].strip():
                raise ValueError(f"{source_label}: línea #EXTINF mal formada o sin nombre")
            pending_extinf = True
            continue
        if line.startswith("#"):
            continue
        if not pending_extinf:
            raise ValueError(f"{source_label}: contenido suelto no asociado a #EXTINF: {line[:120]}")
        uri = re.match(r"^([a-z][a-z0-9+.-]*)://([^\s]+)$", line, re.I)
        try:
            parsed_uri = urlsplit(line)
            valid_authority = bool(parsed_uri.hostname)
        except ValueError:
            valid_authority = False
        if not uri or uri.group(1).casefold() not in ALLOWED_STREAM_SCHEMES or not valid_authority:
            raise ValueError(f"{source_label}: URI de canal inválida")
        pending_extinf = False
    if pending_extinf:
        raise ValueError(f"{source_label}: última entrada #EXTINF no tiene URI")
    if entries == 0:
        raise ValueError(f"{source_label}: no contiene pares #EXTINF/URI válidos")
    return entries

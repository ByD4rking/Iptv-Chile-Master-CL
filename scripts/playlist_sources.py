"""Carga y valida el registro editable de fuentes M3U del repositorio."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "playlist_sources.json"


def load_source_config() -> dict:
    if not CONFIG.is_file():
        raise FileNotFoundError(f"No existe el registro de fuentes: {CONFIG}")
    data = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    if data.get("schema_version") != 1:
        raise ValueError("Versión no compatible en config/playlist_sources.json")
    return data


def load_sources(scope: str) -> list[str]:
    data = load_source_config()
    section = data.get(scope) or {}
    sources = section.get("sources") or []
    urls = []
    names = set()
    seen_urls = set()
    for item in sources:
        name = str(item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        parsed = urlparse(url)
        if not name or not url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"Fuente inválida en scope '{scope}': {item!r}")
        if name in names:
            raise ValueError(f"Nombre de fuente duplicado en '{scope}': {name}")
        if url in seen_urls:
            raise ValueError(f"URL duplicada en '{scope}': {url}")
        names.add(name)
        seen_urls.add(url)
        urls.append(url)
    if not urls:
        raise ValueError(f"No hay fuentes configuradas para '{scope}'")
    return urls


def load_principal_settings() -> dict:
    data = load_source_config()
    principal = data.get("principal") or {}
    special = principal.get("special_sources") or {}
    required = {"iptvsv", "magma", "pluto_mx_alternatives"}
    missing = sorted(required - set(special))
    if missing:
        raise ValueError("Faltan fuentes especiales de Principal: " + ", ".join(missing))
    pluto = principal.get("pluto_sources") or []
    if not pluto:
        raise ValueError("Principal no tiene fuentes Pluto configuradas")
    return {
        "special_sources": special,
        "sources": load_sources("principal"),
        "pluto_sources": [x["url"] for x in pluto],
        "legacy_pluto_sources": [x["url"] for x in principal.get("legacy_pluto_sources", [])],
    }

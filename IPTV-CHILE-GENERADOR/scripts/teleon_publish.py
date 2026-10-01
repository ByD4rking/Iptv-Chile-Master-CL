import json
import re
from datetime import datetime, timezone
from pathlib import Path

from atomic import atomic_write_json, file_sha256

BASE = Path(__file__).resolve().parent.parent
DISCOVERY = BASE / "data" / "teleon_discovery.json"
QUALITY = BASE / "data" / "teleon_quality.json"
OUTPUT = BASE / "IPTV-CHILE-GENERADOR.m3u"
MANIFEST = BASE / "data" / "pipeline_manifest.json"

def clean(value):
    return str(value or "").replace("\n", " ").replace("\r", " ").strip()

def safe(value):
    return clean(value).replace('"', "'")

def load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default

def main():
    discovery = load(DISCOVERY, {})
    quality = load(QUALITY, {})
    text = OUTPUT.read_text(encoding="utf-8-sig")
    existing = {
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(("http://", "https://"))
    }

    by_url = {}
    for item in quality.get("results", []):
        url = clean(item.get("stream_url"))
        if url and item.get("playback_checked") and item.get("playback_ok"):
            by_url[url] = item

    metadata = {}
    for items in (discovery.get("profiles") or {}).values():
        for item in items:
            for url in item.get("stream_urls") or []:
                url = clean(url)
                if url and url not in metadata:
                    classification = item.get("classification") or {}
                    metadata[url] = {
                        "name": clean(item.get("channel_path", "").rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").title() or "Teleon",
                        "page_url": clean(item.get("page_url")),
                        "source": clean(item.get("source")) or "TELEON",
                        "language": clean(item.get("language")) or "es-419",
                        "region": clean(item.get("region")) or "LATAM",
                        "category": clean(classification.get("category")) or "Sin clasificar",
                        "profile": clean(classification.get("profile")) or "unclassified",
                        "confidence": classification.get("confidence", 0),
                        "headers": item.get("stream_headers") or {},
                    }

    additions = []
    for url, q in by_url.items():
        if url in existing:
            continue
        meta = metadata.get(url, {})
        name = meta.get("name") or "Teleon"
        language = meta.get("language") or "es-419"
        region = meta.get("region") or ("España" if language == "es-ES" else "Latinoamérica")
        category = meta.get("category") or "Sin clasificar"
        profile = meta.get("profile") or "unclassified"
        group = f"Teleon | {region} | {category}"
        tvg_id = "teleon-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        lines = [
            f'#EXTINF:-1 tvg-id="{safe(tvg_id)}" tvg-name="{safe(name)}" group-title="{safe(group)}",{name}',
            "#EXTVLCOPT:http-reconnect=true",
            "#EXTVLCOPT:network-caching=1500",
        ]
        for key, value in (meta.get("headers") or {}).items():
            if key.lower() == "referer":
                lines.append(f"#EXTVLCOPT:http-referrer={value}")
            elif key.lower() == "user-agent":
                lines.append(f"#EXTVLCOPT:http-user-agent={value}")
        lines.append(url)
        additions.extend(lines)
        existing.add(url)

    if additions:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n# TELEON DISCOVERY | solo streams HLS validados | candidato directo del generador\n"
        text += "\n".join(additions) + "\n"
        OUTPUT.write_text(text, encoding="utf-8")

    manifest = load(MANIFEST, {})
    manifest["m3u_sha256"] = file_sha256(OUTPUT)
    manifest["teleon_direct_candidates"] = len(additions) // 4 if additions else 0
    manifest["teleon_direct_published"] = True
    manifest["teleon_policy"] = "solo_playback_ok; sin DRM/auth bypass; categoria+idioma conservados"
    atomic_write_json(MANIFEST, manifest)

    print(f"Teleon directo: {manifest['teleon_direct_candidates']} streams añadidos a la M3U.")
    print("Solo se añaden streams con validación HLS/segmento correcta.")
    print(f"Salida: {OUTPUT}")

if __name__ == "__main__":
    main()

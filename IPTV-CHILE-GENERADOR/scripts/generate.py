import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
STATUS_FILE = BASE / "data" / "status.json"
QUALITY_FILE = BASE / "data" / "quality.json"
OUTPUT_FILE = BASE / "IPTV-CHILE-GENERADOR.m3u"

def load_json(path, default):
    if not path.exists(): return default
    try:
        with path.open("r", encoding="utf-8-sig") as f: return json.load(f)
    except Exception: return default

def clean(value): return "" if value is None else str(value).replace("\n", " ").replace("\r", " ").strip()

def quality_key(item): return (int(item.get("height") or 0), int(item.get("bitrate") or 0), -int(item.get("response_time_ms") or 0))

def main():
    channels = load_json(CHANNELS_FILE, [])
    status = load_json(STATUS_FILE, {})
    quality = load_json(QUALITY_FILE, {})
    online = {clean(x.get("url")): x for x in status.get("results", []) if x.get("online") and clean(x.get("url"))}
    quality_by_url = {clean(x.get("url")): x for x in quality.get("results", []) if clean(x.get("url"))}
    lines = ["#EXTM3U"]; emitted = set(); generated = 0
    for channel in channels:
        name = clean(channel.get("name")) or "Canal"; group = clean(channel.get("group")); logo = clean(channel.get("logo"))
        candidates = []
        for source in channel.get("sources", []):
            url = clean(source.get("url"))
            if url and url in online and url not in emitted: candidates.append((quality_key(quality_by_url.get(url, {})), url))
        if not candidates: continue
        candidates.sort(key=lambda x: x[0], reverse=True); url = candidates[0][1]
        attrs = [f'tvg-name="{name}"']
        if channel.get("id"): attrs.append(f'tvg-id="{clean(channel["id"])}"')
        if logo: attrs.append(f'tvg-logo="{logo}"')
        if group: attrs.append(f'group-title="{group}"')
        lines += ["#EXTINF:-1 " + " ".join(attrs) + "," + name, url]; emitted.add(url); generated += 1
    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generados: {generated} | URLs únicas: {len(emitted)} | {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__": main()
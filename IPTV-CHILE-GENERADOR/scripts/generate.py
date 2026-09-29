import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
STATUS_FILE = BASE / "data" / "status.json"
QUALITY_FILE = BASE / "data" / "quality.json"
OUTPUT_FILE = BASE / "IPTV-CHILE-GENERADOR.m3u"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def clean(value):
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("\r", " ").strip()


def quality_key(item):
    return (
        int(item.get("height") or 0),
        int(item.get("bitrate") or 0),
        -int(item.get("response_time_ms") or 0),
    )


def main():
    channels = load_json(CHANNELS_FILE, [])
    status = load_json(STATUS_FILE, {})
    quality = load_json(QUALITY_FILE, {})

    online = {
        clean(item.get("url")): item
        for item in status.get("results", [])
        if item.get("online") and clean(item.get("url"))
    }

    quality_by_url = {
        clean(item.get("url")): item
        for item in quality.get("results", [])
        if clean(item.get("url"))
    }

    lines = [
        "#EXTM3U",
        f'#EXTVLCOPT:http-referrer=""',
        f'# IPTV-CHILE-GENERADOR | {datetime.now(timezone.utc).date().isoformat()}',
    ]

    emitted = set()
    generated = 0

    for channel in channels:
        name = clean(channel.get("name")) or "Canal"
        group = clean(channel.get("group")) or "Chile"
        logo = clean(channel.get("logo"))

        candidates = []

        for source in channel.get("sources", []):
            url = clean(source.get("url"))
            if not url or url not in online or url in emitted:
                continue

            quality = quality_by_url.get(url, {})
            priority = int(source.get("priority") or 0)

            candidates.append(
                (
                    quality_key(quality),
                    priority,
                    url,
                )
            )

        if not candidates:
            continue

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        url = candidates[0][2]

        attrs = [f'tvg-name="{name}"']
        channel_id = clean(channel.get("id"))
        if channel_id:
            attrs.append(f'tvg-id="{channel_id}"')
        if logo:
            attrs.append(f'tvg-logo="{logo}"')
        attrs.append(f'group-title="{group}"')

        lines.append(
            "#EXTINF:-1 "
            + " ".join(attrs)
            + ","
            + name
        )
        lines.append(url)

        emitted.add(url)
        generated += 1

    OUTPUT_FILE.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - GENERATE")
    print("=" * 60)
    print(f"Canales analizados: {len(channels)}")
    print(f"Canales generados:  {generated}")
    print(f"URLs únicas M3U:    {len(emitted)}")
    print(f"Archivo:            {OUTPUT_FILE}")
    print("OK: salida independiente y deduplicada por URL.")


if __name__ == "__main__":
    main()

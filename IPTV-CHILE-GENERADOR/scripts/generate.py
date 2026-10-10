import json
from datetime import datetime, timezone
from pathlib import Path

from atomic import atomic_write_json, atomic_write_text, file_sha256

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
STATUS_FILE = BASE / "data" / "status.json"
QUALITY_FILE = BASE / "data" / "quality.json"
OUTPUT_FILE = BASE / "IPTV-CHILE-GENERADOR.m3u"
MANIFEST_FILE = BASE / "data" / "pipeline_manifest.json"


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


def quality_key(item, status_item, source):
    # La disponibilidad manda sobre la calidad nominal: primero preferimos
    # endpoints estables; después resolución/bitrate. Así un 720p estable no
    # pierde automáticamente frente a un 1080p que falla repetidamente.
    checks = int(item.get("endpoint_checks") or 0)
    successes = int(item.get("endpoint_successes") or 0)
    # Suavizado bayesiano: un endpoint con 1/1 no debe parecer tan fiable
    # como uno probado muchas veces. El prior Beta(1,1) evita decisiones
    # demasiado agresivas con muestras pequeñas.
    reliability = (successes + 1) / (checks + 2)
    return (
        -int(item.get("endpoint_consecutive_failures") or 0),
        reliability,
        checks,
        int(item.get("height") or 0),
        int(item.get("bitrate") or 0),
        -int(status_item.get("response_time_ms") or 999999),
        int(source.get("priority") or 0),
    )


def main():
    channels = load_json(CHANNELS_FILE, [])
    status = load_json(STATUS_FILE, {})
    quality = load_json(QUALITY_FILE, {})

    current_channels_sha = file_sha256(CHANNELS_FILE)
    if status.get("channels_sha256") != current_channels_sha:
        raise SystemExit(
            "INCONSISTENCIA: status.json no corresponde al channels.json actual."
        )
    if quality.get("channels_sha256") != current_channels_sha:
        raise SystemExit(
            "INCONSISTENCIA: quality.json no corresponde al channels.json actual."
        )

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
        f'# IPTV-CHILE-GENERADOR | {datetime.now(timezone.utc).date().isoformat()}',
        f"# IPTV-CHILE-GENERADOR-CHANNELS-SHA256: {current_channels_sha}",
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

            quality_item = quality_by_url.get(url)
            if not quality_item:
                continue
            if quality_item.get("quarantined"):
                continue
            if not quality_item.get("playback_checked") or not quality_item.get("playback_ok"):
                continue

            priority = int(source.get("priority") or 0)
            candidates.append(
                (
                    quality_key(quality_item, online[url], source),
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

        lines.append("#EXTINF:-1 " + " ".join(attrs) + "," + name)
        # Ayuda a reproductores compatibles a recuperar automáticamente el HTTP/HLS
        # ante cortes transitorios. No cambia la URL ni mezcla fuentes entre canales.
        lines.append("#EXTVLCOPT:http-reconnect=true")
        lines.append("#EXTVLCOPT:network-caching=5000")
        lines.append(url)
        emitted.add(url)
        generated += 1

    if not emitted:
        raise SystemExit("ABORTADO: no hay streams validados para publicar.")

    atomic_write_text(OUTPUT_FILE, "\n".join(lines) + "\n")

    manifest = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channels_sha256": current_channels_sha,
        "status_sha256": file_sha256(STATUS_FILE),
        "quality_sha256": file_sha256(QUALITY_FILE),
        "m3u_sha256": file_sha256(OUTPUT_FILE),
        "channels": len(channels),
        "generated_channels": generated,
        "output_urls": len(emitted),
        "channels_with_candidates": sum(1 for channel in channels if channel.get("sources")),
        "channels_with_multiple_candidates": sum(1 for channel in channels if len(channel.get("sources", [])) > 1),
        "quality_playback_ok": sum(
            1 for item in quality.get("results", []) if item.get("playback_ok")
        ),
    }
    atomic_write_json(MANIFEST_FILE, manifest)

    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - GENERATE")
    print("=" * 60)
    print(f"Canales analizados: {len(channels)}")
    print(f"Canales generados:  {generated}")
    print(f"URLs únicas M3U:    {len(emitted)}")
    print(f"Manifest:           {MANIFEST_FILE}")
    print("OK: salida independiente, deduplicada y consistente con sus etapas.")


if __name__ == "__main__":
    main()

import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from atomic import atomic_write_json

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
OUTPUT = BASE / "data" / "channels.json"
SOURCE_HEALTH_FILE = BASE / "data" / "source_health.json"
TIMEOUT = 30


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):
    atomic_write_json(path, data)


def read_source(source):
    url = str(source.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("La fuente debe usar una URL HTTP/HTTPS.")
    request = Request(
        url,
        headers={"User-Agent": "IPTV-CHILE-GENERADOR/3.0"},
    )
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_m3u(text, source_name, priority):
    channels = []
    current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current = {
                "name": line.split(",", 1)[-1].strip(),
                "group": "",
                "logo": "",
                "url": "",
                "source": source_name,
                "priority": priority,
            }

            for key in ("group-title", "tvg-logo"):
                marker = f'{key}="'
                if marker in line:
                    value = line.split(marker, 1)[1].split('"', 1)[0]
                    current["group" if key == "group-title" else "logo"] = value
            continue

        if current and not line.startswith("#") and line.startswith(("http://", "https://")):
            current["url"] = line
            channels.append(current)
            current = None

    return channels


def channel_id(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def main():
    config = load_json(CONFIG, {"sources": []})
    sources = config.get("sources", [])
    if not sources:
        raise SystemExit("No hay fuentes independientes configuradas.")

    all_entries = []
    successful_sources = 0
    health = load_json(SOURCE_HEALTH_FILE, {})
    from datetime import datetime, timezone
    checked_at = datetime.now(timezone.utc).isoformat()

    for source in sources:
        name = str(source.get("name") or "FUENTE").strip()
        source_url = str(source.get("url") or "").strip()
        priority = int(source.get("priority") or 0)
        state = health.setdefault(
            name,
            {
                "url": source_url,
                "priority": priority,
                "checks": 0,
                "successes": 0,
                "failures": 0,
                "consecutive_failures": 0,
                "last_success": None,
                "last_failure": None,
                "last_error": None,
                "last_entries": 0,
            },
        )
        state["url"] = source_url
        state["priority"] = priority
        state["checks"] += 1
        try:
            entries = parse_m3u(read_source(source), name, priority)
            if not entries:
                raise ValueError("La fuente respondió pero no contiene entradas M3U válidas.")
            print(f"[OK] {name}: {len(entries)} entradas")
            all_entries.extend(entries)
            successful_sources += 1
            state["successes"] += 1
            state["consecutive_failures"] = 0
            state["last_success"] = checked_at
            state["last_error"] = None
            state["last_entries"] = len(entries)
        except Exception as error:
            message = str(error)
            print(f"[ERROR] {name}: {message}")
            state["failures"] += 1
            state["consecutive_failures"] += 1
            state["last_failure"] = checked_at
            state["last_error"] = message

    if not successful_sources:
        raise SystemExit("Ninguna fuente independiente respondió correctamente.")

    grouped = {}

    # URL = identidad única. El nombre nunca crea duplicados.
    for entry in all_entries:
        url = str(entry.get("url") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not url or not name:
            continue

        item = grouped.setdefault(
            url,
            {
                "id": channel_id(url),
                "name": name,
                "group": str(entry.get("group") or "Chile").strip() or "Chile",
                "logo": str(entry.get("logo") or "").strip(),
                "sources": [],
                "aliases": [],
            },
        )

        if name not in item["aliases"]:
            item["aliases"].append(name)

        if not item["logo"] and entry.get("logo"):
            item["logo"] = str(entry["logo"]).strip()

        source_name = str(entry.get("source") or "").strip()
        source_priority = int(entry.get("priority") or 0)

        # La URL es la identidad global del canal. Por tanto, una URL
        # nunca puede aparecer dos veces dentro de sources[], aunque
        # distintas fuentes externas la publiquen con nombres distintos.
        existing = next(
            (x for x in item["sources"] if x["url"] == url),
            None,
        )

        if existing is None:
            item["sources"].append(
                {
                    "url": url,
                    "source": source_name,
                    "priority": source_priority,
                }
            )
        elif source_priority > int(existing.get("priority") or 0):
            # Conservamos como principal la fuente con mayor prioridad.
            existing["source"] = source_name
            existing["priority"] = source_priority

    channels = list(grouped.values())

    for url, item in grouped.items():
        item["aliases"] = [x for x in item["aliases"] if x != item["name"]]
        item["sources"].sort(
            key=lambda x: int(x.get("priority") or 0),
            reverse=True,
        )
        if not item["sources"]:
            item["sources"] = [{"url": url, "source": "", "priority": 0}]

    channels.sort(
        key=lambda x: (
            x["group"].lower(),
            x["name"].lower(),
            x["id"],
        )
    )

    save_json(OUTPUT, channels)
    save_json(SOURCE_HEALTH_FILE, health)

    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - COLLECTOR")
    print("=" * 60)
    print(f"Fuentes OK:        {successful_sources}/{len(sources)}")
    print(f"Salud de fuentes:  {SOURCE_HEALTH_FILE}")
    print(f"Entradas originales:{len(all_entries)}")
    print(f"URLs únicas:       {len(channels)}")
    print(f"Archivo:           {OUTPUT}")
    print("OK: generador independiente; ninguna lista local del repositorio es fuente.")


if __name__ == "__main__":
    main()

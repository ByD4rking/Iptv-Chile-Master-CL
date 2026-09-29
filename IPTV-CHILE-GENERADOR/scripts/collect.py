import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from atomic import atomic_write_json

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
CATALOG = BASE / "config" / "catalog.json"
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

    catalog = load_json(CATALOG, {"channels": []})
    catalog_channels = catalog.get("channels", [])
    if not catalog_channels:
        raise SystemExit("El catalogo propio esta vacio o no existe.")

    # El catalogo propio es la fuente de verdad de QUE canales pertenecen
    # a nuestra lista. Las fuentes externas solo pueden aportar endpoints
    # que ya esten declarados en el catalogo; nunca pueden insertar canales
    # nuevos automaticamente.
    discovered = {}
    for entry in all_entries:
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        discovered.setdefault(url, []).append(entry)

    channels = []
    for catalog_entry in catalog_channels:
        item = {
            "id": str(catalog_entry.get("id") or "").strip(),
            "name": str(catalog_entry.get("name") or "").strip(),
            "group": str(catalog_entry.get("group") or "Chile").strip() or "Chile",
            "logo": str(catalog_entry.get("logo") or "").strip(),
            "aliases": list(catalog_entry.get("aliases") or []),
            "sources": [],
        }
        if not item["id"] or not item["name"]:
            continue

        # Conservamos los endpoints declarados por nosotros aunque una fuente
        # externa este caida o deje de publicarlos. Asi el catalogo no se borra
        # por un fallo temporal de terceros.
        catalog_sources = catalog_entry.get("sources") or []
        for catalog_source in catalog_sources:
            url = str(catalog_source.get("url") or "").strip()
            if not url:
                continue

            candidates = discovered.get(url, [])
            if candidates:
                best = max(
                    candidates,
                    key=lambda x: int(x.get("priority") or 0),
                )
                source_name = str(best.get("source") or "EXTERNA").strip()
                priority = int(best.get("priority") or catalog_source.get("priority") or 0)
                if best.get("name") and best["name"] not in item["aliases"] and best["name"] != item["name"]:
                    item["aliases"].append(best["name"])
                if not item["logo"] and best.get("logo"):
                    item["logo"] = str(best["logo"]).strip()
            else:
                source_name = "CATALOGO"
                priority = int(catalog_source.get("priority") or 0)

            item["sources"].append(
                {
                    "url": url,
                    "source": source_name,
                    "priority": priority,
                }
            )

        # Dedupe defensivo por URL.
        unique_sources = {}
        for source in item["sources"]:
            unique_sources[source["url"]] = source
        item["sources"] = sorted(
            unique_sources.values(),
            key=lambda x: (-int(x.get("priority") or 0), x["url"]),
        )

        if item["sources"]:
            channels.append(item)

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

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.request import Request, urlopen

from atomic import atomic_write_json

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
CATALOG = BASE / "config" / "catalog.json"
OUTPUT = BASE / "data" / "channels.json"
SOURCE_HEALTH_FILE = BASE / "data" / "source_health.json"
ENDPOINT_HEALTH_FILE = BASE / "data" / "endpoint_health.json"
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


def normalize_label(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"\[[^]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"\b(?:4k|2160p|1440p|1080p|720p|576p|480p|360p|240p)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def candidate_keys(entry):
    values = [entry.get("name", "")]
    values.extend(entry.get("aliases") or [])
    return {normalize_label(value) for value in values if normalize_label(value)}


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
    catalog_ids_by_key = {}
    for catalog_entry in catalog_channels:
        catalog_id = str(catalog_entry.get("id") or "").strip()
        for key in candidate_keys(catalog_entry):
            catalog_ids_by_key.setdefault(key, set()).add(catalog_id)

    discovered_by_name = {}
    for entry in all_entries:
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        for key in candidate_keys(entry):
            discovered_by_name.setdefault(key, []).append(entry)

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

        # El catalogo controla la pertenencia de canales. Las fuentes solo
        # pueden aportar endpoints alternativos con coincidencia exacta del
        # nombre normalizado (incluyendo aliases), evitando inventar canales.
        candidates_by_url = {}

        def add_candidate(url, source_name, priority, match):
            url = str(url or "").strip()
            if not url:
                return
            candidate = {
                "url": url,
                "source": str(source_name or "EXTERNA").strip(),
                "priority": int(priority or 0),
                "match": match,
            }
            current = candidates_by_url.get(url)
            if current is None or candidate["priority"] > current["priority"]:
                candidates_by_url[url] = candidate

        for catalog_source in catalog_entry.get("sources") or []:
            add_candidate(
                catalog_source.get("url"),
                "CATALOGO",
                int(catalog_source.get("priority") or 0),
                "catalogo",
            )

        for key in candidate_keys(catalog_entry):
            if catalog_ids_by_key.get(key) != {item["id"]}:
                continue
            for discovered_entry in discovered_by_name.get(key, []):
                add_candidate(
                    discovered_entry.get("url"),
                    discovered_entry.get("source"),
                    int(discovered_entry.get("priority") or 0),
                    "nombre_exacto",
                )
                if discovered_entry.get("name") and discovered_entry["name"] not in item["aliases"] and discovered_entry["name"] != item["name"]:
                    item["aliases"].append(discovered_entry["name"])
                if not item["logo"] and discovered_entry.get("logo"):
                    item["logo"] = str(discovered_entry["logo"]).strip()

        item["sources"] = sorted(
            candidates_by_url.values(),
            key=lambda x: (-int(x.get("priority") or 0), x["url"]),
        )

        # Conservamos SIEMPRE el canal del catalogo, incluso si hoy no tiene
        # ningun endpoint candidato. El catalogo es la fuente de verdad de
        # pertenencia; la disponibilidad de endpoints es un estado operativo.
        channels.append(item)

    channels.sort(
        key=lambda x: (
            x["group"].lower(),
            x["name"].lower(),
            x["id"],
        )
    )

    claimed_urls = {}
    duplicate_assignments = 0
    for channel in channels:
        unique_sources = []
        for source in channel.get("sources", []):
            url = source["url"]
            owner = claimed_urls.get(url)
            if owner is not None and owner != channel["id"]:
                duplicate_assignments += 1
                continue
            claimed_urls[url] = channel["id"]
            unique_sources.append(source)
        channel["sources"] = unique_sources

    # No eliminamos canales sin candidatos: el catálogo sigue siendo la
    # fuente de verdad completa. Esos canales quedan en cuarentena operativa
    # hasta que alguna fuente aporte un endpoint verificable.

    if duplicate_assignments:
        print(
            f"AVISO: {duplicate_assignments} asociaciones duplicadas de endpoint "
            "fueron descartadas para mantener identidad URL global."
        )

    save_json(OUTPUT, channels)
    endpoint_health = load_json(ENDPOINT_HEALTH_FILE, {})
    active_urls = {source["url"] for channel in channels for source in channel.get("sources", [])}
    endpoint_health = {url: state for url, state in endpoint_health.items() if url in active_urls}
    for channel in channels:
        for source in channel.get("sources", []):
            state = endpoint_health.setdefault(source["url"], {
                "channel_id": channel["id"], "channel_name": channel["name"],
                "source": source["source"], "priority": source["priority"],
                "checks": 0, "successes": 0, "failures": 0,
                "consecutive_failures": 0, "last_success": None,
                "last_failure": None, "last_error": None,
            })
            state.update({
                "channel_id": channel["id"], "channel_name": channel["name"],
                "source": source["source"], "priority": source["priority"],
            })
    save_json(SOURCE_HEALTH_FILE, health)
    save_json(ENDPOINT_HEALTH_FILE, endpoint_health)

    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - COLLECTOR")
    print("=" * 60)
    print(f"Fuentes OK:        {successful_sources}/{len(sources)}")
    print(f"Salud de fuentes:  {SOURCE_HEALTH_FILE}")
    print(f"Entradas originales:{len(all_entries)}")
    print(f"Canales catalogados: {len(channels)}")
    print(f"Endpoints candidatos:{len(claimed_urls)}")
    print(f"Archivo:           {OUTPUT}")
    print("OK: generador independiente; ninguna lista local del repositorio es fuente.")


if __name__ == "__main__":
    main()

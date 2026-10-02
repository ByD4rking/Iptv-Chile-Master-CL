import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atomic import atomic_write_json

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
CATALOG = BASE / "config" / "catalog.json"
OUTPUT = BASE / "data" / "channels.json"
SOURCE_HEALTH_FILE = BASE / "data" / "source_health.json"
ENDPOINT_HEALTH_FILE = BASE / "data" / "endpoint_health.json"
TIMEOUT = 30
RETRIES = 3
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
SOURCE_QUARANTINE_AFTER = 6
SOURCE_QUARANTINE_HOURS = 24


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
    last_error = None
    for attempt in range(RETRIES):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "IPTV-CHILE-GENERADOR/COLLECT-5.0",
                    "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, text/plain, */*",
                },
            )
            with urlopen(request, timeout=TIMEOUT) as response:
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            last_error = f"HTTP {error.code}"
            if error.code not in RETRYABLE_HTTP:
                raise
        except Exception as error:
            last_error = str(error)
        if attempt < RETRIES - 1:
            import time
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])
    raise RuntimeError(f"Fuente no disponible tras {RETRIES} intentos: {last_error}")


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


def discover_new_candidates(all_entries, catalog_channels):
    discovery_cfg = load_json(BASE / "config" / "discovery.json", {})
    profiles = discovery_cfg.get("profiles", {})
    max_per_profile = int(discovery_cfg.get("max_candidates_per_profile", 250))

    catalog_names = set()
    catalog_urls = set()
    for item in catalog_channels:
        for key in candidate_keys(item):
            catalog_names.add(key)
        for source in item.get("sources") or []:
            url = str(source.get("url") or "").strip()
            if url:
                catalog_urls.add(url)

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "discovery_only",
        "published_automatically": False,
        "profiles": {},
    }

    for profile, terms in profiles.items():
        found = {}
        for entry in all_entries:
            url = str(entry.get("url") or "").strip()
            if not url or url in catalog_urls:
                continue

            haystack = normalize_label(
                f"{entry.get('name', '')} {entry.get('group', '')}"
            )
            matches = [term for term in terms if normalize_label(term) in haystack]
            if not matches:
                continue

            found.setdefault(url, {
                "name": str(entry.get("name") or "").strip(),
                "group": str(entry.get("group") or "").strip(),
                "logo": str(entry.get("logo") or "").strip(),
                "url": url,
                "source": str(entry.get("source") or "").strip(),
                "matched_terms": sorted(set(matches)),
                "requires_validation": True,
                "safe_to_publish_automatically": False,
            })

            if len(found) >= max_per_profile:
                break

        result["profiles"][profile] = list(found.values())

    save_json(BASE / "data" / "discovered_channels.json", result)
    total = sum(len(items) for items in result["profiles"].values())
    print(f"Descubrimiento: {total} candidatos nuevos guardados en data/discovered_channels.json")
    print("IMPORTANTE: descubrimiento separado; no modifica catalog.json ni publica candidatos.")


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

    now_utc = datetime.now(timezone.utc)
    quarantined_source_count = 0
    for source in sources:
        source_name = str(source.get("name") or "FUENTE").strip()
        until = str(health.get(source_name, {}).get("quarantine_until") or "").strip()
        if not until:
            continue
        try:
            if datetime.fromisoformat(until.replace("Z", "+00:00")) > now_utc:
                quarantined_source_count += 1
        except ValueError:
            pass
    force_source_probe = quarantined_source_count == len(sources)
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
        quarantine_until = str(state.get("quarantine_until") or "").strip()
        quarantined = False
        if quarantine_until:
            try:
                quarantined = datetime.fromisoformat(quarantine_until.replace("Z", "+00:00")) > datetime.now(timezone.utc)
            except ValueError:
                quarantined = False
        if quarantined and not force_source_probe:
            state["last_skip"] = checked_at
            state["last_skip_reason"] = "cuarentena_por_fallos_persistentes"
            print(f"[QUARANTINE] {name}: se omite hasta {quarantine_until}")
            continue
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
            state["quarantine_until"] = None
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
            if state["consecutive_failures"] >= SOURCE_QUARANTINE_AFTER:
                from datetime import timedelta
                state["quarantine_until"] = (datetime.now(timezone.utc) + timedelta(hours=SOURCE_QUARANTINE_HOURS)).isoformat()
                print(f"[QUARANTINE] {name}: {state['consecutive_failures']} fallos consecutivos; pausa hasta {state['quarantine_until']}")

    if not successful_sources:
        raise SystemExit("Ninguna fuente independiente respondió correctamente (las fuentes en cuarentena no cuentan como fuente disponible).")

    catalog = load_json(CATALOG, {"channels": []})
    catalog_channels = catalog.get("channels", [])
    if not catalog_channels:
        raise SystemExit("El catalogo propio esta vacio o no existe.")

    discover_new_candidates(all_entries, catalog_channels)

    # El catalogo propio es la fuente de verdad de QUE canales pertenecen
    # a nuestra lista. Las fuentes externas solo pueden aportar endpoints
    # que ya esten declarados en el catalogo; nunca pueden insertar canales
    # nuevos automaticamente.
    catalog_ids_by_key = {}
    catalog_keys_by_id = {}
    catalog_url_keys = {}
    for catalog_entry in catalog_channels:
        catalog_id = str(catalog_entry.get("id") or "").strip()
        channel_key = str(catalog_entry.get("channel_key") or "").strip()
        if not channel_key:
            raise SystemExit(f"El catalogo contiene un canal sin channel_key: {catalog_id}")
        catalog_keys_by_id[catalog_id] = channel_key
        for key in candidate_keys(catalog_entry):
            catalog_ids_by_key.setdefault(key, set()).add(catalog_id)
        for catalog_source in catalog_entry.get("sources") or []:
            source_url = str(catalog_source.get("url") or "").strip()
            if source_url:
                catalog_url_keys[source_url] = channel_key

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
            "channel_key": str(catalog_entry.get("channel_key") or "").strip(),
            "sources": [],
        }
        if not item["id"] or not item["name"]:
            continue

        # El catalogo controla la pertenencia de canales. Las fuentes solo
        # pueden aportar endpoints alternativos con coincidencia exacta del
        # nombre normalizado (incluyendo aliases), evitando inventar canales.
        candidates_by_url = {}

        def add_candidate(url, source_name, priority, match, channel_key=None):
            url = str(url or "").strip()
            if not url:
                return
            candidate = {
                "url": url,
                "source": str(source_name or "EXTERNA").strip(),
                "priority": int(priority or 0),
                "match": match,
            }
            if channel_key:
                candidate["channel_key"] = channel_key
            current = candidates_by_url.get(url)
            if current is None or candidate["priority"] > current["priority"]:
                candidates_by_url[url] = candidate

        for catalog_source in catalog_entry.get("sources") or []:
            add_candidate(
                catalog_source.get("url"),
                "CATALOGO",
                int(catalog_source.get("priority") or 0),
                "catalogo",
                item["channel_key"],
            )

        # Identidad primaria: URL ya declarada en el catalogo -> channel_key.
        # Nombre/alias es solo fallback cuando la clave identifica un unico canal.
        for discovered_entry in all_entries:
            discovered_url = str(discovered_entry.get("url") or "").strip()
            if not discovered_url:
                continue
            if catalog_url_keys.get(discovered_url) != item["channel_key"]:
                continue
            add_candidate(
                discovered_url,
                discovered_entry.get("source"),
                int(discovered_entry.get("priority") or 0),
                "channel_key_por_url",
                item["channel_key"],
            )

        for key in candidate_keys(catalog_entry):
            if catalog_ids_by_key.get(key) != {item["id"]}:
                continue
            for discovered_entry in discovered_by_name.get(key, []):
                discovered_url = str(discovered_entry.get("url") or "").strip()
                if catalog_url_keys.get(discovered_url) not in (None, item["channel_key"]):
                    continue
                match = "channel_key_por_url" if catalog_url_keys.get(discovered_url) == item["channel_key"] else "nombre_exacto_fallback"
                add_candidate(
                    discovered_url,
                    discovered_entry.get("source"),
                    int(discovered_entry.get("priority") or 0),
                    match,
                    item["channel_key"],
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

    # Una URL es identidad global de endpoint. Si una misma URL aparece
    # asociada a dos canales distintos, no elegimos arbitrariamente al primero:
    # la retiramos de todos los canales y dejamos que otra fuente la resuelva.
    url_owners = {}
    for channel in channels:
        for source in channel.get("sources", []):
            url_owners.setdefault(source["url"], set()).add(channel["id"])

    ambiguous_urls = {
        url for url, owners in url_owners.items()
        if len(owners) > 1
    }
    duplicate_assignments = sum(
        len(url_owners[url]) for url in ambiguous_urls
    )

    if ambiguous_urls:
        for channel in channels:
            channel["sources"] = [
                source
                for source in channel.get("sources", [])
                if source["url"] not in ambiguous_urls
            ]
        print(
            f"AVISO: {duplicate_assignments} asociaciones ambiguas fueron "
            "retiradas de forma determinista para preservar ownership único."
        )

    claimed_urls = {
        source["url"]: channel["id"]
        for channel in channels
        for source in channel.get("sources", [])
    }

    # No eliminamos canales sin candidatos: el catálogo sigue siendo la
    # fuente de verdad completa. Esos canales quedan en cuarentena operativa
    # hasta que alguna fuente aporte un endpoint verificable.

    save_json(OUTPUT, channels)
    endpoint_health = load_json(ENDPOINT_HEALTH_FILE, {})
    active_urls = {source["url"] for channel in channels for source in channel.get("sources", [])}
    endpoint_health = {url: state for url, state in endpoint_health.items() if url in active_urls}
    for channel in channels:
        for source in channel.get("sources", []):
            state = endpoint_health.setdefault(source["url"], {
                "channel_id": channel["id"], "channel_name": channel["name"],
                "channel_key": channel["channel_key"],
                "source": source["source"], "priority": source["priority"],
                "checks": 0, "successes": 0, "failures": 0,
                "consecutive_failures": 0, "last_success": None,
                "last_failure": None, "last_error": None,
            })
            existing_channel_id = str(state.get("channel_id") or "").strip()
            existing_channel_key = str(state.get("channel_key") or "").strip()
            if existing_channel_id and existing_channel_id != channel["id"]:
                raise SystemExit(
                    f"INCONSISTENCIA: endpoint {source['url']} cambió de canal "
                    f"({existing_channel_id} -> {channel['id']})."
                )
            if existing_channel_key and existing_channel_key != channel["channel_key"]:
                raise SystemExit(
                    f"INCONSISTENCIA: endpoint {source['url']} cambió de channel_key "
                    f"({existing_channel_key} -> {channel['channel_key']})."
                )
            state.update({
                "channel_id": channel["id"], "channel_name": channel["name"],
                "channel_key": channel["channel_key"],
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

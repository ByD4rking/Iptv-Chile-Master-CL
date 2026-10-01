import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from atomic import atomic_write_json
from teleon_classifier import classify

BASE = Path(__file__).resolve().parent.parent
M3U = BASE / "IPTV-CHILE-GENERADOR.m3u"
TELEON = BASE / "data" / "teleon_discovery.json"
OUTPUT = BASE / "data" / "m3u_inventory.json"
CANDIDATES = BASE / "data" / "m3u_new_candidates.json"
CANDIDATE_M3U = BASE / "data" / "m3u_new_candidates.m3u"


def clean_url(url):
    url = str(url or "").strip()
    if not url or url.startswith("#"):
        return ""
    try:
        p = urlsplit(url)
        if p.scheme not in {"http", "https"} or not p.netloc:
            return ""
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, p.query, ""))
    except ValueError:
        return ""


def parse_extinf(line):
    attrs = {}
    match = re.match(r"#EXTINF:[^,]*?(?:,|$)(.*)$", line)
    display = match.group(1).strip() if match else ""
    for key, value in re.findall(r'''([\w-]+)="([^"]*)"''', line):
        attrs[key.lower()] = value
    if not display:
        display = attrs.get("tvg-name", "")
    return attrs, display


def parse_m3u(path):
    entries = []
    if not path.exists():
        return entries
    pending = None
    options = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            pending = parse_extinf(line)
            options = {}
            continue
        if line.startswith("#EXTVLCOPT:"):
            value = line[len("#EXTVLCOPT:"):]
            if "=" in value:
                k, v = value.split("=", 1)
                options[k.strip()] = v.strip()
            continue
        if line.startswith("#"):
            continue
        url = clean_url(line)
        if not url or pending is None:
            continue
        attrs, display = pending
        groups = [x.strip() for x in attrs.get("group-title", "").split(";") if x.strip()]
        entries.append({
            "name": display,
            "tvg_name": attrs.get("tvg-name", display),
            "tvg_id": attrs.get("tvg-id"),
            "logo": attrs.get("tvg-logo"),
            "groups": groups,
            "url": url,
            "headers": {
                key: value for key, value in options.items()
                if key.lower() in {"http-referrer", "http-user-agent", "http-reconnect"}
            },
        })
        pending = None
        options = {}
    return entries


def key_name(value):
    value = str(value or "").lower()
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    value = re.sub(r"\b(1080p|720p|576p|480p|360p|4k|uhd|hd|fhd)\b", " ", value)
    value = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", value)
    return " ".join(value.split())


def teleon_urls(data):
    urls = set()
    for items in data.get("profiles", {}).values():
        for item in items:
            for url in item.get("stream_urls") or []:
                u = clean_url(url)
                if u:
                    urls.add(u)
    return urls


def teleon_names(data):
    names = set()
    for items in data.get("profiles", {}).values():
        for item in items:
            c = item.get("classification") or {}
            terms = c.get("matched_terms") or []
            if item.get("channel_path"):
                names.add(key_name(item["channel_path"].rsplit("/", 1)[-1]))
            names.update(key_name(x) for x in terms)
    return {x for x in names if x}


def main():
    entries = parse_m3u(M3U)
    seen_urls = set()
    duplicates = []
    unique = []
    for item in entries:
        if item["url"] in seen_urls:
            duplicates.append(item)
            continue
        seen_urls.add(item["url"])
        unique.append(item)

    discovery = json.loads(TELEON.read_text(encoding="utf-8-sig")) if TELEON.exists() else {}
    known_urls = teleon_urls(discovery)
    known_names = teleon_names(discovery)

    new_candidates = []
    for item in unique:
        name_key = key_name(item["name"])
        classification = classify(
            name=item["name"],
            group=" ".join(item["groups"]),
            slug=name_key,
            extra=" ".join(item["tvg_name"] or "" for _ in [0]),
        )
        is_new_url = item["url"] not in known_urls
        is_new_name = bool(name_key) and name_key not in known_names
        if is_new_url:
            new_candidates.append({
                **item,
                "origin": "IPTV-CHILE-GENERADOR.m3u",
                "classification": classification,
                "requires_validation": True,
                "safe_to_publish_automatically": False,
            })

    new_candidates.sort(key=lambda x: (-x["classification"].get("confidence", 0), x["name"].lower()))

    output = {
        "schema_version": 1,
        "mode": "secondary_m3u_inventory_only",
        "source": str(M3U.relative_to(BASE)),
        "source_sha256": None,
        "published_automatically": False,
        "reingestion_protection": {
            "source_is_output_m3u": True,
            "candidates_are_not_reinserted": True,
            "comparison_against": str(TELEON.relative_to(BASE)),
        },
        "metrics": {
            "entries_parsed": len(entries),
            "unique_urls": len(unique),
            "duplicate_urls": len(duplicates),
            "known_to_teleon": sum(1 for x in unique if x["url"] in known_urls),
            "new_urls_vs_teleon": sum(1 for x in unique if x["url"] not in known_urls),
            "new_url_candidates": len(new_candidates),
        },
        "duplicates": duplicates,
        "entries": unique,
    }
    atomic_write_json(OUTPUT, output)
    atomic_write_json(CANDIDATES, {
        "schema_version": 1,
        "mode": "candidate_inventory_only",
        "source": str(M3U.relative_to(BASE)),
        "published_automatically": False,
        "count": len(new_candidates),
        "candidates": new_candidates,
    })

    lines = ["#EXTM3U", "# IPTV-CHILE-GENERADOR | candidatos secundarios M3U | NO PUBLICAR AUTOMATICAMENTE"]
    for item in new_candidates:
        groups = ";".join(item.get("groups") or ["M3U Discovery"])
        name = item.get("name") or item.get("tvg_name") or "Canal sin nombre"
        tvg_name = item.get("tvg_name") or name
        logo = item.get("logo") or ""
        safe_name = tvg_name.replace('"', "'")
        safe_groups = groups.replace('"', "'")
        extinf = f'#EXTINF:-1 tvg-name="{safe_name}"'
        if logo:
            extinf += f' tvg-logo="{logo}"'
        extinf += f' group-title="{safe_groups}",{name}'
        lines.append(extinf)
        for key, value in (item.get("headers") or {}).items():
            if key.lower() == "http-referrer":
                lines.append(f"#EXTVLCOPT:http-referrer={value}")
            elif key.lower() == "http-user-agent":
                lines.append(f"#EXTVLCOPT:http-user-agent={value}")
        lines.append(item["url"])
    from atomic import atomic_write_text
    atomic_write_text(CANDIDATE_M3U, "\n".join(lines) + "\n")

    print(f"M3U inventario: {len(entries)} entradas, {len(unique)} URLs únicas.")
    print(f"Duplicadas: {len(duplicates)}.")
    print(f"URLs no vistas por Teleon: {output['metrics']['new_urls_vs_teleon']}.")
    print(f"Candidatos URL nuevos frente a Teleon: {len(new_candidates)}.")
    print(f"Inventario: {OUTPUT}")
    print(f"Candidatos JSON: {CANDIDATES}")
    print(f"Candidatos M3U: {CANDIDATE_M3U}")


if __name__ == "__main__":
    main()

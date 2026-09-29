import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
OUTPUT = BASE / "data" / "channels.json"
TIMEOUT = 20

def load_json(path, default):
    if not path.exists(): return default
    with path.open("r", encoding="utf-8-sig") as f: return json.load(f)

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def read_source(source):
    local_path = str(source.get("path") or "").strip()
    if local_path:
        path = Path(local_path).expanduser()
        if not path.exists(): raise FileNotFoundError(f"No existe: {path}")
        if not path.is_file(): raise IsADirectoryError(f"No es archivo: {path}")
        return path.read_text(encoding="utf-8-sig", errors="replace")
    url = str(source.get("url") or "").strip()
    if url:
        request = Request(url, headers={"User-Agent": "IPTV-CHILE-GENERADOR/3.0"})
        with urlopen(request, timeout=TIMEOUT) as response: return response.read().decode("utf-8", errors="replace")
    raise ValueError("La fuente no tiene 'path' ni 'url'")

def parse_m3u(text, source_name):
    channels, current = [], None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line: continue
        if line.startswith("#EXTINF:"):
            current = {"name": line.split(",", 1)[-1].strip(), "group": "", "logo": "", "url": "", "source": source_name}
            for key in ("group-title", "tvg-logo"):
                marker = f'{key}="'
                if marker in line:
                    value = line.split(marker, 1)[1].split('"', 1)[0]
                    current["group" if key == "group-title" else "logo"] = value
            continue
        if current and not line.startswith("#") and line.startswith(("http://", "https://")):
            current["url"] = line; channels.append(current); current = None
    return channels

def channel_id(url): return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]

def main():
    config = load_json(CONFIG, {"sources": []})
    sources = config.get("sources", [])
    if not sources: raise SystemExit("No hay fuentes configuradas.")
    all_entries = []
    for source in sources:
        name = str(source.get("name") or "FUENTE").strip()
        try:
            all_entries.extend(parse_m3u(read_source(source), name))
        except Exception as error:
            print(f"[{name}] ERROR: {error}")
    # URL = identidad única. El nombre no se usa para deduplicar.
    grouped = {}
    for entry in all_entries:
        url = str(entry.get("url") or "").strip(); name = str(entry.get("name") or "").strip()
        if not url or not name: continue
        item = grouped.setdefault(url, {"id": channel_id(url), "name": name, "group": str(entry.get("group") or "").strip(), "logo": str(entry.get("logo") or "").strip(), "sources": [], "aliases": []})
        if name not in item["aliases"]: item["aliases"].append(name)
        if not item["group"] and entry.get("group"): item["group"] = str(entry["group"]).strip()
        if not item["logo"] and entry.get("logo"): item["logo"] = str(entry["logo"]).strip()
        source_name = str(entry.get("source") or "").strip()
        if source_name and source_name not in {x.get("source") for x in item["sources"]}: item["sources"].append({"url": url, "source": source_name})
    channels = list(grouped.values())
    for url, item in grouped.items():
        item["aliases"] = [x for x in item["aliases"] if x != item["name"]]
        if not item["sources"]: item["sources"] = [{"url": url, "source": ""}]
    channels.sort(key=lambda x: (x["group"].lower(), x["name"].lower(), x["id"]))
    save_json(OUTPUT, channels)
    print(f"Entradas: {len(all_entries)} | URLs únicas: {len(channels)}")

if __name__ == "__main__": main()
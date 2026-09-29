import json
from pathlib import Path

from atomic import atomic_write_json
BASE = Path(__file__).resolve().parent.parent
FILE = BASE / "data" / "channels.json"

def fix_text(value):
    if not isinstance(value, str): return value
    if any(x in value for x in ("Ã", "Â", "â€")):
        try: return value.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError): return value
    return value

def main():
    if not FILE.exists(): raise SystemExit(f"No existe: {FILE}")
    with FILE.open("r", encoding="utf-8-sig") as f: data = json.load(f)
    for channel in data:
        for key in ("name", "group", "logo"):
            if key in channel: channel[key] = fix_text(channel[key])
        for source in channel.get("sources", []):
            if "source" in source: source["source"] = fix_text(source["source"])
        channel["aliases"] = [fix_text(x) for x in channel.get("aliases", [])]
    atomic_write_json(FILE, data)
    print(f"OK: codificación corregida atómicamente en {FILE}; URLs no modificadas.")

if __name__ == "__main__": main()
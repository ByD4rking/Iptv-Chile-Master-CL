import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
CHANNELS = BASE / "data" / "channels.json"
OUTPUT = BASE / "IPTV-CHILE-GENERADOR.m3u"

def load(path):
    with path.open("r", encoding="utf-8-sig") as f: return json.load(f)

def main():
    config = load(CONFIG)
    sources = config.get("sources", [])
    assert sources, "No hay fuentes configuradas."
    assert all(str(x.get("url", "")).startswith(("http://", "https://")) for x in sources), "Existe una fuente no HTTP/HTTPS."
    channels = load(CHANNELS)
    urls = []
    ids = []
    for channel in channels:
        channel_id = str(channel.get("id") or "").strip()
        assert channel_id, "Canal sin ID."
        assert channel.get("name"), "Canal sin nombre."
        ids.append(channel_id)

        channel_urls = set()
        for source in channel.get("sources", []):
            url = str(source.get("url") or "").strip()
            assert url.startswith(("http://", "https://")), f"URL inválida: {url}"
            assert url not in channel_urls, f"Canal {channel_id} repite la URL: {url}"
            channel_urls.add(url)
            urls.append(url)

    assert len(ids) == len(set(ids)), "channels.json contiene IDs de canal duplicados."
    assert len(urls) == len(set(urls)), "channels.json contiene una URL duplicada."
    assert OUTPUT.exists() and OUTPUT.stat().st_size > 0, "No existe una M3U generada."
    text = OUTPUT.read_text(encoding="utf-8-sig")
    assert text.startswith("#EXTM3U"), "La salida no comienza con #EXTM3U."
    output_urls = [line.strip() for line in text.splitlines() if line.startswith(("http://", "https://"))]
    assert output_urls, "La M3U no contiene URLs."
    assert len(output_urls) == len(set(output_urls)), "La M3U contiene URLs duplicadas."
    assert set(output_urls) <= set(urls), "La M3U contiene una URL ajena a las fuentes independientes."
    extinf = len(re.findall(r"^#EXTINF:", text, re.MULTILINE))
    assert extinf == len(output_urls), f"EXTINF ({extinf}) != URLs ({len(output_urls)})."
    print(f"SELFTEST OK: {len(channels)} canales, {len(output_urls)} URLs finales.")

if __name__ == "__main__": main()
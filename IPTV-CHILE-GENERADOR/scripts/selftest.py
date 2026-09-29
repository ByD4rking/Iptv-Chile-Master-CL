import json
import re
from pathlib import Path

from atomic import file_sha256

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "sources.json"
CATALOG = BASE / "config" / "catalog.json"
CHANNELS = BASE / "data" / "channels.json"
OUTPUT = BASE / "IPTV-CHILE-GENERADOR.m3u"
QUALITY = BASE / "data" / "quality.json"
STATUS = BASE / "data" / "status.json"
SOURCE_HEALTH = BASE / "data" / "source_health.json"
ENDPOINT_HEALTH = BASE / "data" / "endpoint_health.json"
MANIFEST = BASE / "data" / "pipeline_manifest.json"


def load(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    config = load(CONFIG)
    sources = config.get("sources", [])
    assert sources, "No hay fuentes configuradas."
    assert all(
        str(x.get("url", "")).startswith(("http://", "https://"))
        for x in sources
    ), "Existe una fuente no HTTP/HTTPS."

    catalog = load(CATALOG)
    catalog_channels = catalog.get("channels", [])
    assert catalog_channels, "El catalogo propio esta vacio."
    catalog_ids = [str(x.get("id") or "").strip() for x in catalog_channels]
    assert len(catalog_ids) == len(set(catalog_ids)), "El catalogo propio contiene IDs duplicados."

    channels = load(CHANNELS)
    quality = load(QUALITY)
    status = load(STATUS)
    source_health = load(SOURCE_HEALTH)
    endpoint_health = load(ENDPOINT_HEALTH)
    manifest = load(MANIFEST)

    channels_sha = file_sha256(CHANNELS)
    status_sha = file_sha256(STATUS)
    quality_sha = file_sha256(QUALITY)
    m3u_sha = file_sha256(OUTPUT)

    assert status.get("channels_sha256") == channels_sha, (
        "status.json no corresponde al channels.json actual."
    )
    assert quality.get("channels_sha256") == channels_sha, (
        "quality.json no corresponde al channels.json actual."
    )

    assert manifest.get("channels_sha256") == channels_sha, "Manifest no corresponde a channels.json."
    assert manifest.get("status_sha256") == status_sha, "Manifest no corresponde a status.json."
    assert manifest.get("quality_sha256") == quality_sha, "Manifest no corresponde a quality.json."
    assert manifest.get("m3u_sha256") == m3u_sha, "Manifest no corresponde a la M3U."

    configured_names = {str(x.get("name") or "").strip() for x in sources}
    assert configured_names <= set(source_health), (
        "Falta historial de salud para una fuente configurada."
    )

    urls = []
    ids = []
    for channel in channels:
        channel_id = str(channel.get("id") or "").strip()
        assert channel_id, "Canal sin ID."
        assert channel.get("name"), "Canal sin nombre."
        ids.append(channel_id)

        channel_urls = set()
        assert channel.get("sources"), f"Canal {channel_id} sin endpoints candidatos."
        for source in channel.get("sources", []):
            url = str(source.get("url") or "").strip()
            assert url.startswith(("http://", "https://")), f"URL inválida: {url}"
            assert url not in channel_urls, f"Canal {channel_id} repite la URL: {url}"
            channel_urls.add(url)
            assert url in endpoint_health, f"Endpoint sin historial: {url}"
            urls.append(url)

    assert len(ids) == len(set(ids)), "channels.json contiene IDs de canal duplicados."
    assert set(ids) <= set(catalog_ids), "channels.json contiene un canal fuera del catalogo propio."
    assert set(catalog_ids) == set(ids), "channels.json perdio o agrego canales respecto del catalogo propio."
    assert len(urls) == len(set(urls)), "channels.json contiene una URL duplicada."
    assert quality.get("total_urls") == len(urls), "quality.json no cubre todos los endpoints candidatos."
    assert quality.get("endpoint_candidates") == len(urls), "quality.json no registra todos los candidatos."
    assert quality.get("channels_with_multiple_candidates", 0) == sum(1 for c in channels if len(c.get("sources", [])) > 1), "Métrica de candidatos múltiples inconsistente."
    assert OUTPUT.exists() and OUTPUT.stat().st_size > 0, "No existe una M3U generada."

    text = OUTPUT.read_text(encoding="utf-8-sig")
    assert text.startswith("#EXTM3U"), "La salida no comienza con #EXTM3U."
    assert f"# IPTV-CHILE-GENERADOR-CHANNELS-SHA256: {channels_sha}" in text, (
        "La M3U no pertenece al snapshot actual de channels.json."
    )

    output_urls = [
        line.strip()
        for line in text.splitlines()
        if line.startswith(("http://", "https://"))
    ]
    quality_by_url = {
        str(x.get("url") or "").strip(): x
        for x in quality.get("results", [])
    }

    for url in output_urls:
        item = quality_by_url.get(url)
        assert item, f"La M3U contiene una URL sin resultado de calidad: {url}"
        assert item.get("playback_checked") and item.get("playback_ok"), (
            f"La M3U contiene una URL sin reproducción verificada: {url}"
        )

    assert output_urls, "La M3U no contiene URLs."
    assert len(output_urls) == len(set(output_urls)), "La M3U contiene URLs duplicadas."
    channel_urls = set(urls)
    assert set(output_urls) <= channel_urls, (
        "La M3U contiene una URL que no pertenece a los endpoints candidatos."
    )
    extinf = len(re.findall(r"^#EXTINF:", text, re.MULTILINE))
    assert extinf == len(output_urls), f"EXTINF ({extinf}) != URLs ({len(output_urls)})."

    temp_files = list((BASE / "data").glob(".*.tmp"))
    temp_files += list(BASE.glob(".*.tmp"))
    assert not temp_files, f"Quedaron temporales atómicos: {temp_files}"

    print(
        f"SELFTEST OK: {len(channels)} canales, {len(urls)} candidatos, {len(output_urls)} URLs finales; "
        "pipeline completo con snapshots y manifest consistente."
    )


if __name__ == "__main__":
    main()

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
DISCOVERY = BASE / "data" / "discovered_channels.json"


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
    catalog_keys = [str(x.get("channel_key") or "").strip() for x in catalog_channels]
    assert all(catalog_ids), "El catalogo contiene un canal sin ID."
    assert all(catalog_keys), "El catalogo contiene un canal sin channel_key."
    assert len(catalog_ids) == len(set(catalog_ids)), "El catalogo propio contiene IDs duplicados."
    assert len(catalog_keys) == len(set(catalog_keys)), "El catalogo propio contiene channel_key duplicados."

    catalog_urls = []
    for catalog_channel in catalog_channels:
        for source in catalog_channel.get("sources") or []:
            url = str(source.get("url") or "").strip()
            assert url.startswith(("http://", "https://")), (
                f"Catalogo: endpoint no HTTP/HTTPS: {url}"
            )
            catalog_urls.append(url)
    assert len(catalog_urls) == len(set(catalog_urls)), (
        "El catalogo propio contiene endpoints duplicados."
    )

    discovery = load(DISCOVERY)
    assert discovery.get("mode") == "discovery_only", "El descubrimiento no está en modo seguro."
    assert discovery.get("published_automatically") is False, "El descubrimiento no puede publicar automaticamente."
    assert isinstance(discovery.get("profiles"), dict), "Descubrimiento sin perfiles."
    for profile, items in discovery.get("profiles", {}).items():
        assert isinstance(items, list), f"Perfil de descubrimiento inválido: {profile}"
        seen_discovery_urls = set()
        for item in items:
            url = str(item.get("url") or "").strip()
            assert url.startswith(("http://", "https://")), f"Descubrimiento: URL inválida: {url}"
            assert url not in seen_discovery_urls, f"Descubrimiento: URL duplicada: {url}"
            seen_discovery_urls.add(url)
            assert item.get("safe_to_publish_automatically") is False, "Candidato marcado para publicación automática."
            assert item.get("requires_validation") is True, "Candidato sin validación obligatoria."

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
    for source in sources:
        name = str(source.get("name") or "").strip()
        state = source_health[name]
        assert str(state.get("url") or "").strip() == str(source.get("url") or "").strip(), (
            f"Health de fuente {name} apunta a otra URL."
        )
        assert int(state.get("checks") or 0) >= 0
        assert int(state.get("successes") or 0) >= 0
        assert int(state.get("failures") or 0) >= 0
        assert int(state.get("successes") or 0) + int(state.get("failures") or 0) == int(
            state.get("checks") or 0
        ), f"Health inconsistente para la fuente {name}."

    urls = []
    ids = []
    candidate_pairs = set()

    for channel in channels:
        channel_id = str(channel.get("id") or "").strip()
        assert channel_id, "Canal sin ID."
        assert channel.get("name"), "Canal sin nombre."
        channel_key = str(channel.get("channel_key") or "").strip()
        assert channel_key, f"Canal {channel_id} sin channel_key."
        assert channel_key in set(catalog_keys), f"Canal {channel_id} usa un channel_key fuera del catalogo."
        catalog_channel = next(x for x in catalog_channels if str(x.get("id") or "").strip() == channel_id)
        assert channel_key == str(catalog_channel.get("channel_key") or "").strip(), (
            f"Canal {channel_id} tiene channel_key distinto al catalogo."
        )
        ids.append(channel_id)

        channel_urls = set()
        for source in channel.get("sources", []):
            url = str(source.get("url") or "").strip()
            assert url.startswith(("http://", "https://")), f"URL inválida: {url}"
            assert url not in channel_urls, f"Canal {channel_id} repite la URL: {url}"
            channel_urls.add(url)
            candidate_pairs.add((channel_id, url))

            assert url in endpoint_health, f"Endpoint sin historial: {url}"
            health = endpoint_health[url]
            assert str(health.get("channel_id") or "") == channel_id, (
                f"Endpoint {url} tiene health asociado al canal equivocado."
            )
            assert str(health.get("channel_key") or "") == channel_key, (
                f"Endpoint {url} tiene health asociado al channel_key equivocado."
            )

            checks = int(health.get("checks") or 0)
            successes = int(health.get("successes") or 0)
            failures = int(health.get("failures") or 0)
            assert checks >= 0 and successes >= 0 and failures >= 0
            assert successes + failures == checks, (
                f"Health inconsistente para {url}: successes + failures != checks."
            )
            quarantine_until = health.get("quarantine_until")
            if quarantine_until:
                assert isinstance(quarantine_until, str), f"quarantine_until inválido para {url}."
                from datetime import datetime
                datetime.fromisoformat(quarantine_until.replace("Z", "+00:00"))
            urls.append(url)

    assert len(ids) == len(set(ids)), "channels.json contiene IDs de canal duplicados."
    assert set(ids) <= set(catalog_ids), "channels.json contiene un canal fuera del catalogo propio."
    assert set(catalog_ids) == set(ids), "channels.json perdio o agrego canales respecto del catalogo propio."
    assert len(urls) == len(set(urls)), "channels.json contiene una URL duplicada."

    assert quality.get("total_urls") == len(urls), "quality.json no cubre todos los endpoints candidatos."
    assert quality.get("endpoint_candidates") == len(urls), "quality.json no registra todos los candidatos."
    assert quality.get("channels_with_multiple_candidates", 0) == sum(
        1 for c in channels if len(c.get("sources", [])) > 1
    ), "Métrica de candidatos múltiples inconsistente."

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
    assert set(output_urls) <= set(urls), (
        "La M3U contiene una URL que no pertenece a los endpoints candidatos."
    )

    expected_with_candidates = sum(1 for channel in channels if channel.get("sources"))
    expected_multiple = sum(1 for channel in channels if len(channel.get("sources", [])) > 1)
    expected_playback_ok = sum(
        1 for item in quality.get("results", []) if item.get("playback_ok")
    )
    assert manifest.get("channels") == len(channels), "Manifest: cantidad de canales inconsistente."
    assert manifest.get("generated_channels") == len(output_urls), (
        "Manifest: cantidad de canales generados inconsistente."
    )
    assert manifest.get("output_urls") == len(output_urls), (
        "Manifest: cantidad de URLs inconsistente."
    )
    assert manifest.get("channels_with_candidates") == expected_with_candidates, (
        "Manifest: channels_with_candidates inconsistente."
    )
    assert manifest.get("channels_with_multiple_candidates") == expected_multiple, (
        "Manifest: channels_with_multiple_candidates inconsistente."
    )
    assert manifest.get("quality_playback_ok") == expected_playback_ok, (
        "Manifest: quality_playback_ok inconsistente."
    )

    extinf = len(re.findall(r"^#EXTINF:", text, re.MULTILINE))
    assert extinf == len(output_urls), f"EXTINF ({extinf}) != URLs ({len(output_urls)})."

    # Estabilidad: cada canal publicado debe conservar las directivas de
    # reconexión/caché. No se altera la URL ni se permite fallback cruzado.
    reconnect_blocks = re.findall(
        r"^#EXTINF:[^\n]*\n((?:#[^\n]*\n)*)(https?://[^\n]+)",
        text,
        flags=re.MULTILINE,
    )
    assert len(reconnect_blocks) == len(output_urls), (
        "No se pudo asociar cada canal con su bloque de reproducción."
    )
    for metadata, _url in reconnect_blocks:
        assert "#EXTVLCOPT:http-reconnect=true" in metadata, (
            "Canal publicado sin http-reconnect=true."
        )
        assert "#EXTVLCOPT:network-caching=1500" in metadata, (
            "Canal publicado sin network-caching=1500."
        )

    # La salida debe seleccionar como máximo un endpoint por canal y cada
    # combinación canal/endpoint debe existir exactamente entre los candidatos.
    # Entre EXTINF y la URL puede haber directivas #EXTVLCOPT u otras
    # etiquetas M3U compatibles. El parser del selftest debe tratarlas como
    # metadatos del mismo bloque, no como una entrada sin URL.
    blocks = re.findall(
        r'^#EXTINF:[^\n]*\btvg-id="([^"]+)"[^\n]*(?:\n#[^\n]*)*\n(https?://[^\n]+)',
        text,
        flags=re.MULTILINE,
    )
    assert len(blocks) == len(output_urls), "Hay una entrada M3U sin tvg-id o sin URL asociada."

    selected_ids = [channel_id for channel_id, _ in blocks]
    assert len(selected_ids) == len(set(selected_ids)), (
        "La M3U contiene más de un endpoint seleccionado para el mismo canal."
    )
    assert set(selected_ids) <= set(catalog_ids), (
        "La M3U contiene un tvg-id que no pertenece al catálogo."
    )

    selected_pairs = {(channel_id, url) for channel_id, url in blocks}
    # Regresión crítica: la salida debe elegir exactamente el candidato que
    # generate.py considera óptimo para cada canal. Así evitamos que una
    # modificación futura del generador vuelva a preferir calidad nominal
    # sobre estabilidad real, o cambie el criterio entre etapas.
    status_by_url = {
        str(x.get("url") or "").strip(): x
        for x in status.get("results", [])
    }
    quality_by_url = {
        str(x.get("url") or "").strip(): x
        for x in quality.get("results", [])
    }

    def selection_key(quality_item, status_item, source):
        checks = int(quality_item.get("endpoint_checks") or 0)
        successes = int(quality_item.get("endpoint_successes") or 0)
        reliability = (successes + 1) / (checks + 2)
        return (
            -int(quality_item.get("endpoint_consecutive_failures") or 0),
            reliability,
            checks,
            int(quality_item.get("height") or 0),
            int(quality_item.get("bitrate") or 0),
            -int(status_item.get("response_time_ms") or 999999),
            int(source.get("priority") or 0),
        )

    channels_by_id = {str(c.get("id") or "").strip(): c for c in channels}
    for channel_id, selected_url in selected_pairs:
        channel = channels_by_id[channel_id]
        candidates = []
        for source in channel.get("sources", []):
            url = str(source.get("url") or "").strip()
            item = quality_by_url.get(url)
            if not item or item.get("quarantined"):
                continue
            if not item.get("playback_checked") or not item.get("playback_ok"):
                continue
            candidates.append((selection_key(item, status_by_url.get(url, {}), source), url))
        assert candidates, f"Canal {channel_id} publicado sin candidatos reproducibles."
        expected_url = max(candidates, key=lambda pair: pair[0])[1]
        assert selected_url == expected_url, (
            f"Canal {channel_id}: generate.py seleccionó {selected_url}, "
            f"pero el candidato óptimo auditado es {expected_url}."
        )

    assert selected_pairs <= candidate_pairs, (
        "La M3U seleccionó una combinación canal/endpoint que no existe en channels.json."
    )

    # Estabilidad de red: las etapas de adquisición/validación deben conservar
    # reintentos y backoff para no descartar un endpoint por un corte transitorio.
    for script_name in ("check.py", "collect.py", "quality.py"):
        script_text = (BASE / "scripts" / script_name).read_text(encoding="utf-8")
        assert re.search(r"^RETRIES\s*=\s*[2-9]\d*$", script_text, re.MULTILINE), (
            f"{script_name} perdió la política mínima de reintentos."
        )
        assert "RETRY_BACKOFF_SECONDS" in script_text, (
            f"{script_name} perdió el backoff de reintentos."
        )

    temp_files = list((BASE / "data").glob(".*.tmp"))
    temp_files += list(BASE.glob(".*.tmp"))
    assert not temp_files, f"Quedaron temporales atómicos: {temp_files}"

    print(
        f"SELFTEST OK: {len(channels)} canales, {len(urls)} candidatos, {len(output_urls)} URLs finales; "
        "pipeline completo con snapshots y manifest consistente."
    )


if __name__ == "__main__":
    main()

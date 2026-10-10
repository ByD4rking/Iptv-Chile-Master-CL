from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alimentar_principal import aplicar_reconexion_por_canal, validar_orden_canales


def channel_records(lines: list[str]) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXTINF:"):
            continue
        url = ""
        for item in lines[index + 1:]:
            if item.startswith("#EXTINF:"):
                break
            if item.strip().startswith(("http://", "https://")):
                url = item.strip()
                break
        records.append((line, url))
    return records


def main() -> None:
    source = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="canal-a" group-title="Chile",Canal A',
        "#EXTVLCOPT:network-caching=1500",
        "#EXTVLCOPT:network-caching=1500",
        "#EXTVLCOPT:http-reconnect=true",
        "https://example.test/canal-a.m3u8",
        '#EXTINF:-1 tvg-id="canal-b" group-title="Chile",Canal B',
        "https://example.test/canal-b.m3u8",
        '#EXTINF:-1 tvg-id="pluto-a" group-title="Pluto",Pluto A',
        "#EXTVLCOPT:network-caching=1500",
        "https://service-stitcher.clusters.pluto.tv/v2/channel/pluto-a/master.m3u8",
    ]

    before_order = ["id:canal-a", "id:canal-b", "id:pluto-a"]
    result, reconnects_added = aplicar_reconexion_por_canal(source)
    validar_orden_canales(before_order, result)
    assert channel_records(source) == channel_records(result), (
        "la reconexión alteró nombres, URLs o secuencia de canales"
    )
    text = "\n".join(result)

    assert text.count("#EXTVLCOPT:network-caching=5000") == 2
    assert "#EXTVLCOPT:network-caching=1500" not in text
    assert text.count("#EXTVLCOPT:http-reconnect=true") == 2
    assert reconnects_added == 1
    assert result[result.index("#EXTINF:-1 tvg-id=\"pluto-a\""):].count(
        "#EXTVLCOPT:network-caching=1500"
    ) == 1
    assert result[result.index("#EXTINF:-1 tvg-id=\"pluto-a\""):].count(
        "#EXTVLCOPT:network-caching=5000"
    ) == 0
    assert result.count("https://example.test/canal-a.m3u8") == 1
    assert result.count("https://example.test/canal-b.m3u8") == 1

    try:
        validar_orden_canales(before_order, [
            '#EXTINF:-1 tvg-id="canal-b",Canal B',
            "https://example.test/canal-b.m3u8",
            '#EXTINF:-1 tvg-id="canal-a",Canal A',
            "https://example.test/canal-a.m3u8",
            '#EXTINF:-1 tvg-id="pluto-a",Pluto A',
            "https://service-stitcher.clusters.pluto.tv/v2/channel/pluto-a/master.m3u8",
        ])
    except RuntimeError:
        pass
    else:
        raise AssertionError("el resguardo aceptó un cambio de orden")

    print("SELFTEST OK: buffer VLC 5000 ms, reconexión y orden/URLs preservados.")

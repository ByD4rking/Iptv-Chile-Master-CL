from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alimentar_principal import (
    aplicar_reconexion_por_canal,
    validar_orden_canales,
    integrar_alternativas_pluto,
    es_url_pluto,
    extraer_pluto_id,
    aplicar_ajustes_referencia,
    FUENTE_MAGMA,
    FUENTE_PLUTO_ALTERNATIVAS,
)


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
    assert channel_records(source) == channel_records(result)
    text = "\n".join(result)
    assert text.count("#EXTVLCOPT:network-caching=5000") == 2
    assert text.count("#EXTVLCOPT:network-caching=1500") == 1  # solo se conserva en el bloque Pluto
    assert text.count("#EXTVLCOPT:http-reconnect=true") == 2
    assert reconnects_added == 1
    assert text.count("https://example.test/canal-a.m3u8") == 1
    assert text.count("https://example.test/canal-b.m3u8") == 1

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

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, url, timeout):
            if url.endswith("PlutoTV.MX.m3u"):
                return FakeResponse("\n".join([
                    "#EXTM3U",
                    '#EXTINF:-1 tvg-id="",UFC (720p)',
                    "https://jmp2.uk/plu-67a52cd4ec91870008a62164.m3u8",
                    '#EXTINF:-1 tvg-id="",Comedy Central South Park',
                    "https://jmp2.uk/plu-609ae5cd48d3200007b0a98e.m3u8",
                    '#EXTINF:-1 tvg-id="",Pokémon',
                    "https://jmp2.uk/plu-6870072ca9d5c45c3e9466f1.m3u8",
                    '#EXTINF:-1 tvg-id="",Canal fuera de LATAM',
                    "https://jmp2.uk/plu-aaaaaaaaaaaaaaaaaaaaaaaa.m3u8",
                ]))
            return FakeResponse("\n".join([
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="67a52cd4ec91870008a62164" group-title="Deportes",UFC',
                "https://jmp2.uk/plu-67a52cd4ec91870008a62164.m3u8",
                '#EXTINF:-1 tvg-id="609ae5cd48d3200007b0a98e" group-title="South Park",Comedy Central South Park',
                "https://jmp2.uk/plu-609ae5cd48d3200007b0a98e.m3u8",
                '#EXTINF:-1 tvg-id="6870072ca9d5c45c3e9466f1" group-title="Anime",Pokémon',
                "https://jmp2.uk/plu-6870072ca9d5c45c3e9466f1.m3u8",
            ]))

    base = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="67a52cd4ec91870008a62164" group-title="Deportes",UFC',
        "https://example.test/ufc-base.m3u8",
        '#EXTINF:-1 tvg-id="609ae5cd48d3200007b0a98e" group-title="South Park",Comedy Central South Park',
        "https://example.test/southpark-base.m3u8",
        '#EXTINF:-1 tvg-id="6870072ca9d5c45c3e9466f1" group-title="Anime",Pokémon',
        "https://example.test/pokemon-base.m3u8",
    ]
    assert es_url_pluto("https://jmp2.uk/plu-67a52cd4ec91870008a62164.m3u8")
    assert extraer_pluto_id("https://jmp2.uk/plu-67a52cd4ec91870008a62164.m3u8") == "67a52cd4ec91870008a62164"

    resultado, auditoria = integrar_alternativas_pluto(base, FakeSession())
    resultado_texto = "\n".join(resultado)
    assert auditoria["fuente_ok"] is True
    assert auditoria["agregadas"] == 3, auditoria
    assert auditoria["sin_coincidencia"] == 0, auditoria
    assert "UFC (OPCIÓN 2)" in resultado_texto
    assert "Comedy Central South Park (OPCIÓN 2)" in resultado_texto
    assert "Pokémon (OPCIÓN 2)" in resultado_texto
    assert "Canal fuera de LATAM" not in resultado_texto
    assert resultado_texto.count('group-title="Deportes"') == 2
    assert resultado_texto.count('group-title="South Park"') == 2
    assert resultado_texto.count('group-title="Anime"') == 2
    assert "https://example.test/ufc-base.m3u8" in resultado_texto

    test_ajustes_referencia()
    print("SELFTEST OK: reconexión, orden, Pluto MX y ajustes de referencia.")
    

def test_ajustes_referencia() -> None:
    source = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="6759ee82bd523200083b4f0f" group-title="Anime",Avatar: La Leyenda de Aang',
        "https://jmp2.uk/plu-6759ee82bd523200083b4f0f.m3u8",
        '#EXTINF:-1 tvg-id="delmi-1" group-title="Anime",Delmi TV',
        "https://example.test/delmi-1.m3u8",
        '#EXTINF:-1 tvg-id="delmi-2" group-title="Anime",Delmi TV 2',
        "https://example.test/delmi-2.m3u8",
        '#EXTINF:-1 tvg-id="anime-es" group-title="Anime",Canal Anime [Pluto ES]',
        "https://jmp2.uk/plu-aaaaaaaaaaaaaaaaaaaaaaaa.m3u8",
        '#EXTINF:-1 tvg-id="cine-es" group-title="Cine",Cine Pluto ES',
        "https://jmp2.uk/plu-bbbbbbbbbbbbbbbbbbbbbbbb.m3u8",
        '#EXTINF:-1 tvg-id="baby" group-title="Infantiles",Baby Shark TV',
        "https://example.test/baby.m3u8",
        '#EXTINF:-1 tvg-id="wipeout" group-title="Competencia",Wipe Out',
        "https://example.test/wipeout.m3u8",
    ]
    before_order = [
        "id:6759ee82bd523200083b4f0f",
        "id:delmi-1",
        "id:delmi-2",
        "id:anime-es",
        "id:cine-es",
        "id:baby",
        "id:wipeout",
    ]
    result = aplicar_ajustes_referencia(source)
    result_text = "\n".join(result)
    assert "Canal Anime [Pluto ES]" not in result_text
    assert "Cine Pluto ES" in result_text
    assert result_text.count(",Delmi TV") == 1
    assert result_text.count(",Delmi TV 2") == 1
    avatar_index = next(i for i, x in enumerate(result) if x.startswith("#EXTINF") and ",Avatar: La Leyenda de Aang" in x)
    baby_index = next(i for i, x in enumerate(result) if x.startswith("#EXTINF") and ",Baby Shark TV" in x)
    assert 'group-title="Infantiles"' in result[avatar_index]
    assert avatar_index < baby_index
    assert "American Ninja Warrior" in result_text
    assert 'group-title="Competencia",American Ninja Warrior' in result_text
    assert "https://d4whmvwm0rdvi.cloudfront.net/10007/99951318/hls/master.m3u8?ads.xumo_channelId=99951318" in result_text
    assert "https://raw.githubusercontent.com/RoqueDJ/iptv-svg/main/1792421696158.png" in result_text
    validar_orden_canales(before_order, result)
    assert FUENTE_MAGMA == "https://raw.githubusercontent.com/Rayder378/IPTV-SV/refs/heads/main/Magma%20TV%20-Titan2022_XD.m3u"
    assert FUENTE_PLUTO_ALTERNATIVAS == "https://raw.githubusercontent.com/Rayder378/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u"

if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alimentar_principal import (
    aplicar_reconexion_por_canal,
    validar_orden_canales,
    firma_orden_canales,
    integrar_pluto_mx,
    aplicar_ajustes_referencia,
    cargar_ids_pluto_es_anime,
    FUENTE_MAGMA,
    FUENTE_PLUTO_ALTERNATIVAS,
    reubicar_bloques_pluto_sin_reordenar_principal,
    reemplazar_categoria,
    ordenar_bloques_magma_y_originales,
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
    assert channel_records(source) == channel_records(result), (
        "la reconexión alteró nombres, URLs o secuencia de canales"
    )
    text = "\n".join(result)

    assert text.count("#EXTVLCOPT:network-caching=5000") == 2
    assert text.count("#EXTVLCOPT:network-caching=1500") == 1  # solo se conserva en Pluto
    assert text.count("#EXTVLCOPT:http-reconnect=true") == 2
    assert reconnects_added == 1
    pluto_index = next(
        i for i, linea in enumerate(result)
        if linea.startswith('#EXTINF:-1 tvg-id="pluto-a"')
    )
    assert result[pluto_index:].count("#EXTVLCOPT:network-caching=1500") == 1
    assert result[pluto_index:].count("#EXTVLCOPT:network-caching=5000") == 0
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

    print("SELFTEST base OK: buffer VLC, reconexión y orden/URLs preservados.")


def test_ordenamiento_solicitado_de_entretenimiento_no_bloquea_la_lista() -> None:
    before = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="ent-a" group-title="Entretenimiento / Cine / Series",Canal A',
        "https://example.test/a.m3u8",
        '#EXTINF:-1 tvg-id="ent-b" group-title="Entretenimiento / Cine / Series",Canal B',
        "https://example.test/b.m3u8",
        '#EXTINF:-1 tvg-id="sports-a" group-title="Deportes",Canal Deportes A',
        "https://example.test/sports-a.m3u8",
        '#EXTINF:-1 tvg-id="sports-b" group-title="Deportes",Canal Deportes B',
        "https://example.test/sports-b.m3u8",
    ]
    after = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="ent-b" group-title="Entretenimiento / Cine / Series",Canal B',
        "https://example.test/b.m3u8",
        '#EXTINF:-1 tvg-id="ent-a" group-title="Entretenimiento / Cine / Series",Canal A',
        "https://example.test/a.m3u8",
        '#EXTINF:-1 tvg-id="sports-a" group-title="Deportes",Canal Deportes A',
        "https://example.test/sports-a.m3u8",
        '#EXTINF:-1 tvg-id="sports-b" group-title="Deportes",Canal Deportes B',
        "https://example.test/sports-b.m3u8",
    ]
    before_order = firma_orden_canales(before)
    entertainment_keys = set(firma_orden_canales([
        line for line in before
        if line.startswith("#EXTINF")
        and 'group-title="Entretenimiento / Cine / Series"' in line
    ]))
    entertainment_keys.update(firma_orden_canales([
        line for line in after
        if line.startswith("#EXTINF")
        and 'group-title="Entretenimiento / Cine / Series"' in line
    ]))
    validar_orden_canales(
        before_order,
        after,
        claves_reordenables=entertainment_keys,
    )


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
        '#EXTINF:-1 tvg-id="608035b8d8705f0007260287" group-title="Anime",Pluto TV Anime',
        "https://jmp2.uk/plu-608035b8d8705f0007260287.m3u8",
        '#EXTINF:-1 tvg-id="cine-es" group-title="Cine",Cine Pluto ES',
        "https://jmp2.uk/plu-bbbbbbbbbbbbbbbbbbbbbbbb.m3u8",
        '#EXTINF:-1 tvg-id="baby" group-title="Infantiles",Baby Shark TV',
        "https://example.test/baby.m3u8",
        '#EXTINF:-1 tvg-id="wipeout" group-title="Competencia",Wipe Out',
        "https://example.test/wipeout.m3u8",
    ]
    before_order = firma_orden_canales(source)
    result = aplicar_ajustes_referencia(source)
    result_text = "\n".join(result)
    assert "Canal Anime [Pluto ES]" not in result_text
    assert "Cine Pluto ES" in result_text
    assert sum(1 for x in result if x.startswith("#EXTINF") and x.endswith(",Delmi TV")) == 1
    assert sum(1 for x in result if x.startswith("#EXTINF") and x.endswith(",Delmi TV 2")) == 1
    avatar_index = next(i for i, x in enumerate(result) if x.startswith("#EXTINF") and ",Avatar: La Leyenda de Aang" in x)
    baby_index = next(i for i, x in enumerate(result) if x.startswith("#EXTINF") and ",Baby Shark TV" in x)
    assert 'group-title="Infantiles"' in result[avatar_index]
    assert avatar_index < baby_index
    assert "American Ninja Warrior" in result_text
    assert 'group-title="Competencia",American Ninja Warrior' in result_text
    assert "https://d4whmvwm0rdvi.cloudfront.net/10007/99951318/hls/master.m3u8?ads.xumo_channelId=99951318" in result_text
    assert "https://raw.githubusercontent.com/RoqueDJ/iptv-svg/main/1792421696158.png" in result_text
    validar_orden_canales(before_order, result)
    again = aplicar_ajustes_referencia(result)
    assert "\n".join(again).count("American Ninja Warrior") == 1
    assert sum(1 for x in again if x.startswith("#EXTINF") and "Avatar: La Leyenda de Aang" in x) == 1


def test_pluto_es_identity_lookup_fails_closed() -> None:
    class FailingSession:
        def get(self, url: str, timeout: int):
            raise OSError("catálogo Pluto ES temporalmente no disponible")

    try:
        cargar_ids_pluto_es_anime(FailingSession())
    except RuntimeError as exc:
        assert "se cancela la actualización" in str(exc)
    else:
        raise AssertionError("la caída de Pluto ES no canceló la actualización")


def test_pluto_es_identity_lookup_loads_catalog_ids() -> None:
    class FakeResponse:
        text = "\n".join([
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="bbbbbbbbbbbbbbbbbbbbbbbb" group-title="Anime",Anime ES',
            "https://jmp2.uk/plu-bbbbbbbbbbbbbbbbbbbbbbbb.m3u8",
            '#EXTINF:-1 tvg-id="cccccccccccccccccccccccc" group-title="Anime",Anime ES 2',
            "https://example.test/anime-es-2.m3u8",
        ])

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, timeout: int):
            return FakeResponse()

    ids = cargar_ids_pluto_es_anime(FakeSession())
    assert "bbbbbbbbbbbbbbbbbbbbbbbb" in ids
    assert "cccccccccccccccccccccccc" in ids
    assert "608035b8d8705f0007260287" in ids


def test_pluto_es_rejects_any_anime_without_identity() -> None:
    class FakeResponse:
        text = "\\n".join([
            "#EXTM3U",
            '#EXTINF:-1 group-title="Anime",Anime sin ID',
            "https://cdn.example.test/anime-sin-id.m3u8",
            '#EXTINF:-1 tvg-id="bbbbbbbbbbbbbbbbbbbbbbbb" group-title="Anime",Anime con ID',
            "https://jmp2.uk/plu-bbbbbbbbbbbbbbbbbbbbbbbb.m3u8",
        ])

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, timeout: int):
            return FakeResponse()

    try:
        cargar_ids_pluto_es_anime(FakeSession())
    except RuntimeError as exc:
        assert "se cancela la actualización" in str(exc)
    else:
        raise AssertionError("Pluto ES aceptó un canal Anime sin identidad")


def test_pluto_mx_importer() -> None:
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, timeout: int):
            if url.endswith("PlutoTV.MX.m3u"):
                return FakeResponse("\n".join([
                    "#EXTM3U",
                    '#EXTINF:-1 tvg-id="",Pokémon',
                    "https://jmp2.uk/plu-6870072ca9d5c45c3e9466f1.m3u8",
                    '#EXTINF:-1 tvg-id="",Cazador de Homicidas',
                    "https://jmp2.uk/plu-6109a9f5531b840007a4a187.m3u8",
                    '#EXTINF:-1 tvg-id="",Claro Sports (720p)',
                    "https://jmp2.uk/plu-6320d2755e54db000783fd87.m3u8",
                    "#EXTINF:-1 tvg-id=\"\",I Shouldn't Be Alive",
                    "https://jmp2.uk/plu-69fcaaa1853a01a827bcd056.m3u8",
                    '#EXTINF:-1 tvg-id="",Pluto TV Mi Obsesión Favorita',
                    "https://jmp2.uk/plu-6109ab25b84d6a0007504886.m3u8",
                ]))
            return FakeResponse("\n".join([
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="6870072ca9d5c45c3e9466f1" group-title="Anime",Pokémon',
                "https://jmp2.uk/plu-6870072ca9d5c45c3e9466f1.m3u8",
                "#EXTINF:-1 tvg-id=\"69fcaaa1853a01a827bcd056\" group-title=\"Documentales\",I Shouldn't Be Alive",
                "https://jmp2.uk/plu-69fcaaa1853a01a827bcd056.m3u8",
            ]))

    base = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="6870072ca9d5c45c3e9466f1" group-title="Anime",Pokémon',
        "https://example.test/pokemon-base.m3u8",
        '#EXTINF:-1 tvg-id="60ed5fb9c4716d0007d180c5" group-title="Investigación",Cazador de Homicidas',
        "https://example.test/cazador-base.m3u8",
        '#EXTINF:-1 tvg-id="aaaaaaaaaaaaaaaaaaaaaaaa" group-title="Deportes",Claro Sports (México)',
        "https://example.test/claro-base.m3u8",
        '#EXTINF:-1 tvg-id="baby" group-title="Infantiles",Baby Shark TV',
        "https://example.test/baby.m3u8",
        '#EXTINF:-1 tvg-id="wipeout" group-title="Competencia",Wipe Out',
        "https://example.test/wipeout.m3u8",
        '#EXTINF:-1 tvg-id="docs" group-title="Documentales y Cultura",Documental base',
        "https://example.test/docs.m3u8",
        '#EXTINF:-1 tvg-id="life" group-title="Estilo De Vida",Estilo base',
        "https://example.test/life.m3u8",
    ]
    result, audit = integrar_pluto_mx(base, FakeSession())
    result_text = "\n".join(result)
    assert audit["fuente_ok"] is True
    assert audit["agregadas"] == 4, audit
    assert audit["bases_nuevas"] == 2, audit
    assert audit["sin_coincidencia"] == 0, audit
    for cid in [
        "6870072ca9d5c45c3e9466f1",
        "6109a9f5531b840007a4a187",
        "6320d2755e54db000783fd87",
        "69fcaaa1853a01a827bcd056",
        "6109ab25b84d6a0007504886",
    ]:
        assert f"/plu-{cid}.m3u8" in result_text
    assert "Pokémon (OPCIÓN 2)" in result_text
    assert "Cazador de Homicidas (OPCIÓN 2)" in result_text
    assert "Claro Sports (México) (OPCIÓN 2)" in result_text
    assert "I Shouldn't Be Alive (OPCIÓN 2)" in result_text
    assert 'group-title="Documentales y Cultura",I Shouldn\'t Be Alive' in result_text
    assert 'group-title="Estilo De Vida",Pluto TV Mi Obsesión Favorita' in result_text
    again, audit_again = integrar_pluto_mx(result, FakeSession())
    assert audit_again["agregadas"] == 0, audit_again
    assert audit_again["bases_nuevas"] == 0, audit_again
    assert again.count("https://jmp2.uk/plu-6870072ca9d5c45c3e9466f1.m3u8") == 1



def test_pluto_options_remain_adjacent() -> None:
    channel_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    source = [
        "#EXTM3U",
        f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Competencia",Canal Base (OPCIÓN 2)',
        f"https://jmp2.uk/plu-{channel_id}.m3u8",
        '#EXTINF:-1 tvg-id="wipeout" group-title="Competencia",Wipe Out',
        "https://example.test/wipeout.m3u8",
        f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Competencia",Canal Base',
        f"https://service-stitcher.clusters.pluto.tv/v2/channel/{channel_id}/master.m3u8",
    ]
    result, _, _ = reubicar_bloques_pluto_sin_reordenar_principal(source)
    names = [line for line in result if line.startswith("#EXTINF")]
    base_index = next(i for i, line in enumerate(names) if line.endswith(",Canal Base"))
    option_index = next(i for i, line in enumerate(names) if line.endswith(",Canal Base (OPCIÓN 2)"))
    assert option_index == base_index + 1, names


def test_extinf_category_fallback_preserves_duration() -> None:
    line = '#EXTINF:-1 tvg-id="demo",Canal demo'
    updated = reemplazar_categoria(line, "Estilo De Vida")
    assert updated == '#EXTINF:-1 group-title="Estilo De Vida" tvg-id="demo",Canal demo'
    assert "-1 group-title=" in updated and 'Vida"-1' not in updated

def test_pluto_mx_fails_closed() -> None:
    class FailingSession:
        def get(self, url: str, timeout: int):
            raise OSError("fuente temporalmente no disponible")

    original = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="canal-a" group-title="Anime",Canal A',
        "https://example.test/canal-a.m3u8",
    ]
    try:
        integrar_pluto_mx(original, FailingSession())
    except RuntimeError as exc:
        assert "se cancela la actualización" in str(exc)
    else:
        raise AssertionError("Pluto MX fallido no canceló la actualización")


def test_pluto_mx_rejects_empty_m3u() -> None:
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, timeout: int):
            if url.endswith("PlutoTV.MX.m3u"):
                return FakeResponse("#EXTM3U")
            return FakeResponse("#EXTM3U\\n#EXTINF:-1,Canal LATAM\\nhttps://latam.example/canal.m3u8")

    original = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="canal-a" group-title="Anime",Canal A',
        "https://example.test/canal-a.m3u8",
    ]
    try:
        integrar_pluto_mx(original, FakeSession())
    except RuntimeError as exc:
        assert "se cancela la actualización" in str(exc)
    else:
        raise AssertionError("Pluto MX aceptó una M3U vacía como importación válida")


def test_pluto_option_on_external_cdn_stays_adjacent() -> None:
    channel_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    source = [
        "#EXTM3U",
        f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Anime",Canal Pluto',
        f"https://service-stitcher.clusters.pluto.tv/v2/channel/{channel_id}/master.m3u8",
        f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Anime",Canal Pluto (OPCIÓN 2)',
        "https://cdn.example.test/pluto-option.m3u8",
    ]
    result, _, _ = reubicar_bloques_pluto_sin_reordenar_principal(source)
    names = [line for line in result if line.startswith("#EXTINF")]
    base_index = next(i for i, line in enumerate(names) if line.endswith(",Canal Pluto"))
    option_index = next(i for i, line in enumerate(names) if line.endswith(",Canal Pluto (OPCIÓN 2)"))
    assert option_index == base_index + 1, names


def test_magma_and_original_entertainment_blocks_are_sorted() -> None:
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeSession:
        def get(self, url: str, timeout: int):
            return FakeResponse("\n".join([
                "#EXTM3U",
                '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Alpha',
                "https://magma.example/alpha.m3u8",
                '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Zulu',
                "https://magma.example/zulu.m3u8",
            ]))

    lines = [
        "#EXTM3U",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Retro TV',
        "https://original.example/retro.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Zulu [MAGMA]',
        "https://magma.example/zulu.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Original Zulu',
        "https://original.example/zulu.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Venevisión Internacional (Venezuela)',
        "https://original.example/venevision-int.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Venevisión [V3](Venezuela)',
        "https://original.example/venevision-v3.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Venevisión (Venezuela)[Opc.2]',
        "https://original.example/venevision-opc2.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Venevisión [V2](Venezuela)',
        "https://original.example/venevision-v2.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Venevisión (Venezuela)',
        "https://original.example/venevision.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Chespirito TV',
        "https://original.example/chespirito.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Alpha [MAGMA]',
        "https://magma.example/alpha.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Los Simpson Latino Opc. 2',
        "https://original.example/simpson2.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Original Alpha',
        "https://original.example/alpha.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",El Chavo TV',
        "https://original.example/chavo.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Los Simpson Latino',
        "https://original.example/simpson.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Canal fijo extra',
        "https://original.example/fijo-extra.m3u8",
        '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Canal original extra',
        "https://original.example/extra.m3u8",
        '#EXTINF:-1 group-title="Anime",Delmi TV [V2]',
        "https://original.example/delmi.m3u8",
    ]
    result, audit = ordenar_bloques_magma_y_originales(lines, FakeSession())
    names = [
        line.split(",", 1)[1]
        for line in result
        if line.startswith("#EXTINF") and 'group-title="Entretenimiento / Cine / Series"' in line
    ]
    assert names[:5] == [
        "Los Simpson Latino",
        "Los Simpson Latino Opc. 2",
        "El Chavo TV",
        "Chespirito TV",
        "Retro TV",
    ], names
    assert names[5:7] == ["Alpha [MAGMA]", "Zulu [MAGMA]"], names
    assert names[7:] == [
        "Canal fijo extra",
        "Canal original extra",
        "Original Alpha",
        "Original Zulu",
        "Venevisión (Venezuela)",
        "Venevisión (Venezuela)[Opc.2]",
        "Venevisión [V2](Venezuela)",
        "Venevisión [V3](Venezuela)",
        "Venevisión Internacional (Venezuela)",
    ], names
    assert audit == {"fijos": 5, "magma": 2, "originales": 9, "urls_magma": 2}
    assert "Delmi TV [V2]" in "\n".join(result)


def test_pluto_mx_tvg_id_keeps_extinf_duration() -> None:
    class FakeResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    channel_id = "6320d2755e54db000783fd87"

    class FakeSession:
        def get(self, url: str, timeout: int):
            if url.endswith("PlutoTV.MX.m3u"):
                return FakeResponse("\n".join([
                    "#EXTM3U",
                    '#EXTINF:-1 tvg-id="",Claro Sports (720p)',
                    f"https://jmp2.uk/plu-{channel_id}.m3u8",
                ]))
            return FakeResponse("\\n".join([
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="6320d2755e54db000783fd87" group-title="Deportes",Claro Sports',
                f"https://jmp2.uk/plu-{channel_id}.m3u8",
            ]))

    base = [
        "#EXTM3U",
        '#EXTINF:0 type="stream" group-title="Deportes",Claro Sports (México)',
        f"https://service-stitcher.clusters.pluto.tv/v2/channel/{channel_id}/master.m3u8",
    ]
    result, audit = integrar_pluto_mx(base, FakeSession())
    option = next(
        line for line in result
        if line.startswith("#EXTINF") and line.endswith(",Claro Sports (México) (OPCIÓN 2)")
    )
    assert option.startswith(f'#EXTINF:0 tvg-id="{channel_id}" type="stream"')
    assert audit["agregadas"] == 1


def test_external_source_urls() -> None:
    assert FUENTE_MAGMA == "https://raw.githubusercontent.com/Rayder378/IPTV-SV/refs/heads/main/Magma%20TV%20-Titan2022_XD.m3u"
    assert FUENTE_PLUTO_ALTERNATIVAS == "https://raw.githubusercontent.com/Rayder378/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u"


if __name__ == "__main__":
    main()
    test_ordenamiento_solicitado_de_entretenimiento_no_bloquea_la_lista()
    test_ajustes_referencia()
    test_pluto_es_identity_lookup_fails_closed()
    test_pluto_es_identity_lookup_loads_catalog_ids()
    test_pluto_es_rejects_any_anime_without_identity()
    test_pluto_mx_importer()
    test_pluto_mx_rejects_empty_m3u()
    test_pluto_options_remain_adjacent()
    test_extinf_category_fallback_preserves_duration()
    test_pluto_mx_fails_closed()
    test_pluto_option_on_external_cdn_stays_adjacent()
    test_magma_and_original_entertainment_blocks_are_sorted()
    test_pluto_mx_tvg_id_keeps_extinf_duration()
    test_external_source_urls()
    print("SELFTEST OK: MAGMA, Pluto MX, Anime, Avatar y American Ninja Warrior.")


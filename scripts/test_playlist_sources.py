import base64
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from playlist_sources import load_principal_settings, load_sources
import alimentar_principal as ap


class PlaylistSourceRegistryTests(unittest.TestCase):
    def test_principal_and_god_sources_are_loadable_and_unique(self):
        principal = load_principal_settings()
        god = load_sources("god")
        self.assertGreaterEqual(len(principal["sources"]), 15)
        self.assertGreaterEqual(len(principal["pluto_sources"]), 3)
        self.assertGreaterEqual(len(god), 30)
        self.assertEqual(len(god), len(set(god)))

    def test_main_pluto_sources_are_the_requested_three_regions(self):
        principal = load_principal_settings()
        paths = [url.rsplit("/", 1)[-1] for url in principal["pluto_sources"]]
        self.assertEqual(paths, ["pluto_latam.m3u", "pluto_es.m3u", "pluto_mx.m3u"])

    def test_brazil_catalog_is_refresh_only_and_not_an_import_source(self):
        principal = load_principal_settings()
        catalog_paths = [url.rsplit("/", 1)[-1] for url in principal["pluto_catalog_sources"]]
        self.assertEqual(catalog_paths, ["pluto_br.m3u"])
        self.assertNotIn(principal["pluto_catalog_sources"][0], principal["pluto_sources"])
        self.assertEqual(ap.FUENTES_PLUTO_CATALOGO[-1], principal["pluto_catalog_sources"][0])

    def test_pluto_priority_dedup_preserves_distinct_urls_as_options(self):
        channel_id = "68a3a97fd8f7693ae3f8575f"
        base_url = (
            "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/"
            f"v2/stitch/hls/channel/{channel_id}/master.m3u8?jwt=base&country=CL"
        )
        mx_url = f"https://jmp2.uk/plu-{channel_id}.m3u8"
        alternate_url = (
            "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/"
            f"v2/stitch/hls/channel/{channel_id}/master.m3u8?jwt=other&country=MX"
        )
        lines = [
            "#EXTM3U",
            f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Infantiles",Los Pitufos',
            base_url,
            f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Infantiles",Los Pitufos (OPCIÓN 2)',
            mx_url,
            f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Infantiles",Los Pitufos',
            alternate_url,
            f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Infantiles",Los Pitufos duplicado',
            alternate_url,
        ]

        result, removed = ap.deduplicar_pluto_por_prioridad(lines, {})
        joined = "\n".join(result)
        names = [
            line.split(",", 1)[1]
            for line in result
            if line.startswith("#EXTINF") and "Los Pitufos" in line
        ]
        self.assertEqual(removed, 1)
        self.assertIn(base_url, joined)
        self.assertIn(mx_url, joined)
        self.assertIn(alternate_url, joined)
        self.assertEqual(len(names), 3)
        self.assertTrue(any("(OPCIÓN 2)" in name for name in names))
        self.assertTrue(any("(OPCIÓN 3)" in name for name in names))

    def test_deduplicar_urls_exactas_conserva_primer_bloque_y_metadatos(self):
        url_radio = "https://cl-2.backend.energeek.cl/bkp/egradioweb/index.m3u8?token=test"
        url_retro = "https://cl-2.backend.energeek.cl/bkp/egretroweb/index.m3u8?token=test"
        lines = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-name="EnerGeek Radio" tvg-logo="https://cdn.example/radio.png" group-title="CHILE TV",EnerGeek Radio',
            "#EXTVLCOPT:http-reconnect=true",
            url_radio,
            '#EXTINF:-1 tvg-name="Radio duplicada" group-title="Musica",Radio duplicada',
            url_radio,
            '#EXTINF:-1 tvg-name="EnerGeek Retro" tvg-logo="https://cdn.example/retro.png" group-title="CHILE TV",EnerGeek Retro',
            url_retro,
            '#EXTINF:-1 tvg-name="Retro duplicado" group-title="Series",Retro duplicado',
            url_retro,
        ]
        result, removed = ap.deduplicar_urls_exactas(lines)
        joined = "\n".join(result)
        self.assertEqual(removed, 2)
        self.assertEqual(joined.count(url_radio), 1)
        self.assertEqual(joined.count(url_retro), 1)
        self.assertIn('tvg-logo="https://cdn.example/radio.png"', joined)
        self.assertIn('tvg-logo="https://cdn.example/retro.png"', joined)
        self.assertIn("#EXTVLCOPT:http-reconnect=true", joined)
        self.assertNotIn("Radio duplicada", joined)
        self.assertNotIn("Retro duplicado", joined)

    def test_stable_pluto_mx_is_used_as_fallback_catalog(self):
        self.assertEqual(
            ap.FUENTES_PLUTO_CATALOGO,
            [*ap.FUENTES_PLUTO[:2], ap.FUENTE_PLUTO_ALTERNATIVAS, *ap.FUENTES_PLUTO[2:], *ap.FUENTES_PLUTO_CATALOGO_EXTRA],
        )

    def test_pluto_refresh_prefers_stable_mx_and_removes_only_expired_orphans(self):
        class Response:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                return None

        class Session:
            def __init__(self, contents, failing=None):
                self.contents = contents
                self.failing = failing

            def get(self, url, timeout=30):
                if url == self.failing:
                    raise RuntimeError("fuente temporalmente no disponible")
                return Response(self.contents[url])

        def token_url(channel_id, exp, country="MX"):
            payload = base64.urlsafe_b64encode(
                json.dumps({"exp": exp}).encode("utf-8")
            ).decode("ascii").rstrip("=")
            return (
                "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/"
                f"v2/stitch/hls/channel/{channel_id}/master.m3u8"
                f"?jwt=x.{payload}.x&country={country}"
            )

        def m3u(channel_id, name, url):
            return (
                f'#EXTINF:-1 tvg-id="{channel_id}" group-title="Pluto",{name}\n'
                f"{url}\n"
            )

        latam_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
        es_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
        mx_id = "cccccccccccccccccccccccc"
        orphan_id = "dddddddddddddddddddddddd"
        live_orphan_id = "eeeeeeeeeeeeeeeeeeeeeeee"
        internal_only_id = "ffffffffffffffffffffffff"
        br_id = "999999999999999999999999"

        sources = list(ap.FUENTES_PLUTO_CATALOGO)
        self.assertEqual(len(sources), 5)
        contents = {
            sources[0]: "#EXTM3U\n" + m3u(latam_id, "Canal LATAM", f"https://jmp2.uk/plu-{latam_id}.m3u8"),
            sources[1]: "#EXTM3U\n" + m3u(es_id, "Canal ES", f"https://jmp2.uk/plu-{es_id}.m3u8"),
            sources[2]: "#EXTM3U\n" + m3u(mx_id, "Canal MX estable", f"https://jmp2.uk/plu-{mx_id}.m3u8"),
            # El catálogo MX interno trae un duplicado tokenizado y un canal
            # exclusivo con JWT vencido; el externo estable debe ganar.
            sources[3]: (
                "#EXTM3U\n"
                + m3u(mx_id, "Canal MX tokenizado", token_url(mx_id, 1))
                + m3u(internal_only_id, "Canal MX solo interno", token_url(internal_only_id, 1))
            ),
            # Brasil se consulta solo para renovar IDs ya presentes; no alimenta altas.
            sources[4]: "#EXTM3U\n" + m3u(br_id, "Canal Brasil", f"https://jmp2.uk/plu-{br_id}.m3u8"),
        }

        lineas = ["#EXTM3U"]
        lineas += [
            f'#EXTINF:-1 tvg-id="{latam_id}" group-title="Pluto",Canal LATAM',
            token_url(latam_id, 1, "CL"),
            f'#EXTINF:-1 tvg-id="{mx_id}" group-title="Pluto",Canal MX',
            token_url(mx_id, 1, "MX"),
            f'#EXTINF:-1 tvg-id="{orphan_id}" group-title="Pluto",Canal retirado',
            token_url(orphan_id, 1, "MX"),
            f'#EXTINF:-1 tvg-id="{internal_only_id}" group-title="Pluto",Canal MX solo interno',
            token_url(internal_only_id, 1, "MX"),
            f'#EXTINF:-1 tvg-id="{br_id}" group-title="Brasil",Canal Brasil',
            token_url(br_id, 1, "BR"),
            f'#EXTINF:-1 tvg-id="{live_orphan_id}" group-title="Pluto",Canal temporal aún vigente',
            token_url(live_orphan_id, 4102444800, "MX"),
            '#EXTINF:-1 tvg-id="no-pluto" group-title="Test",Canal no Pluto',
            "https://example.com/live.m3u8",
        ]

        original_minimos = ap.PLUTO_CATALOGO_MINIMOS
        ap.PLUTO_CATALOGO_MINIMOS = {fuente: 1 for fuente in sources}
        try:
            result, stats = ap.reemplazar_pluto_tercero_por_propio(
                lineas, Session(contents)
            )
            joined = "\n".join(result)
            self.assertTrue(stats["catalogo_completo"])
            self.assertEqual(stats["expirados_eliminados"], 2)
            self.assertIn(f"https://jmp2.uk/plu-{latam_id}.m3u8", joined)
            self.assertIn(f"https://jmp2.uk/plu-{mx_id}.m3u8", joined)
            self.assertIn(f"https://jmp2.uk/plu-{br_id}.m3u8", joined)
            self.assertNotIn("Canal retirado", joined)
            self.assertNotIn("Canal MX solo interno", joined)
            self.assertIn("Canal temporal aún vigente", joined)
            self.assertIn("https://example.com/live.m3u8", joined)
    
            # Si falla una fuente, no se retiran canales sin reemplazo aunque su
            # token esté vencido: se prioriza conservarlos hasta recuperar catálogo.
            partial, partial_stats = ap.reemplazar_pluto_tercero_por_propio(
                lineas, Session(contents, failing=sources[-1])
            )
            self.assertFalse(partial_stats["catalogo_completo"])
            self.assertIn("Canal retirado", "\n".join(partial))
            self.assertIn("Canal MX solo interno", "\n".join(partial))
        finally:
            ap.PLUTO_CATALOGO_MINIMOS = original_minimos


    def test_god_only_references_existing_regional_pluto_outputs(self):
        god = load_sources("god")
        local = [url for url in god if "/pluto/output/playlists/" in url]
        expected = {
            f"https://raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/refs/heads/main/pluto/output/playlists/pluto_{code}.m3u"
            for code in ("latam", "es", "mx", "ar", "br", "cl", "us")
        }
        self.assertEqual(set(local), expected)
        self.assertFalse(any(url.endswith("/pluto_all.m3u") or url.endswith("/pluto.m3u") for url in god))

    def test_special_sources_keep_their_current_urls(self):
        special = load_principal_settings()["special_sources"]
        self.assertEqual(special["iptvsv"], "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/IPTVSV.m3u")
        self.assertEqual(special["magma"], "https://raw.githubusercontent.com/Rayder378/IPTV-SV/refs/heads/main/Magma%20TV%20-Titan2022_XD.m3u")
        self.assertEqual(special["pluto_mx_alternatives"], "https://raw.githubusercontent.com/JMigue85/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u")


if __name__ == "__main__":
    unittest.main()

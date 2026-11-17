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

    def test_stable_pluto_mx_is_used_as_fallback_catalog(self):
        self.assertEqual(
            ap.FUENTES_PLUTO_CATALOGO,
            [*ap.FUENTES_PLUTO[:2], ap.FUENTE_PLUTO_ALTERNATIVAS, *ap.FUENTES_PLUTO[2:]],
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

        sources = list(ap.FUENTES_PLUTO_CATALOGO)
        self.assertEqual(len(sources), 4)
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

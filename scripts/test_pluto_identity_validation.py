"""Regression tests for Pluto identity aliases during final coverage checks."""
import base64
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alimentar_principal import (
    identidades_pluto,
    calcular_ids_pluto_faltantes,
    reemplazar_pluto_tercero_por_propio,
    jwt_necesita_renovacion_en_url,
)


class PlutoIdentityValidationTests(unittest.TestCase):
    def test_tvg_id_and_url_channel_id_are_both_retained_as_aliases(self):
        extinf = '#EXTINF:-1 tvg-id="epg.alias" group-title="Anime",Canal'
        url = "https://service.example/vod/channel/0123456789abcdef01234567/master.m3u8"
        self.assertEqual(
            identidades_pluto(extinf, url),
            {"id:epg.alias", "id:0123456789abcdef01234567"},
        )

    def test_same_channel_url_passes_when_tvg_id_was_normalized_differently(self):
        source_extinf = '#EXTINF:-1 tvg-id="epg.alias",Canal'
        final_extinf = '#EXTINF:-1 tvg-id="different.epg.alias",Canal'
        url = "https://service.example/vod/channel/0123456789abcdef01234567/master.m3u8"
        required = {"id:epg.alias"}
        aliases = {"id:epg.alias": identidades_pluto(source_extinf, url)}
        final_aliases = identidades_pluto(final_extinf, url)
        self.assertEqual(calcular_ids_pluto_faltantes(required, aliases, final_aliases), set())

    def test_real_missing_channel_is_still_rejected(self):
        source_extinf = '#EXTINF:-1 tvg-id="epg.alias",Canal'
        source_url = "https://service.example/vod/channel/0123456789abcdef01234567/master.m3u8"
        required = {"id:epg.alias"}
        aliases = {"id:epg.alias": identidades_pluto(source_extinf, source_url)}
        final_aliases = identidades_pluto(
            '#EXTINF:-1 tvg-id="other.channel",Otro canal',
            "https://service.example/vod/channel/abcdef0123456789abcdef01/master.m3u8",
        )
        self.assertEqual(
            calcular_ids_pluto_faltantes(required, aliases, final_aliases),
            {"id:epg.alias"},
        )

    def test_expired_mx_tagged_url_prefers_latam_catalog_over_mx(self):
        old_url = (
            "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/channel/0123456789abcdef01234567/"
            "master.m3u8?country=MX&jwt=old"
        )
        latam_url = (
            "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/channel/0123456789abcdef01234567/"
            "master.m3u8?country=MX&jwt=latam"
        )
        mx_url = (
            "https://mx.example/channel/0123456789abcdef01234567/"
            "master.m3u8?country=MX&jwt=mx"
        )
        extinf = '#EXTINF:-1 tvg-id="epg.alias" group-title="Infantiles",Canal'
        catalog = (
            {"epg.alias": {"url": latam_url}, "0123456789abcdef01234567": {"url": latam_url}},
            {"canal": {"url": latam_url}},
            {"latam": {}, "es": {}, "mx": {
                "epg.alias": {"url": mx_url},
                "0123456789abcdef01234567": {"url": mx_url},
            }},
            0,
            True,
        )
        with patch("alimentar_principal.cargar_catalogo_pluto_propio", return_value=catalog), \
             patch("alimentar_principal.jwt_necesita_renovacion_en_url",
                   side_effect=lambda url, *args, **kwargs: "jwt=old" in url), \
             patch("alimentar_principal.jwt_expirado_en_url",
                   side_effect=lambda url, *args, **kwargs: "jwt=old" in url):
            result, stats = reemplazar_pluto_tercero_por_propio(
                ["#EXTM3U", extinf, old_url],
                session=None,
            )
        self.assertEqual(result[-1], latam_url)
        self.assertEqual(stats["reemplazados"], 1)

    def test_expired_brazil_url_is_preserved_when_no_brazil_catalog_exists(self):
        old_url = (
            "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/channel/abcdef0123456789abcdef0123/"
            "master.m3u8?country=BR&jwt=old"
        )
        extinf = '#EXTINF:-1 tvg-id="br.channel" group-title="Brasil",Canal Brasil'
        catalog = ({}, {}, {"latam": {}, "es": {}, "mx": {}}, 0, True)
        with patch("alimentar_principal.cargar_catalogo_pluto_propio", return_value=catalog), \
             patch("alimentar_principal.jwt_necesita_renovacion_en_url", return_value=True), \
             patch("alimentar_principal.jwt_expirado_en_url", return_value=True):
            result, stats = reemplazar_pluto_tercero_por_propio(
                ["#EXTM3U", extinf, old_url],
                session=None,
            )
        self.assertEqual(result[-1], old_url)
        self.assertEqual(stats["expirados_eliminados"], 0)
        self.assertEqual(stats["conservados_sin_reemplazo"], 1)

    def test_non_jwt_mx_alternative_is_preserved_as_an_independent_option(self):
        external_url = "https://jmp2.uk/plu-0123456789abcdef01234567.m3u8"
        latam_url = (
            "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/channel/0123456789abcdef01234567/"
            "master.m3u8?country=MX&jwt=latam"
        )
        extinf = '#EXTINF:-1 tvg-id="epg.alias" group-title="Infantiles",Canal'
        catalog = (
            {"epg.alias": {"url": latam_url}, "0123456789abcdef01234567": {"url": latam_url}},
            {"canal": {"url": latam_url}},
            {"latam": {}, "es": {}, "mx": {}},
            0,
            True,
        )
        with patch("alimentar_principal.cargar_catalogo_pluto_propio", return_value=catalog):
            result, stats = reemplazar_pluto_tercero_por_propio(
                ["#EXTM3U", extinf, external_url],
                session=None,
            )
        self.assertEqual(result[-1], external_url)
        self.assertEqual(stats["sin_jwt_conservados"], 1)

    def test_jwt_with_less_than_six_hours_is_marked_for_early_refresh(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"exp": 1000}).encode("utf-8")
        ).decode("ascii").rstrip("=")
        url = f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/master.m3u8?jwt=header.{payload}.signature"
        self.assertTrue(jwt_necesita_renovacion_en_url(url, margen_segundos=600, ahora=500))
        self.assertFalse(jwt_necesita_renovacion_en_url(url, margen_segundos=100, ahora=500))



    def test_exact_url_channel_id_beats_conflicting_epg_alias(self):
        old_url = "https://service-stitcher.pluto.tv/channel/0123456789abcdef01234567/master.m3u8?jwt=old"
        expected_url = "https://service-stitcher.pluto.tv/channel/0123456789abcdef01234567/master.m3u8?jwt=latam"
        wrong_url = "https://service-stitcher.pluto.tv/channel/abcdef0123456789abcdef01/master.m3u8?jwt=wrong"
        extinf = '#EXTINF:-1 tvg-id="epg.alias" group-title="Infantiles",Canal'
        catalog = (
            {"epg.alias": {"url": wrong_url}, "0123456789abcdef01234567": {"url": expected_url}},
            {},
            {"latam": {}, "es": {}, "mx": {}},
            0,
            True,
        )
        with patch("alimentar_principal.cargar_catalogo_pluto_propio", return_value=catalog), \
             patch("alimentar_principal.jwt_necesita_renovacion_en_url",
                   side_effect=lambda url, *args, **kwargs: "jwt=old" in url), \
             patch("alimentar_principal.jwt_expirado_en_url", return_value=False):
            result, stats = reemplazar_pluto_tercero_por_propio(
                ["#EXTM3U", extinf, old_url],
                session=None,
            )
        self.assertEqual(result[-1], expected_url)
        self.assertEqual(stats["reemplazados"], 1)

    def test_name_fallback_uses_normalized_channel_name(self):
        old_url = "https://service-stitcher.pluto.tv/channel/aaaaaaaaaaaaaaaaaaaaaaaa/master.m3u8?jwt=old"
        expected_url = "https://service-stitcher.pluto.tv/channel/bbbbbbbbbbbbbbbbbbbbbbbb/master.m3u8?jwt=fresh"
        extinf = '#EXTINF:-1 tvg-id="unmatched.alias" group-title="Infantiles",Canal Kids [Opción 2]'
        catalog = (
            {},
            {"canalkids": {"url": expected_url}},
            {"latam": {}, "es": {}, "mx": {}},
            0,
            True,
        )
        with patch("alimentar_principal.cargar_catalogo_pluto_propio", return_value=catalog), \
             patch("alimentar_principal.jwt_necesita_renovacion_en_url",
                   side_effect=lambda url, *args, **kwargs: "jwt=old" in url), \
             patch("alimentar_principal.jwt_expirado_en_url", return_value=False):
            result, stats = reemplazar_pluto_tercero_por_propio(
                ["#EXTM3U", extinf, old_url],
                session=None,
            )
        self.assertEqual(result[-1], expected_url)
        self.assertEqual(stats["reemplazados"], 1)

if __name__ == "__main__":
    unittest.main()

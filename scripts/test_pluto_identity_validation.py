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
            "https://stitcher.example/channel/0123456789abcdef01234567/"
            "master.m3u8?country=MX&jwt=old"
        )
        latam_url = (
            "https://stitcher.example/channel/0123456789abcdef01234567/"
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
            "https://stitcher.example/channel/abcdef0123456789abcdef0123/"
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

    def test_jwt_with_less_than_six_hours_is_marked_for_early_refresh(self):
        payload = base64.urlsafe_b64encode(
            json.dumps({"exp": 1000}).encode("utf-8")
        ).decode("ascii").rstrip("=")
        url = f"https://stitcher.example/master.m3u8?jwt=header.{payload}.signature"
        self.assertTrue(jwt_necesita_renovacion_en_url(url, margen_segundos=600, ahora=500))
        self.assertFalse(jwt_necesita_renovacion_en_url(url, margen_segundos=100, ahora=500))


if __name__ == "__main__":
    unittest.main()

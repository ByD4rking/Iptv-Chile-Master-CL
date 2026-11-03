"""Regression tests for Pluto identity aliases during final coverage checks."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alimentar_principal import (
    identidades_pluto,
    ids_pluto_faltantes,
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
        self.assertEqual(ids_pluto_faltantes(required, aliases, final_aliases), set())

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
            ids_pluto_faltantes(required, aliases, final_aliases),
            {"id:epg.alias"},
        )


if __name__ == "__main__":
    unittest.main()

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from playlist_sources import load_principal_settings, load_sources


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
        self.assertEqual(special["pluto_mx_alternatives"], "https://raw.githubusercontent.com/Rayder378/IPTV-SV/refs/heads/main/PlutoTV.MX.m3u")


if __name__ == "__main__":
    unittest.main()

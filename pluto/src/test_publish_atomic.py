from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate_multiregion as generator
from regions import REGIONS


class AtomicPlaylistPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.playlists = self.root / "playlists"
        self.regional = self.root / "regional"
        self.playlists.mkdir()
        self.regional.mkdir()
        self.playlist = self.playlists / "pluto_cl.m3u"
        self.data = self.regional / "channels_cl.json"
        self.old_m3u = (
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="old" tvg-name="Anterior",Anterior\n'
            'https://example.test/old/master.m3u8\n'
        )
        self.old_json = '[{"id": "old", "name": "Anterior", "stream": "https://example.test/old/master.m3u8"}]'
        self.playlist.write_text(self.old_m3u, encoding="utf-8")
        self.data.write_text(self.old_json, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_failed_m3u_replace_restores_both_previous_files(self):
        channels = [{
            "id": "new",
            "name": "Nuevo",
            "stream": "https://example.test/new/master.m3u8",
            "category": "Entretenimiento",
        }]
        original_replace = Path.replace
        injected = {"done": False}

        def fail_new_playlist_once(path, target):
            if (
                not injected["done"]
                and path == self.playlist.with_suffix(".m3u.tmp")
                and target == self.playlist
            ):
                injected["done"] = True
                raise OSError("fallo simulado al reemplazar M3U")
            return original_replace(path, target)

        with (
            patch.object(generator, "PLAYLIST_DIR", self.playlists),
            patch.object(generator, "REGIONAL_DATA_DIR", self.regional),
            patch.object(generator, "preserve_previous_channels", return_value=(channels, 0)),
            patch.object(generator, "refresh_preserved_streams", return_value=channels),
            patch.object(generator, "preserve_previous_order", return_value=channels),
            patch.object(Path, "replace", autospec=True, side_effect=fail_new_playlist_once),
        ):
            with self.assertRaisesRegex(OSError, "fallo simulado"):
                generator.write_if_safe(REGIONS["cl"], channels)

        self.assertTrue(injected["done"], "la prueba debe alcanzar el reemplazo real del M3U")
        self.assertEqual(self.playlist.read_text(encoding="utf-8"), self.old_m3u)
        self.assertEqual(self.data.read_text(encoding="utf-8"), self.old_json)
        self.assertFalse(self.playlist.with_suffix(".m3u.tmp").exists())
        self.assertFalse(self.data.with_suffix(".json.tmp").exists())
        self.assertFalse(self.playlist.with_suffix(".m3u.rollback").exists())
        self.assertFalse(self.data.with_suffix(".json.rollback").exists())

    def test_successful_publish_updates_playlist_and_data(self):
        channels = [{
            "id": "new",
            "name": "Nuevo",
            "stream": "https://example.test/new/master.m3u8",
            "category": "Entretenimiento",
        }]
        with (
            patch.object(generator, "PLAYLIST_DIR", self.playlists),
            patch.object(generator, "REGIONAL_DATA_DIR", self.regional),
            patch.object(generator, "preserve_previous_channels", return_value=(channels, 0)),
            patch.object(generator, "refresh_preserved_streams", return_value=channels),
            patch.object(generator, "preserve_previous_order", return_value=channels),
        ):
            path, count, updated, _ = generator.write_if_safe(REGIONS["cl"], channels)

        self.assertEqual(path, self.playlist)
        self.assertEqual(count, 1)
        self.assertTrue(updated)
        self.assertIn('tvg-id="new"', self.playlist.read_text(encoding="utf-8"))
        stored = json.loads(self.data.read_text(encoding="utf-8"))
        self.assertEqual(stored[0]["id"], "new")


if __name__ == "__main__":
    unittest.main(verbosity=2)

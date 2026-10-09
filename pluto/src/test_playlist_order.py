from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate_multiregion import preserve_previous_order


class PlaylistOrderTests(unittest.TestCase):
    def test_existing_order_is_kept_and_new_channels_are_appended(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            playlist = Path(temporary_directory) / "previous.m3u"
            playlist.write_text(
                "#EXTM3U\n"
                '#EXTINF:-1 tvg-id="channel-b" tvg-name="Canal B",Canal B\n'
                "https://example.test/b/master.m3u8\n"
                '#EXTINF:-1 tvg-id="channel-a" tvg-name="Canal A",Canal A\n'
                "https://example.test/a/master.m3u8\n",
                encoding="utf-8",
            )
            fresh = [
                {"id": "channel-new", "name": "Nuevo", "stream": "https://example.test/new/master.m3u8"},
                {"id": "channel-a", "name": "Canal A actualizado", "stream": "https://example.test/a2/master.m3u8"},
                {"id": "channel-b", "name": "Canal B", "stream": "https://example.test/b2/master.m3u8"},
            ]

            ordered = preserve_previous_order(playlist, fresh)
            self.assertEqual(
                [channel["id"] for channel in ordered],
                ["channel-b", "channel-a", "channel-new"],
            )

    def test_rotated_id_keeps_its_slot_when_name_is_unique(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            playlist = Path(temporary_directory) / "previous.m3u"
            playlist.write_text(
                "#EXTM3U\n"
                '#EXTINF:-1 tvg-id="old-id" tvg-name="Canal Uno",Canal Uno\n'
                "https://example.test/one/master.m3u8\n",
                encoding="utf-8",
            )
            fresh = [
                {"id": "new-id", "name": "Canal Uno", "stream": "https://example.test/one-new/master.m3u8"},
                {"id": "new-channel", "name": "Canal Nuevo", "stream": "https://example.test/new/master.m3u8"},
            ]

            ordered = preserve_previous_order(playlist, fresh)
            self.assertEqual(
                [channel["id"] for channel in ordered],
                ["new-id", "new-channel"],
            )


if __name__ == "__main__":
    unittest.main()

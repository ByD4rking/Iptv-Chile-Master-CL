from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate_multiregion import preserve_previous_order, validate_playlist_content


class PlaylistOrderTests(unittest.TestCase):
    def test_valid_playlist_passes_validation(self):
        content = (
            "#EXTM3U\\n"
            '#EXTINF:-1 tvg-id="one" tvg-name="Uno",Uno\\n'
            "https://example.test/one/master.m3u8\\n"
            '#EXTINF:-1 tvg-id="two" tvg-name="Dos",Dos\\n'
            "https://example.test/two/master.m3u8\\n"
        )
        self.assertEqual(validate_playlist_content(content), 2)

    def test_empty_or_missing_header_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_playlist_content("")
        with self.assertRaises(RuntimeError):
            validate_playlist_content('#EXTINF:-1 tvg-id="one"\\nhttps://example.test/one/master.m3u8\\n')

    def test_duplicate_channel_id_is_rejected(self):
        content = (
            "#EXTM3U\\n"
            '#EXTINF:-1 tvg-id="same",Uno\\nhttps://example.test/one/master.m3u8\\n'
            '#EXTINF:-1 tvg-id="same",Dos\\nhttps://example.test/two/master.m3u8\\n'
        )
        with self.assertRaisesRegex(RuntimeError, "ID duplicado"):
            validate_playlist_content(content)

    def test_duplicate_stream_is_rejected(self):
        content = (
            "#EXTM3U\\n"
            '#EXTINF:-1 tvg-id="one",Uno\\nhttps://example.test/shared/master.m3u8\\n'
            '#EXTINF:-1 tvg-id="two",Dos\\nhttps://example.test/shared/master.m3u8\\n'
        )
        with self.assertRaisesRegex(RuntimeError, "stream duplicado"):
            validate_playlist_content(content)

    def test_url_without_extinf_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "sin #EXTINF"):
            validate_playlist_content("#EXTM3U\\nhttps://example.test/orphan/master.m3u8\\n")

    def test_non_hls_stream_is_rejected(self):
        content = '#EXTM3U\\n#EXTINF:-1 tvg-id="one",Uno\\nhttps://example.test/one/video.mp4\\n'
        with self.assertRaisesRegex(RuntimeError, "stream HLS inválido"):
            validate_playlist_content(content)

    def test_existing_order_is_kept_and_new_channels_are_appended(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            playlist = Path(temporary_directory) / "previous.m3u"
            playlist.write_text(
                "#EXTM3U\\n"
                '#EXTINF:-1 tvg-id="channel-b" tvg-name="Canal B",Canal B\\n'
                "https://example.test/b/master.m3u8\\n"
                '#EXTINF:-1 tvg-id="channel-a" tvg-name="Canal A",Canal A\\n'
                "https://example.test/a/master.m3u8\\n",
                encoding="utf-8",
            )
            fresh = [
                {"id": "channel-new", "name": "Nuevo", "stream": "https://example.test/new/master.m3u8"},
                {"id": "channel-a", "name": "Canal A actualizado", "stream": "https://example.test/a2/master.m3u8"},
                {"id": "channel-b", "name": "Canal B", "stream": "https://example.test/b2/master.m3u8"},
            ]
            ordered = preserve_previous_order(playlist, fresh)
            self.assertEqual([channel["id"] for channel in ordered], ["channel-b", "channel-a", "channel-new"])

    def test_rotated_id_keeps_its_slot_when_name_is_unique(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            playlist = Path(temporary_directory) / "previous.m3u"
            playlist.write_text(
                "#EXTM3U\\n"
                '#EXTINF:-1 tvg-id="old-id" tvg-name="Canal Uno",Canal Uno\\n'
                "https://example.test/one/master.m3u8\\n",
                encoding="utf-8",
            )
            fresh = [
                {"id": "new-id", "name": "Canal Uno", "stream": "https://example.test/one-new/master.m3u8"},
                {"id": "new-channel", "name": "Canal Nuevo", "stream": "https://example.test/new/master.m3u8"},
            ]
            ordered = preserve_previous_order(playlist, fresh)
            self.assertEqual([channel["id"] for channel in ordered], ["new-id", "new-channel"])


if __name__ == "__main__":
    unittest.main()

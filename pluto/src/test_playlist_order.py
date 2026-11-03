from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from generate_multiregion import preserve_previous_channels, preserve_previous_order, validate_playlist_content


class PlaylistOrderTests(unittest.TestCase):
    def test_valid_playlist_passes_validation(self):
        content = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="one" tvg-name="Uno",Uno\n'
            "https://example.test/one/master.m3u8\n"
            '#EXTINF:-1 tvg-id="two" tvg-name="Dos",Dos\n'
            "https://example.test/two/master.m3u8\n"
        )
        self.assertEqual(validate_playlist_content(content), 2)

    def test_empty_or_missing_header_is_rejected(self):
        with self.assertRaises(RuntimeError):
            validate_playlist_content("")
        with self.assertRaises(RuntimeError):
            validate_playlist_content('#EXTINF:-1 tvg-id="one"\nhttps://example.test/one/master.m3u8\n')

    def test_duplicate_channel_id_is_rejected(self):
        content = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="same",Uno\nhttps://example.test/one/master.m3u8\n'
            '#EXTINF:-1 tvg-id="same",Dos\nhttps://example.test/two/master.m3u8\n'
        )
        with self.assertRaisesRegex(RuntimeError, "ID duplicado"):
            validate_playlist_content(content)

    def test_duplicate_stream_is_rejected(self):
        content = (
            "#EXTM3U\n"
            '#EXTINF:-1 tvg-id="one",Uno\nhttps://example.test/shared/master.m3u8\n'
            '#EXTINF:-1 tvg-id="two",Dos\nhttps://example.test/shared/master.m3u8\n'
        )
        with self.assertRaisesRegex(RuntimeError, "stream duplicado"):
            validate_playlist_content(content)

    def test_url_without_extinf_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "sin #EXTINF"):
            validate_playlist_content("#EXTM3U\nhttps://example.test/orphan/master.m3u8\n")

    def test_non_hls_stream_is_rejected(self):
        content = '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://example.test/one/video.mp4\n'
        with self.assertRaisesRegex(RuntimeError, "stream HLS inválido"):
            validate_playlist_content(content)

    def test_invalid_url_hosts_and_fake_m3u8_suffix_are_rejected(self):
        for url in (
            "https:///missing-host/master.m3u8",
            "https://user:pass@example.test/master.m3u8",
            "https://example.test/video.mp4?format=.m3u8",
            "javascript://example.test/master.m3u8",
        ):
            with self.subTest(url=url):
                content = f'#EXTM3U\n#EXTINF:-1 tvg-id="bad",Bad\n{url}\n'
                with self.assertRaisesRegex(RuntimeError, "stream HLS inválido"):
                    validate_playlist_content(content)

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
            self.assertEqual([channel["id"] for channel in ordered], ["channel-b", "channel-a", "channel-new"])

    def test_missing_channel_is_removed_after_three_complete_catalogs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            playlist = Path(temporary_directory) / "pluto_cl.m3u"
            old_channels = [{
                "id": "old",
                "name": "Anterior",
                "stream": "https://example.test/old/master.m3u8",
                "consecutive_absences": 0,
            }]
            fresh = []
            for index in range(4):
                channel = {
                    "id": f"stay-{index}",
                    "name": f"Permanece {index}",
                    "stream": f"https://example.test/stay-{index}/master.m3u8",
                    "consecutive_absences": 0,
                }
                old_channels.append(dict(channel))
                fresh.append(dict(channel))
            playlist_lines = ["#EXTM3U"]
            for channel in old_channels:
                playlist_lines.extend([
                    f'#EXTINF:-1 tvg-id="{channel["id"]}" tvg-name="{channel["name"]}",{channel["name"]}',
                    channel["stream"],
                ])
            playlist.write_text("\n".join(playlist_lines) + "\n", encoding="utf-8")
            state = old_channels

            first, preserved = preserve_previous_channels(playlist, [dict(x) for x in fresh], previous_state=state)
            self.assertEqual(preserved, 1)
            self.assertEqual(next(x for x in first if x["id"] == "old")["consecutive_absences"], 1)

            second, preserved = preserve_previous_channels(playlist, [dict(x) for x in fresh], previous_state=first)
            self.assertEqual(preserved, 1)
            self.assertEqual(next(x for x in second if x["id"] == "old")["consecutive_absences"], 2)

            third, preserved = preserve_previous_channels(playlist, [dict(x) for x in fresh], previous_state=second)
            self.assertEqual(preserved, 0)
            self.assertEqual([x["id"] for x in third], ["stay"])

    def test_partial_catalog_does_not_advance_absence_counter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            playlist = Path(temporary_directory) / "pluto_cl.m3u"
            entries = []
            for index in range(10):
                entries.extend([
                    f'#EXTINF:-1 tvg-id="id-{index}" tvg-name="Canal {index}",Canal {index}',
                    f"https://example.test/{index}/master.m3u8",
                ])
            playlist.write_text("#EXTM3U\n" + "\n".join(entries) + "\n", encoding="utf-8")
            state = [
                {"id": f"id-{index}", "name": f"Canal {index}", "stream": f"https://example.test/{index}/master.m3u8", "consecutive_absences": 2}
                for index in range(10)
            ]
            fresh = [{"id": "id-0", "name": "Canal 0", "stream": "https://example.test/0/master.m3u8"}]
            result, preserved = preserve_previous_channels(playlist, fresh, previous_state=state)
            self.assertEqual(preserved, 9)
            self.assertEqual(next(x for x in result if x["id"] == "id-1")["consecutive_absences"], 2)

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
            self.assertEqual([channel["id"] for channel in ordered], ["new-id", "new-channel"])


if __name__ == "__main__":
    unittest.main()

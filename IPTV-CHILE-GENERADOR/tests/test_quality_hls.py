from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quality


class HlsVodValidationTests(unittest.TestCase):
    def setUp(self):
        # MPEG-TS con bytes de sincronización en los límites de paquete.
        self.valid_ts = bytearray(564)
        self.valid_ts[0] = self.valid_ts[188] = self.valid_ts[376] = 0x47

    def test_short_finished_vod_is_accepted_after_every_segment_is_checked(self):
        playlist = "#EXTM3U\n#EXTINF:6,\nseg1.ts\n#EXTINF:6,\nseg2.ts\n#EXT-X-ENDLIST\n"
        def segment(url):
            return 200, "video/mp2t", bytes(self.valid_ts), url
        with patch.object(quality, "fetch_segment", side_effect=segment) as fetch:
            ok, count, error = quality.validate_hls_segments(playlist, "https://example.test/vod/index.m3u8")
        self.assertTrue(ok, error)
        self.assertEqual(count, 2)
        self.assertEqual(fetch.call_count, 2)

    def test_live_playlist_still_requires_stability_window(self):
        playlist = "#EXTM3U\n#EXTINF:6,\nseg1.ts\n#EXTINF:6,\nseg2.ts\n"
        with patch.object(quality, "fetch_segment") as fetch:
            ok, count, error = quality.validate_hls_segments(playlist, "https://example.test/live/index.m3u8")
        self.assertFalse(ok)
        self.assertEqual(count, 2)
        self.assertIn("se requieren 3", error)
        fetch.assert_not_called()

    def test_short_finished_vod_fails_if_its_segment_is_invalid(self):
        playlist = "#EXTM3U\n#EXTINF:6,\nerror.ts\n#EXT-X-ENDLIST\n"
        with patch.object(quality, "fetch_segment", return_value=(200, "text/html", b"<html>error</html>", "https://example.test/error.ts")):
            ok, count, error = quality.validate_hls_segments(playlist, "https://example.test/vod/index.m3u8")
        self.assertFalse(ok)
        self.assertEqual(count, 0)
        self.assertIn("inválido", error)


if __name__ == "__main__":
    unittest.main()

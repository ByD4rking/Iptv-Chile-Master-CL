from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quality



class EndpointFailureClassificationTests(unittest.TestCase):
    def test_http_404_and_410_are_confirmed_not_found_candidates(self):
        channel = {"id": "test-channel", "name": "Canal de prueba"}
        for code in (404, 410):
            with self.subTest(code=code):
                error = HTTPError(
                    "https://example.test/live.m3u8",
                    code,
                    "not found",
                    {},
                    BytesIO(b""),
                )
                with patch.object(quality, "fetch", side_effect=error):
                    result = quality.inspect_url({
                        "channel": channel,
                        "source": {
                            "url": "https://example.test/live.m3u8",
                            "source": "TEST",
                            "priority": 1,
                        },
                    })
                self.assertEqual(result["failure_class"], "not_found_candidate")
                self.assertTrue(result["failure_confirmed"])
                self.assertFalse(result["playback_checked"])

    def test_http_403_remains_transient(self):
        error = HTTPError(
            "https://example.test/live.m3u8",
            403,
            "forbidden",
            {},
            BytesIO(b""),
        )
        with patch.object(quality, "fetch", side_effect=error):
            result = quality.inspect_url({
                "channel": {"id": "test-channel", "name": "Canal de prueba"},
                "source": {
                    "url": "https://example.test/live.m3u8",
                    "source": "TEST",
                    "priority": 1,
                },
            })
        self.assertEqual(result["failure_class"], "transient")
        self.assertFalse(result["failure_confirmed"])


class QuarantineReportingTests(unittest.TestCase):
    def test_quarantined_endpoint_is_reported_without_counting_a_new_failure(self):
        result = quality.quarantined_result(
            {"id": "channel-1", "name": "Canal pausado"},
            {"url": "https://example.test/live.m3u8", "source": "TEST", "priority": 10},
            {
                "quarantine_until": "2026-11-25T00:00:00+00:00",
                "checks": 12,
                "successes": 2,
                "failures": 10,
                "consecutive_failures": 10,
            },
        )
        self.assertEqual(result["failure_class"], "quarantined")
        self.assertFalse(result["failure_confirmed"])
        self.assertTrue(result["quarantined"])
        self.assertFalse(result["playback_checked"])
        self.assertEqual(result["endpoint_checks"], 12)
        self.assertEqual(result["endpoint_failures"], 10)


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

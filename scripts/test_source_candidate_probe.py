import unittest
from unittest.mock import patch
from scripts.source_candidate_probe import _first_uri, probe_stream


class SourceCandidateProbeTests(unittest.TestCase):
    def test_first_uri_skips_hls_tags(self):
        self.assertEqual(
            _first_uri(["#EXT-X-VERSION:3", "", "#EXTINF:6,", "segment001.ts"]),
            "segment001.ts",
        )

    @patch("scripts.source_candidate_probe._fetch")
    def test_validates_hls_manifest_and_first_segment(self, fetch):
        fetch.side_effect = [
            (200, "application/vnd.apple.mpegurl", "https://cdn.example/live/index.m3u8",
             b"#EXTM3U\n#EXTINF:6,\nseg001.ts\n#EXT-X-ENDLIST\n"),
            (200, "video/mp2t", "https://cdn.example/live/seg001.ts", b"\x47" * 188),
        ]
        result = probe_stream("https://cdn.example/live/index.m3u8")
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "segment_or_direct_media_sampled")

    @patch("scripts.source_candidate_probe._safe_open")
    @patch("scripts.source_candidate_probe._is_public_host", return_value=True)
    def test_caps_direct_video_to_a_sample_instead_of_marking_it_too_large(self, _public, opener):
        class Response:
            status = 200
            headers = {"Content-Type": "video/mp2t"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size=-1): return b"X" * size
            def geturl(self): return "https://cdn.example/live.ts"
        opener.return_value = Response()
        from scripts.source_candidate_probe import _fetch, SEGMENT_SAMPLE
        _, _, _, body = _fetch("https://cdn.example/live.ts", 256 * 1024)
        self.assertEqual(len(body), SEGMENT_SAMPLE)

    @patch("scripts.source_candidate_probe._fetch")
    def test_rejects_html_error_page_with_http_200(self, fetch):
        fetch.return_value = (200, "text/html", "https://cdn.example/live.m3u8", b"<html>denied</html>")
        result = probe_stream("https://cdn.example/live.m3u8")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "html_error_page")


if __name__ == "__main__":
    unittest.main(verbosity=2)

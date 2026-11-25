import unittest
from unittest.mock import patch
from scripts.channel_identity import parse_playlist_text
from scripts.logo_asset_check import collect_candidate_urls, inspect_asset


class FakeResponse:
    status = 200
    def __init__(self, body, content_type="image/png"):
        self.body = body
        self.headers = {"Content-Type": content_type}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size=-1): return self.body[:size]


class LogoAssetCheckTests(unittest.TestCase):
    @patch("scripts.logo_asset_check._is_public_host", return_value=True)
    def test_accepts_png_magic_and_image_content_type(self, _):
        body = b"\x89PNG\r\n\x1a\n" + b"x" * 16
        result = inspect_asset("https://img.example/logo.png", lambda *a, **k: FakeResponse(body))
        self.assertEqual(result["status"], "valid_png")
        self.assertNotIn("url", result)

    def test_rejects_conflicting_logo_urls_across_sources(self):
        current = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Canal Uno\nhttps://stream.example/live\n'
        )
        source_a = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/a.png",Canal Uno\nhttps://a.example/live\n'
        )
        source_b = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/b.png",Canal Uno\nhttps://b.example/live\n'
        )
        self.assertEqual(collect_candidate_urls(current, [("A", source_a), ("B", source_b)]), {})

    @patch("scripts.logo_asset_check._is_public_host", return_value=True)
    def test_rejects_html_disguised_as_image(self, _):
        result = inspect_asset("https://img.example/logo.png", lambda *a, **k: FakeResponse(b"<html>no</html>"))
        self.assertEqual(result["status"], "not_an_image")

    @patch("scripts.logo_asset_check._is_public_host", return_value=False)
    def test_blocks_non_public_hosts(self, _):
        result = inspect_asset("http://127.0.0.1/logo.png")
        self.assertEqual(result["status"], "blocked_non_public_host")


if __name__ == "__main__":
    unittest.main(verbosity=2)

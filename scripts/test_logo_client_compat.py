import unittest

from scripts.channel_identity import parse_playlist_text
from scripts.logo_client_compat import audit_logo_compatibility


class LogoClientCompatibilityTests(unittest.TestCase):
    def test_https_png_is_candidate_not_certified(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/logo.png",Uno\n'
            'https://stream.example/live\n'
        )
        result = audit_logo_compatibility(records)
        self.assertEqual(result["unique_logo_references"], 1)
        self.assertEqual(result["references"][0]["format"], "png")
        self.assertEqual(result["references"][0]["status"], "candidate")
        self.assertIn("no certifica renderizado", result["client_validation"])

    def test_svg_and_unknown_extensions_are_review_warnings(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-logo="https://img.example/logo.svg",SVG\nhttps://s.example/a\n'
            '#EXTINF:-1 tvg-logo="https://img.example/logo",Unknown\nhttps://s.example/b\n'
        )
        result = audit_logo_compatibility(records)
        warnings = [set(item["warnings"]) for item in result["references"]]
        self.assertTrue(any("svg_requires_client_validation" in item for item in warnings))
        self.assertTrue(any("unknown_image_format" in item for item in warnings))

    def test_invalid_scheme_and_embedded_credentials_are_flagged(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-logo="file:///tmp/logo.png",Local\nhttps://s.example/a\n'
            '#EXTINF:-1 tvg-logo="https://user:pass@img.example/logo.png",Cred\nhttps://s.example/b\n'
        )
        result = audit_logo_compatibility(records)
        self.assertEqual(result["invalid_references"], 2)
        self.assertNotIn("pass", repr(result))

    def test_missing_logo_and_field_conflicts_are_reported_without_replacement(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Missing\nhttps://s.example/a\n'
            '#EXTINF:-1 tvg-id="two" tvg-logo="https://img.example/a.png" logo="https://img.example/b.png",Conflict\n'
            'https://s.example/b\n'
        )
        result = audit_logo_compatibility(records)
        self.assertEqual(len(result["missing_logo_channels"]), 1)
        self.assertEqual(len(result["field_conflicts"]), 1)
        self.assertEqual(result["channels"], 2)
        self.assertIn("no descarga", result["policy"])

    def test_http_and_duplicate_references_are_diagnosed(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-logo="http://img.example/logo.jpg",Uno\nhttps://s.example/a\n'
            '#EXTINF:-1 tvg-logo="http://img.example/logo.jpg",Dos\nhttps://s.example/b\n'
        )
        result = audit_logo_compatibility(records)
        self.assertEqual(result["unique_logo_references"], 1)
        self.assertEqual(result["references"][0]["channels"], ["Dos", "Uno"])
        self.assertIn("insecure_http", result["references"][0]["warnings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

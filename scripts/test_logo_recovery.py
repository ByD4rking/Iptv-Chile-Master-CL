import unittest

from scripts.channel_identity import parse_playlist_text
from scripts.logo_recovery import propose_missing_logos


class MissingLogoRecoveryTests(unittest.TestCase):
    def test_missing_logo_gets_unique_strong_candidate(self):
        channel_id = "5ff4b9ccf938f8000779eb99"
        current = parse_playlist_text(
            f'#EXTM3U\\n#EXTINF:-1 tvg-id="{channel_id}" group-title="Anime",One Piece\\n'
            'https://stream.example/live\\n'
        )
        source = parse_playlist_text(
            f'#EXTM3U\\n#EXTINF:-1 tvg-id="{channel_id}" group-title="Anime" '
            f'tvg-logo="https://img.example/one-piece.png",One Piece\\n'
            'https://source.example/live\\n'
        )
        result = propose_missing_logos(current, [("REFERENCE", source)])
        self.assertEqual(result["missing_logo_channels"], 1)
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["confidence"], "strong")
        self.assertEqual(result["proposals"][0]["format"], "png")
        self.assertNotIn("https://img.example/one-piece.png", repr(result))

    def test_existing_logo_is_never_proposed_or_changed(self):
        current = parse_playlist_text(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/existing.png",Uno\\n'
            'https://stream.example/live\\n'
        )
        source = parse_playlist_text(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/replacement.png",Uno\\n'
            'https://source.example/live\\n'
        )
        before = current[0]["tvg_logo"]
        result = propose_missing_logos(current, [("REFERENCE", source)])
        self.assertEqual(result["missing_logo_channels"], 0)
        self.assertEqual(result["proposals"], [])
        self.assertEqual(current[0]["tvg_logo"], before)

    def test_conflicting_candidate_logos_are_not_proposed(self):
        current = parse_playlist_text(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="one" group-title="News",Uno\\n'
            'https://stream.example/live\\n'
        )
        source = parse_playlist_text(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="one" group-title="News" tvg-logo="https://img.example/a.png",Uno\\n'
            'https://source.example/a\\n'
            '#EXTINF:-1 tvg-id="one" group-title="News" tvg-logo="https://img.example/b.png",Uno\\n'
            'https://source.example/b\\n'
        )
        result = propose_missing_logos(current, [("REFERENCE", source)])
        self.assertEqual(result["proposals"], [])
        self.assertEqual(len(result["ambiguous"]), 1)

    def test_svg_and_unknown_formats_are_not_proposed_for_ss_iptv_compatibility(self):
        current = parse_playlist_text(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="one",Uno\\nhttps://stream.example/live\\n'
        )
        source = parse_playlist_text(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/logo.svg",Uno\\n'
            'https://source.example/live\\n'
        )
        result = propose_missing_logos(current, [("REFERENCE", source)])
        self.assertEqual(result["proposals"], [])
        self.assertEqual(len(result["unmatched"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

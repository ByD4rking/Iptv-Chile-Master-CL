import tempfile
import unittest
from pathlib import Path

from scripts.channel_identity import parse_playlist_text
from scripts.playlist_regression import audit_files, evaluate_regressions


def records(text):
    return parse_playlist_text(text)


class PlaylistRegressionTests(unittest.TestCase):
    def test_blocks_unexpected_channel_removal_by_default(self):
        before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/one\n'
            '#EXTINF:-1 tvg-id="two",Dos\nhttps://a.example/two\n'
        )
        after = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/one\n'
        )
        result = evaluate_regressions(before, after)
        self.assertFalse(result["passed"])
        self.assertEqual(result["violations"][0]["rule"], "unexpected_removals")

    def test_allows_expected_removal_only_when_explicitly_permitted(self):
        before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/one\n'
            '#EXTINF:-1 tvg-id="two",Dos\nhttps://a.example/two\n'
        )
        after = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/one\n'
        )
        result = evaluate_regressions(before, after, max_removed=1)
        self.assertTrue(result["passed"])

    def test_blocks_category_reassignment(self):
        before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" group-title="Anime",Uno\nhttps://a.example/one\n'
        )
        after = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" group-title="Deportes",Uno\nhttps://a.example/one\n'
        )
        result = evaluate_regressions(before, after)
        self.assertFalse(result["passed"])
        self.assertEqual(result["category_changes"], 1)

    def test_allows_only_the_exactly_reviewed_category_change(self):
        before = records(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="ptv" group-title="Entretenimiento / Cine / Series",PTV OnLine\\n'
            'https://a.example/ptv\\n'
        )
        after = records(
            '#EXTM3U\\n#EXTINF:-1 tvg-id="ptv" group-title="Bolivia",PTV OnLine\\n'
            'https://a.example/ptv\\n'
        )
        allowed = {("PTV OnLine", "Entretenimiento / Cine / Series", "Bolivia")}
        result = evaluate_regressions(before, after, allowed_category_changes=allowed)
        self.assertTrue(result["passed"])
        self.assertEqual(result["category_changes"], 1)
        self.assertEqual(len(result["approved_category_changes"]), 1)
        self.assertEqual(result["unapproved_category_changes"], [])

        rejected = evaluate_regressions(
            before, after,
            allowed_category_changes={("PTV OnLine", "Anime", "Bolivia")},
        )
        self.assertFalse(rejected["passed"])
        self.assertEqual(len(rejected["unapproved_category_changes"]), 1)

    def test_blocks_replacement_of_existing_logo_but_allows_missing_logo_fill(self):
        before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/old.png",Uno\n'
            'https://a.example/one\n'
        )
        replaced = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/new.png",Uno\n'
            'https://a.example/one\n'
        )
        filled = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one" tvg-logo="https://img.example/new.png",Uno\n'
            'https://a.example/one\n'
        )
        self.assertFalse(evaluate_regressions(before, replaced)["passed"])
        missing_before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/one\n'
        )
        self.assertTrue(evaluate_regressions(missing_before, filled)["passed"])

    def test_token_renewal_is_not_a_stream_regression(self):
        before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\n'
            'https://a.example/one.m3u8?jwt=old\n'
        )
        after = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\n'
            'https://a.example/one.m3u8?jwt=new\n'
        )
        result = evaluate_regressions(before, after, fail_on_stream_change=True)
        self.assertTrue(result["passed"])
        self.assertEqual(result["stream_changes"], 0)

    def test_real_stream_change_is_reported_and_can_be_blocked(self):
        before = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/old\n'
        )
        after = records(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\nhttps://a.example/new\n'
        )
        result = evaluate_regressions(before, after, fail_on_stream_change=True)
        self.assertFalse(result["passed"])
        self.assertEqual(result["stream_changes"], 1)

    def test_audit_files_rejects_invalid_m3u(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "before.m3u"
            after = Path(tmp) / "after.m3u"
            before.write_text("#EXTM3U\n#EXTINF:-1,Uno\nhttps://a.example/one\n")
            after.write_text("<html>403</html>")
            with self.assertRaises(ValueError):
                audit_files(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)

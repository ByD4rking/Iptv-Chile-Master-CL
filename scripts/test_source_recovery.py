import unittest

from scripts.channel_identity import parse_playlist_text, safe_url_fingerprint
from scripts.source_recovery import suggest_recoveries


def parse(text):
    return parse_playlist_text(text)


class SourceRecoveryTests(unittest.TestCase):
    def test_suggests_unique_strong_identity_alternative_for_persistently_failed_channel(self):
        current_url = "https://bad.example/vod/channel/0123456789abcdef01234567/master.m3u8"
        candidate_url = "https://good.example/vod/channel/0123456789abcdef01234567/master.m3u8"
        current = parse(
            '#EXTM3U\n#EXTINF:-1 tvg-id="epg.one",Canal Uno\n' + current_url + '\n'
        )
        candidates = parse(
            '#EXTM3U\n#EXTINF:-1 tvg-id="changed.epg",Nuevo nombre\n' + candidate_url + '\n'
        )
        health = {current_url: {"ok": False, "consecutive_failures": 4, "state": "SUSPECT"}}
        result = suggest_recoveries(current, [("IPTVSV", candidates)], health)
        self.assertEqual(result["channels_needing_recovery"], 1)
        self.assertEqual(result["channels_with_candidates"], 1)
        self.assertEqual(result["recommendations"][0]["candidates"][0]["confidence"], "strong")
        self.assertNotIn(candidate_url, repr(result))

    def test_does_not_suggest_when_failure_is_below_threshold_or_recovered(self):
        url = "https://bad.example/live"
        current = parse('#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\n' + url + '\n')
        health = {url: {"ok": False, "consecutive_failures": 2}}
        self.assertEqual(
            suggest_recoveries(current, [], health)["channels_needing_recovery"], 0
        )
        health[url] = {"ok": True, "consecutive_failures": 0}
        self.assertEqual(
            suggest_recoveries(current, [], health)["channels_needing_recovery"], 0
        )

    def test_ambiguous_candidate_aliases_are_not_recommended(self):
        current_url = "https://bad.example/live"
        current = parse(
            '#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\n' + current_url + '\n'
        )
        candidates = parse(
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="one",Uno A\nhttps://good.example/a\n'
            '#EXTINF:-1 tvg-id="one",Uno B\nhttps://good.example/b\n'
        )
        result = suggest_recoveries(
            current, [("MAGMA", candidates)],
            {current_url: {"ok": False, "consecutive_failures": 5}},
        )
        self.assertEqual(result["channels_with_candidates"], 0)
        self.assertEqual(result["recommendations"][0]["action"], "no_verified_alternative")

    def test_fallback_requires_unique_name_and_group_without_strong_ids(self):
        current_url = "https://bad.example/live"
        current = parse(
            '#EXTM3U\n#EXTINF:-1 group-title="Chile",Canal Uno\n' + current_url + '\n'
        )
        candidates = parse(
            '#EXTM3U\n#EXTINF:-1 group-title="Chile",Canal Uno\nhttps://good.example/live\n'
        )
        result = suggest_recoveries(
            current, [("FuenteB", candidates)],
            {current_url: {"ok": False, "consecutive_failures": 3}},
        )
        self.assertEqual(result["recommendations"][0]["candidates"][0]["confidence"], "fallback")

    def test_no_recommendation_if_candidate_is_same_stream(self):
        url = "https://same.example/live"
        current = parse('#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\n' + url + '\n')
        candidates = parse('#EXTM3U\n#EXTINF:-1 tvg-id="one",Uno\n' + url + '\n')
        result = suggest_recoveries(
            current, [("Same", candidates)],
            {url: {"ok": False, "consecutive_failures": 5}},
        )
        self.assertEqual(result["channels_with_candidates"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

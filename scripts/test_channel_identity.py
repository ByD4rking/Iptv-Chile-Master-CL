import unittest

from scripts.channel_identity import (
    compare_snapshots,
    parse_playlist_text,
    safe_url_fingerprint,
    url_provider_alias,
)


class ChannelIdentityTests(unittest.TestCase):
    def test_explicit_tvg_id_survives_name_group_and_url_changes(self):
        before = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="canal.uno" group-title="Chile",Canal Uno\n'
            'https://old.example/live.m3u8\n'
        )
        after = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="CANAL.UNO" group-title="Noticias",Nuevo Nombre\n'
            'https://new.example/live.m3u8\n'
        )
        result = compare_snapshots(before, after)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["renamed_or_moved"], 1)
        self.assertEqual(result["stream_changes"], 1)
        self.assertEqual(result["changes"][0]["confidence"], "strong")

    def test_provider_channel_id_matches_when_tvg_id_changes(self):
        url = "https://cdn.example/vod/channel/0123456789abcdef01234567/master.m3u8"
        old = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="old.epg",Canal\n' + url + '?jwt=old\n'
        )
        new = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="new.epg",Canal renombrado\n' + url + '?jwt=new\n'
        )
        result = compare_snapshots(old, new)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["stream_changes"], 0)
        self.assertTrue(url_provider_alias(url).startswith("provider-channel:"))

    def test_token_rotation_does_not_look_like_stream_change(self):
        a = "https://cdn.example/live.m3u8?jwt=first&country=CL"
        b = "https://cdn.example/live.m3u8?jwt=second&country=CL"
        self.assertEqual(safe_url_fingerprint(a), safe_url_fingerprint(b))

    def test_real_path_change_is_detected(self):
        before = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="id1",Canal\nhttps://cdn.example/a.m3u8\n'
        )
        after = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="id1",Canal\nhttps://cdn.example/b.m3u8\n'
        )
        self.assertEqual(compare_snapshots(before, after)["stream_changes"], 1)

    def test_fallback_requires_unique_name_and_group(self):
        before = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1,Canal\nhttps://a.example/live\n'
        )
        after = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1,Canal\nhttps://b.example/live\n'
        )
        result = compare_snapshots(before, after)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["changes"][0]["confidence"], "fallback")
        self.assertEqual(result["stream_changes"], 1)

    def test_duplicate_strong_aliases_are_not_guessed(self):
        source = (
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="duplicate",Canal A\nhttps://a.example/live\n'
            '#EXTINF:-1 tvg-id="duplicate",Canal B\nhttps://b.example/live\n'
        )
        result = compare_snapshots(parse_playlist_text(source), parse_playlist_text(source))
        self.assertEqual(result["matched"], 0)
        self.assertEqual(len(result["ambiguous"]), 4)
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["added"], 2)

    def test_conflicting_aliases_are_not_allowed_to_cross_match(self):
        before = parse_playlist_text(
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="one",Uno\nhttps://cdn.example/vod/channel/aaaaaaaaaaaaaaaa/master.m3u8\n'
            '#EXTINF:-1 tvg-id="two",Dos\nhttps://cdn.example/vod/channel/bbbbbbbbbbbbbbbb/master.m3u8\n'
        )
        after = parse_playlist_text(
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="two",Uno\nhttps://cdn.example/vod/channel/aaaaaaaaaaaaaaaa/master.m3u8\n'
            '#EXTINF:-1 tvg-id="one",Dos\nhttps://cdn.example/vod/channel/bbbbbbbbbbbbbbbb/master.m3u8\n'
        )
        result = compare_snapshots(before, after)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["added"], 2)
        self.assertEqual(len(result["ambiguous"]), 4)

    def test_category_prevents_unsafe_name_only_match(self):
        before = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 group-title="Anime",Canal\nhttps://a.example/live\n'
        )
        after = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 group-title="Deportes",Canal\nhttps://b.example/live\n'
        )
        result = compare_snapshots(before, after)
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["added"], 1)

    def test_missing_uri_does_not_borrow_next_channel_stream(self):
        records = parse_playlist_text(
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="missing",Canal sin URL\n'
            '#EXTINF:-1 tvg-id="valid",Canal válido\nhttps://valid.example/live\n'
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["stream_fingerprint"], "")
        self.assertNotEqual(records[1]["stream_fingerprint"], "")

    def test_placeholder_channel_ids_are_not_identity_aliases(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 channelId="-1",Canal A\nhttps://a.example/live\n'
            '#EXTINF:-1 channelId="-1",Canal B\nhttps://b.example/live\n'
        )
        self.assertEqual(records[0]["channel_id"], "")
        self.assertEqual(records[1]["channel_id"], "")
        result = compare_snapshots(records, records)
        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["added"], 0)

    def test_duplicate_tvg_ids_match_distinct_explicit_option_variants(self):
        source = (
            '#EXTM3U\n'
            '#EXTINF:-1 tvg-id="pluto.one" tvg-name="One Piece",One Piece\n'
            'https://a.example/live\n'
            '#EXTINF:-1 tvg-id="pluto.one" tvg-name="One Piece",One Piece [Opción 2]\n'
            'https://b.example/live\n'
        )
        result = compare_snapshots(parse_playlist_text(source), parse_playlist_text(source))
        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["ambiguous"], [])

    def test_option_variant_survives_base_display_name_change(self):
        before = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="same" tvg-name="Canal",Canal [Opción 2]\n'
            'https://old.example/live\n'
        )
        after = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="same" tvg-name="Canal",Canal renovado (OPCIÓN 2)\n'
            'https://new.example/live\n'
        )
        result = compare_snapshots(before, after)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["added"], 0)
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["stream_changes"], 1)

    def test_report_never_contains_raw_token(self):
        records = parse_playlist_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="safe",Canal\n'
            'https://cdn.example/live.m3u8?jwt=secret-value\n'
        )
        self.assertNotIn("secret-value", repr(records))


if __name__ == "__main__":
    unittest.main(verbosity=2)

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("auditar_fuentes.py")
SPEC = importlib.util.spec_from_file_location("auditar_fuentes", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuditSourceTests(unittest.TestCase):
    def test_parse_m3u_extracts_channel_identity_name_stream_and_group(self):
        text = '#EXTM3U\n#EXTINF:-1 tvg-id="canal.1" tvg-name="Canal Uno" group-title="Chile",Canal Uno HD\nhttps://a.example/one.m3u8\n'
        result = MODULE.parse_m3u(text)
        self.assertEqual(result["canal.1"], ["Canal Uno", "https://a.example/one.m3u8", "Chile"])

    def test_diff_detects_added_removed_renamed_and_stream_url(self):
        old = {
            "url": "https://old.example/list.m3u",
            "sha256": "old",
            "channel_count": 2,
            "channels": {
                "one": ["Canal Uno", "https://a/1", "Chile"],
                "two": ["Canal Dos", "https://a/2", "Chile"],
            },
        }
        new = {
            "url": "https://new.example/list.m3u",
            "sha256": "new",
            "channel_count": 2,
            "channels": {
                "one": ["Canal 1", "https://b/1", "Chile"],
                "three": ["Canal Tres", "https://a/3", "Anime"],
            },
        }
        result = MODULE.diff_source("FUENTE", old, new)
        self.assertTrue(result["source_url_changed"])
        self.assertEqual(result["added_channels"], 1)
        self.assertEqual(result["removed_channels"], 1)
        self.assertEqual(result["renamed_channels"], 1)
        self.assertEqual(result["changed_stream_urls"], 1)

    def test_duplicate_channel_ids_are_not_silently_overwritten(self):
        text = '#EXTM3U\n#EXTINF:-1 tvg-id="x",Uno\nhttps://a/1\n#EXTINF:-1 tvg-id="x",Dos\nhttps://a/2\n'
        self.assertEqual(len(MODULE.parse_m3u(text)), 2)

    def test_snapshot_never_persists_raw_stream_urls(self):
        raw = b'#EXTM3U\\n#EXTINF:-1 tvg-id="x",Canal X\\nhttps://signed.example/stream.m3u8?token=secret\\n'
        snapshot = MODULE.snapshot_entry(raw, "TEST", "https://source.example/list.m3u")
        serialized = str(snapshot)
        self.assertNotIn("signed.example", serialized)
        self.assertNotIn("secret", serialized)

    def test_source_url_must_be_http_or_https(self):
        with self.assertRaises(ValueError):
            MODULE.fetch_url("file:///etc/passwd")


if __name__ == "__main__":
    unittest.main()

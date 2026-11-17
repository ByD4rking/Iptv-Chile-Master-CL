import importlib.util
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
        raw = b'#EXTM3U\n#EXTINF:-1 tvg-id="x",Canal X\nhttps://signed.example/stream.m3u8?token=secret\n'
        snapshot = MODULE.snapshot_entry(raw, "TEST", "https://source.example/list.m3u")
        serialized = str(snapshot)
        self.assertNotIn("signed.example", serialized)
        self.assertNotIn("secret", serialized)

    def test_source_url_must_be_http_or_https(self):
        with self.assertRaises(ValueError):
            MODULE.fetch_url("file:///etc/passwd")



    def test_category_change_keeps_same_identity(self):
        old_text = '#EXTM3U\n#EXTINF:-1 tvg-id="canal.x" group-title="Series",Canal X\nhttps://a/x\n'
        new_text = '#EXTM3U\n#EXTINF:-1 tvg-id="canal.x" group-title="Cine",Canal X\nhttps://a/x\n'
        old = MODULE.snapshot_entry(old_text.encode(), "SRC", "https://src/list.m3u")
        new = MODULE.snapshot_entry(new_text.encode(), "SRC", "https://src/list.m3u")
        diff = MODULE.diff_source("SRC", old, new)
        self.assertEqual(diff["added_channels"], 0)
        self.assertEqual(diff["removed_channels"], 0)
        self.assertEqual(diff["changed_categories"], 1)

    def test_name_fallback_identity_does_not_depend_on_category(self):
        before = MODULE.parse_m3u('#EXTM3U\n#EXTINF:-1 group-title="Series",Canal X\nhttps://a/x\n')
        after = MODULE.parse_m3u('#EXTM3U\n#EXTINF:-1 group-title="Cine",Canal X\nhttps://b/x\n')
        self.assertEqual(set(before), set(after))
        self.assertEqual(before["canal x"][2], "Series")
        self.assertEqual(after["canal x"][2], "Cine")


    def test_principal_audits_all_25_unique_m3u_sources(self):
        sources = MODULE.configured_sources("principal")
        principal_sources = [item for item in sources if item["name"].startswith("PRINCIPAL/")]
        urls = {item["url"] for item in principal_sources}
        self.assertEqual(len(urls), 25)
        self.assertIn("PRINCIPAL/SPECIAL-PLUTO_MX_ALTERNATIVES", {item["name"] for item in principal_sources})
        self.assertIn("PRINCIPAL/SPECIAL-FEAR_FACTOR", {item["name"] for item in principal_sources})
        self.assertTrue(any(item["name"].startswith("GOD/") and item["readonly"] for item in sources))


    def test_rename_without_tvg_id_is_detected_when_stream_url_is_stable(self):
        old_text = '#EXTM3U\n#EXTINF:-1 group-title="Series",Nombre Antiguo\nhttps://a/stream.m3u8\n'
        new_text = '#EXTM3U\n#EXTINF:-1 group-title="Cine",Nombre Nuevo\nhttps://a/stream.m3u8\n'
        old = MODULE.snapshot_entry(old_text.encode(), "SRC", "https://src/list.m3u")
        new = MODULE.snapshot_entry(new_text.encode(), "SRC", "https://src/list.m3u")
        diff = MODULE.diff_source("SRC", old, new)
        self.assertEqual(diff["added_channels"], 0)
        self.assertEqual(diff["removed_channels"], 0)
        self.assertEqual(diff["renamed_channels"], 1)
        self.assertEqual(diff["changed_categories"], 1)

if __name__ == "__main__":
    unittest.main()

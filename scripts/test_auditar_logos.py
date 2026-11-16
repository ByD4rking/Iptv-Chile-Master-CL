import unittest
from scripts.auditar_logos import audit, parse_playlist

class LogoAuditTests(unittest.TestCase):
    def test_parse_and_deduplicate_logo_urls(self):
        text = '\n'.join([
            '#EXTM3U',
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/a.png",Canal A',
            'https://stream.test/a.m3u8',
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/a.png",Canal A Opción 2',
            'https://stream.test/b.m3u8',
            '#EXTINF:-1 group-title="Música" tvg-logo="",Canal B',
            'https://stream.test/c.m3u8',
        ])
        rows = parse_playlist(text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["group"], "Anime")
        self.assertEqual(rows[2]["logo"], "")

    def test_audit_does_not_modify_and_reports_statuses(self):
        text = '\n'.join([
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/good.png",Bueno',
            'https://stream.test/good.m3u8',
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/bad.png",Malo',
            'https://stream.test/bad.m3u8',
            '#EXTINF:-1 group-title="Música" tvg-logo="",Sin logo',
            'https://stream.test/none.m3u8',
        ])
        before = text
        def fake(url):
            return {"status": "ok" if url.endswith("good.png") else "broken", "detail": "test"}
        result = audit(text, checker=fake)
        self.assertEqual(result["channels"], 3)
        self.assertEqual(result["unique_logo_urls"], 2)
        self.assertEqual(result["logo_urls"]["ok"], 1)
        self.assertEqual(result["logo_urls"]["broken"], 1)
        self.assertEqual(len(result["missing_logo_entries"]), 1)
        self.assertEqual(text, before)

if __name__ == "__main__":
    unittest.main()

import unittest

from calidad_magma_cine import (
    audit_and_filter_channels,
    remove_rejected_cinema_blocks,
)


def channel(name, category, url):
    return {
        "nombre": name,
        "categoria": category,
        "url": url,
        "extinf": f'#EXTINF:-1 group-title="{category}",{name}',
    }


class CalidadMagmaCineTests(unittest.TestCase):
    def test_only_verified_1080p_16_9_cinema_is_allowed(self):
        good = channel("Cine Acción", "Cine / Películas", "https://a/good.m3u8")
        low = channel("Cine Romance", "Cine / Películas", "https://a/low.m3u8")
        anamorphic = channel("Cine Marvel", "Cine / Películas", "https://a/anamorphic.m3u8")
        series = channel("Breaking Bad", "Entretenimiento / Cine / Series", "https://a/series.m3u8")
        outcomes = {
            "https://a/good.m3u8": {"status": "accept", "resolution": "1920x1080", "field_order": "progressive"},
            "https://a/low.m3u8": {"status": "reject", "reason": "resolucion-distinta-de-1920x1080"},
            "https://a/anamorphic.m3u8": {"status": "reject", "reason": "aspect-ratio-distinto-de-16:9"},
        }
        allowed, rejected, unverified = audit_and_filter_channels(
            [good, low, anamorphic, series],
            probe=lambda url: outcomes[url],
        )
        self.assertEqual(allowed, [good, series])
        self.assertEqual([item["channel"] for item in rejected], [low, anamorphic])
        self.assertEqual(unverified, [])

    def test_unverified_stream_is_not_deleted_or_accepted(self):
        unknown = channel("Cine 2026", "Cine / Películas", "https://a/unknown.m3u8")
        allowed, rejected, unverified = audit_and_filter_channels(
            [unknown],
            probe=lambda url: {"status": "unknown", "reason": "error-de-red"},
        )
        self.assertEqual(allowed, [])
        self.assertEqual(rejected, [])
        self.assertEqual(unverified[0]["channel"], unknown)

    def test_non_cinema_channels_do_not_need_1080p_probe(self):
        series = channel("Friends", "Entretenimiento / Cine / Series", "https://a/friends.m3u8")
        allowed, rejected, unverified = audit_and_filter_channels(
            [series],
            probe=lambda url: self.fail("No debe sondear series"),
        )
        self.assertEqual(allowed, [series])
        self.assertEqual(rejected, [])
        self.assertEqual(unverified, [])

    def test_remove_only_rejected_cinema_urls(self):
        lines = [
            "#EXTM3U",
            '#EXTINF:-1 group-title="Cine / Películas",Cine SD',
            "#EXTVLCOPT:http-user-agent=test",
            "https://a/sd.m3u8",
            '#EXTINF:-1 group-title="Cine / Películas",Cine HD',
            "https://a/hd.m3u8",
            '#EXTINF:-1 group-title="Entretenimiento / Cine / Series",Serie',
            "https://a/serie.m3u8",
        ]
        output = remove_rejected_cinema_blocks(lines, {"https://a/sd.m3u8"})
        self.assertNotIn("https://a/sd.m3u8", output)
        self.assertIn("https://a/hd.m3u8", output)
        self.assertIn("https://a/serie.m3u8", output)
        self.assertEqual(sum(line.startswith("#EXTINF") for line in output), 2)

    def test_no_rejected_urls_keeps_every_line(self):
        lines = ["#EXTM3U", '#EXTINF:-1 group-title="Cine / Películas",Cine', "https://a/movie.m3u8"]
        self.assertEqual(remove_rejected_cinema_blocks(lines, set()), lines)


if __name__ == "__main__":
    unittest.main()

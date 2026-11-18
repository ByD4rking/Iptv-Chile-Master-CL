import unittest

from scripts.blindajes_principal import priorizar_history_documentales


def bloque(nombre, categoria="Documentales y Cultura"):
    return [
        f'#EXTINF:-1 tvg-name="{nombre}" group-title="{categoria}",{nombre}',
        f"https://example.com/{nombre.lower().replace(' ', '-')}.m3u8",
    ]


class DocumentalesHistoryOrderTests(unittest.TestCase):
    def test_history_family_then_history2_family_preserving_each_order(self):
        lines = ["#EXTM3U"]
        lines += bloque("E! Entertainment")
        lines += bloque("History (720p)")
        lines += bloque("Discovery Channel")
        lines += bloque("History 2 (720p)")
        lines += bloque("History (1080p)")
        lines += bloque("Nat Geo")
        lines += bloque("History 2 (1080p)")
        result = priorizar_history_documentales(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "History (720p)",
            "History (1080p)",
            "History 2 (720p)",
            "History 2 (1080p)",
            "E! Entertainment",
            "Discovery Channel",
            "Nat Geo",
        ])

    def test_other_categories_are_untouched(self):
        lines = ["#EXTM3U"] + bloque("History (720p)", "CHILE TV") + bloque("History 2", "Anime")
        self.assertEqual(priorizar_history_documentales(lines), lines)


if __name__ == "__main__":
    unittest.main()

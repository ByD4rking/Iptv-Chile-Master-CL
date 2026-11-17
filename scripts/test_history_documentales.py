import unittest

from scripts.blindajes_principal import (
    LOGOS_AUTORIZADOS_POR_NOMBRE,
    priorizar_history_documentales,
)


def bloque(nombre, categoria="Documentales y Cultura"):
    return [
        f'#EXTINF:-1 tvg-name="{nombre}" group-title="{categoria}",{nombre}',
        f"https://example.com/{nombre.lower().replace(' ', '-')}.m3u8",
    ]


class DocumentalesHistoryOrderTests(unittest.TestCase):
    def test_history_history2_second_history_are_first_in_category(self):
        lines = ["#EXTM3U"]
        lines += bloque("E! Entertainment")
        lines += bloque("History (720p)")
        lines += bloque("Discovery Channel")
        lines += bloque("History 2 (720p)")
        lines += bloque("History (1080p)")
        lines += bloque("Nat Geo")
        result = priorizar_history_documentales(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "History (720p)",
            "History 2 (720p)",
            "History (1080p)",
            "E! Entertainment",
            "Discovery Channel",
            "Nat Geo",
        ])

    def test_both_chile_tv_signals_use_the_existing_tvn_logo(self):
        tvn_logo = "https://i.imgur.com/3FKZHL4.png"
        self.assertEqual(LOGOS_AUTORIZADOS_POR_NOMBRE["TVN HD (LOCAL)"], tvn_logo)
        self.assertEqual(LOGOS_AUTORIZADOS_POR_NOMBRE["TV Chile (1080p) [Geo-blocked]"], tvn_logo)


if __name__ == "__main__":
    unittest.main()

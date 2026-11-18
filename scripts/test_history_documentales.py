import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.blindajes_principal import priorizar_history_documentales
from alimentar_principal import validar_orden_canales


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

    def test_channel_order_validator_allows_only_history_priority(self):
        original = ["#EXTM3U"]
        original += bloque("E! Entertainment")
        original += bloque("History Channel HD")
        original += bloque("Discovery Channel")
        original += bloque("History 2 Latin America (1080p)")
        original += bloque("Nat Geo")
        reordered = priorizar_history_documentales(original)
        validar_orden_canales(original, reordered)

    def test_channel_order_validator_still_rejects_other_reordering(self):
        original = ["#EXTM3U"]
        original += bloque("E! Entertainment")
        original += bloque("History Channel HD")
        original += bloque("Discovery Channel")
        original += bloque("History 2 Latin America (1080p)")
        original += bloque("Nat Geo")
        reordered = priorizar_history_documentales(original)
        # Alterar el orden relativo de dos canales ajenos a History debe fallar.
        extinf_positions = [i for i, line in enumerate(reordered) if line.startswith("#EXTINF")]
        blocks = []
        for i in extinf_positions:
            end = next((j for j in extinf_positions if j > i), len(reordered))
            blocks.append(reordered[i:end])
        blocks[2], blocks[3] = blocks[3], blocks[2]
        invalid = ["#EXTM3U"] + [line for block in blocks for line in block]
        with self.assertRaisesRegex(RuntimeError, "ORDEN BLOQUEADO"):
            validar_orden_canales(original, invalid)

    def test_other_categories_are_untouched(self):
        lines = ["#EXTM3U"] + bloque("History (720p)", "CHILE TV") + bloque("History 2", "Anime")
        self.assertEqual(priorizar_history_documentales(lines), lines)


if __name__ == "__main__":
    unittest.main()

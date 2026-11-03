import unittest
import alimentar_principal as ap


def block(channel_id, category, name, url):
    return [
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" tvg-logo="https://logo.example/{channel_id}.png" group-title="{category}",{name}',
        url,
    ]


class TestAlternativasPrincipal(unittest.TestCase):
    def entries(self, lines):
        result = []
        i = 0
        while i < len(lines):
            if lines[i].startswith("#EXTINF"):
                j = i + 1
                while j < len(lines) and not lines[j].startswith("#EXTINF"):
                    j += 1
                result.append(lines[i:j])
                i = j
            else:
                i += 1
        return result

    def test_cygtvcl_alternatives_become_adjacent_and_numbered(self):
        lines = ["#EXTM3U"] + block("cygtvcl.id", "CHILE TV", "CYGTVCL", "https://a.example/live.m3u8")
        lines += block("cygtvcl.id", "CHILE TV", "CYGTVCL", "https://other.example/live.m3u8")
        lines += block("other.id", "CHILE TV", "Canal distinto", "https://other.example/other.m3u8")
        output = ap.agrupar_alternativas_por_identidad(lines)
        parsed = self.entries(output)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertEqual(names[:2], ["CYGTVCL", "CYGTVCL [Opción 2]"])
        self.assertEqual(parsed[0][-1], "https://a.example/live.m3u8")
        self.assertEqual(parsed[1][-1], "https://other.example/live.m3u8")

    def test_reference_rules_move_kids_remove_only_es_smurfs_and_fix_delmi(self):
        lines = ["#EXTM3U"]
        lines += block("popeye.id", "Retro", "Popeye", "https://kids.example/popeye.m3u8")
        lines += block("pitufos.latam", "Infantiles", "Los Pitufos", "https://kids.example/pitufos.m3u8")
        lines += block("pitufos.es", "Infantiles", "Los Pitufos [Pluto ES]", "https://stitcher.example/pitufos.m3u8?country=ES")
        lines += block("heidi.id", "Infantiles", "Heidi", "https://kids.example/heidi.m3u8")
        lines += block("delmi.v2", "Entretenimiento", "Delmi TV [V2]", "https://anime.example/delmi.m3u8")
        lines += block("comp.id", "Competencia", "Competencia prueba", "https://sports.example/live.m3u8")
        output = ap.aplicar_ajustes_referencia(lines, set())
        parsed = self.entries(output)
        kids = [item for item in parsed if 'group-title="Infantiles"' in item[0]]
        self.assertEqual([item[0].split(",", 1)[1] for item in kids[:3]],
                         ["Popeye", "Los Pitufos", "Heidi"])
        self.assertFalse(any("Los Pitufos [Pluto ES]" in item[0] for item in parsed))
        self.assertTrue(any('group-title="Anime"' in item[0] and item[0].endswith(",Delmi TV 2") for item in parsed))

    def test_cartoonito_option_four_is_kept_and_rejoined(self):
        lines = ["#EXTM3U"]
        lines += block("cartoonito.id", "Infantiles", "Cartoonito HD", "https://a.example/cartoonito.m3u8")
        lines += block("other.id", "Infantiles", "Otro canal", "https://other.example/live.m3u8")
        lines += block("cartoonito.id", "Infantiles", "Cartoonito HD [Opc.4]", "https://four.example/cartoonito.m3u8")
        output = ap.agrupar_alternativas_por_identidad(lines)
        parsed = self.entries(output)
        cartoonito = [item for item in parsed if "cartoonito" in item[0].lower()]
        self.assertEqual(len(cartoonito), 2)
        self.assertEqual([item[0].split(",", 1)[1] for item in cartoonito],
                         ["Cartoonito HD", "Cartoonito HD [Opción 2]"])
        self.assertEqual(cartoonito[1][-1], "https://four.example/cartoonito.m3u8")


if __name__ == "__main__":
    unittest.main()

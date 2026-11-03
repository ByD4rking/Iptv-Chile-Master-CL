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

import unittest

import alimentar_principal as ap


def bloque(nombre, categoria="Entretenimiento / Cine / Series", url=None):
    url = url or "https://example.com/" + str(abs(hash(nombre)))
    return [
        f'#EXTINF:-1 tvg-name="{nombre}" group-title="{categoria}",{nombre}',
        url,
    ]


class FamilyGroupingTests(unittest.TestCase):
    def test_groups_related_channels_without_reordering_families(self):
        lines = ["#EXTM3U"]
        lines += bloque("Los Simpson Latino")
        lines += bloque("Telemundo Internacional")
        lines += bloque("El Chavo TV")
        lines += bloque("Telemundo 51")
        lines += bloque("Los Simpson Latino HD")
        lines += bloque("Chespirito TV")
        lines += bloque("Comedy Central")
        lines += bloque("Comedy Central HD")
        result = ap.agrupar_familias_por_categoria(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "Los Simpson Latino",
            "Los Simpson Latino HD",
            "Telemundo Internacional",
            "Telemundo 51",
            "El Chavo TV",
            "Chespirito TV",
            "Comedy Central",
            "Comedy Central HD",
        ])

    def test_cnn_services_remain_separate_families(self):
        lines = ["#EXTM3U"]
        lines += bloque("CNN Chile")
        lines += bloque("CNN en Español")
        lines += bloque("CNN Headlines International")
        lines += bloque("CNN Chile HD")
        result = ap.agrupar_familias_por_categoria(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "CNN Chile", "CNN Chile HD", "CNN en Español",
            "CNN Headlines International",
        ])


if __name__ == "__main__":
    unittest.main()

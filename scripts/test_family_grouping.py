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

    def test_new_family_variant_is_inserted_after_existing_family(self):
        original = ["#EXTM3U"]
        original += bloque("CityTV SD", categoria="Entretenimiento Premium")
        original += bloque("DHE HD", categoria="Entretenimiento Premium")
        original += bloque("Caracol Internacional SD", categoria="Entretenimiento Premium")

        current = ["#EXTM3U"]
        current += bloque("Caracol HD2", categoria="Entretenimiento Premium")
        current += bloque("CityTV SD", categoria="Entretenimiento Premium")
        current += bloque("DHE HD", categoria="Entretenimiento Premium")
        current += bloque("Caracol Internacional SD", categoria="Entretenimiento Premium")

        result = ap.agrupar_familias_por_categoria(current, original)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "CityTV SD",
            "DHE HD",
            "Caracol Internacional SD",
            "Caracol HD2",
        ])

    def test_generic_channel_prefixes_do_not_merge_unrelated_services(self):
        lines = ["#EXTM3U"]
        lines += bloque("Canal Onza TV")
        lines += bloque("Canal Teleclásica México")
        lines += bloque("Canal Onza TV HD")
        result = ap.agrupar_familias_por_categoria(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "Canal Onza TV", "Canal Onza TV HD", "Canal Teleclásica México",
        ])

    def test_anime_franchises_are_grouped(self):
        lines = ["#EXTM3U"]
        lines += bloque("Naruto", categoria="Anime")
        lines += bloque("Dragon Ball Z", categoria="Anime")
        lines += bloque("Naruto Shippuden", categoria="Anime")
        lines += bloque("Dragon Ball Super", categoria="Anime")
        result = ap.agrupar_familias_por_categoria(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "Naruto", "Naruto Shippuden", "Dragon Ball Z", "Dragon Ball Super",
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

    def test_chavo_and_chespirito_are_distinct_families(self):
        lines = ["#EXTM3U"]
        lines += bloque("El Chavo TV")
        lines += bloque("Los Simpson Latino")
        lines += bloque("Chespirito TV")
        result = ap.agrupar_familias_por_categoria(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, ["El Chavo TV", "Los Simpson Latino", "Chespirito TV"])

    def test_tve_and_comedy_central_brand_variants_group(self):
        lines = ["#EXTM3U"]
        lines += bloque("TVE Internacional America")
        lines += bloque("Comedy Central")
        lines += bloque("TVE Internacional America HD")
        lines += bloque("Comedy Central en español")
        result = ap.agrupar_familias_por_categoria(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "TVE Internacional America", "TVE Internacional America HD",
            "Comedy Central", "Comedy Central en español",
        ])

    def test_unnamed_channels_are_not_collapsed_together(self):
        lines = ["#EXTM3U",
                 '#EXTINF:-1 group-title="Test",',
                 "https://example.com/one.m3u8",
                 '#EXTINF:-1 group-title="Test",',
                 "https://example.com/two.m3u8"]
        result = ap.agrupar_familias_por_categoria(lines)
        self.assertEqual(sum(line.startswith("#EXTINF") for line in result), 2)

    def test_logo_restoration_only_touches_authorized_channels(self):
        reference = [
            '#EXTINF:-1 tvg-name="Canal Permitido" tvg-logo="https://logos.example/permitido.png" group-title="Test",Canal Permitido',
            "https://streams.example/permitido.m3u8",
            '#EXTINF:-1 tvg-name="Canal Bloqueado" tvg-logo="https://logos.example/bloqueado.png" group-title="Test",Canal Bloqueado',
            "https://streams.example/bloqueado.m3u8",
        ]
        current = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-name="Canal Permitido" group-title="Test",Canal Permitido',
            "https://streams.example/permitido.m3u8",
            '#EXTINF:-1 tvg-name="Canal Bloqueado" group-title="Test",Canal Bloqueado',
            "https://streams.example/bloqueado.m3u8",
        ]
        result, _ = ap.restaurar_logos_historicos(
            current, reference, nombres_autorizados={"Canal Permitido"}
        )
        permitido = next(x for x in result if x.startswith("#EXTINF") and "Canal Permitido" in x)
        bloqueado = next(x for x in result if x.startswith("#EXTINF") and "Canal Bloqueado" in x)
        self.assertIn('tvg-logo="https://logos.example/permitido.png"', permitido)
        self.assertNotIn("tvg-logo=", bloqueado)

    def test_authorized_logo_override_updates_both_logo_attributes(self):
        current = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-name="TL+ (El Salvador)" tvg-logo="https://old.example/expired.png" logo="https://old.example/expired.png" group-title="Anime",TL+ (El Salvador)',
            "https://streams.example/tlplus.m3u8",
        ]
        correct = "https://kift.live/media/avatars/27ffc836-28d5-457b-9ebe-f65b0c2f5fb9/091fff8e-0e9e-46f9-b5ff-50cf24ce481b.png"
        result, _ = ap.restaurar_logos_historicos(
            current,
            [],
            nombres_autorizados={"TL+ (El Salvador)"},
            logos_autorizados_por_nombre={"TL+ (El Salvador)": correct},
        )
        entry = next(x for x in result if x.startswith("#EXTINF"))
        self.assertEqual(entry.count(correct), 2)
        self.assertNotIn("old.example", entry)

    def test_category_order_is_preserved(self):
        lines = ["#EXTM3U"]
        lines += bloque("Canal A", categoria="Primera")
        lines += bloque("Canal B", categoria="Primera")
        lines += bloque("Canal A HD", categoria="Primera")
        lines += bloque("Canal C", categoria="Segunda")
        result = ap.agrupar_familias_por_categoria(lines)
        cats = []
        for line in result:
            if line.startswith("#EXTINF"):
                cats.append(ap.normalizar(ap.extraer_categoria(line)))
        self.assertEqual(cats, ["primera", "primera", "primera", "segunda"])


if __name__ == "__main__":
    unittest.main()

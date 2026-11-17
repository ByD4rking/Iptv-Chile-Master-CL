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

    def test_intentionally_sorted_categories_keep_the_current_order(self):
        original = ["#EXTM3U"]
        original += bloque("Naruto", categoria="Anime")
        original += bloque("Dragon Ball Z", categoria="Anime")
        original += bloque("Retro TV", categoria="Entretenimiento / Cine / Series")
        original += bloque("Los Simpson Latino", categoria="Entretenimiento / Cine / Series")

        current = ["#EXTM3U"]
        current += bloque("Dragon Ball Z", categoria="Anime")
        current += bloque("Dragon Ball Super", categoria="Anime")
        current += bloque("Naruto", categoria="Anime")
        current += bloque("Los Simpson Latino", categoria="Entretenimiento / Cine / Series")
        current += bloque("Los Simpson Latino [Opción 2]", categoria="Entretenimiento / Cine / Series")
        current += bloque("Retro TV", categoria="Entretenimiento / Cine / Series")

        result = ap.agrupar_familias_por_categoria(current, original)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "Dragon Ball Z", "Dragon Ball Super", "Naruto",
            "Los Simpson Latino", "Los Simpson Latino [Opción 2]", "Retro TV",
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

    def test_new_option_is_inserted_after_existing_base(self):
        original = ["#EXTM3U"]
        original += bloque("Caracol Internacional SD", categoria="Entretenimiento Premium")
        original += bloque("CityTV SD", categoria="Entretenimiento Premium")

        current = ["#EXTM3U"]
        current += bloque("Caracol Internacional SD [Opción 2]", categoria="Entretenimiento Premium")
        current += bloque("CityTV SD", categoria="Entretenimiento Premium")
        current += bloque("Caracol Internacional SD", categoria="Entretenimiento Premium")

        result = ap.agrupar_familias_por_categoria(current, original)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "Caracol Internacional SD",
            "Caracol Internacional SD [Opción 2]",
            "CityTV SD",
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

    def test_anime_saga_order_places_boruto_before_naruto_movies(self):
        lines = ["#EXTM3U"]
        lines += bloque("Naruto (Peliculas)", categoria="Anime")
        lines += bloque("Boruto: Naruto Next Generations", categoria="Anime")
        lines += bloque("Naruto Shippuden", categoria="Anime")
        lines += bloque("Naruto", categoria="Anime")
        lines += bloque("Dragon Ball GT", categoria="Anime")
        lines += bloque("Dragon Ball Z", categoria="Anime")
        lines += bloque("Dragon Ball Super", categoria="Anime")
        result = ap.ordenar_anime_alfabeticamente(lines)
        names = [line.rsplit(",", 1)[-1] for line in result if line.startswith("#EXTINF")]
        self.assertEqual(names, [
            "Dragon Ball Z",
            "Dragon Ball Super",
            "Dragon Ball GT",
            "Naruto",
            "Naruto Shippuden",
            "Boruto: Naruto Next Generations",
            "Naruto (Peliculas)",
        ])

    def test_final_alternative_grouping_renumbers_in_playlist_order(self):
        def pitufos(nombre, numero):
            return [
                f'#EXTINF:-1 tvg-id="pluto.pitufos" tvg-name="Los Pitufos" group-title="Infantiles",{nombre}',
                f"https://example.com/pitufos-{numero}.m3u8",
            ]
        lines = ["#EXTM3U"]
        lines += pitufos("Los Pitufos", 1)
        lines += pitufos("Los Pitufos (OPCIÓN 3)", 3)
        lines += pitufos("Los Pitufos [Opción 2]", 2)
        result = ap.agrupar_alternativas_por_identidad(lines)
        entries = [line for line in result if line.startswith("#EXTINF")]
        names = [line.rsplit(",", 1)[-1] for line in entries]
        self.assertEqual(names, [
            "Los Pitufos",
            "Los Pitufos [Opción 2]",
            "Los Pitufos [Opción 3]",
        ])
        self.assertEqual(sum(1 for line in result if line.endswith(".m3u8")), 3)

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

    def test_logo_authorization_whitelist_contains_only_the_nine_requested_names(self):
        self.assertEqual(len(ap.NOMBRES_LOGOS_AUTORIZADOS_PRINCIPAL), 9)
        self.assertNotIn("Radio Rancagua FM (720p)", ap.NOMBRES_LOGOS_AUTORIZADOS_PRINCIPAL)
        self.assertNotIn("Radio Ritmo FM", ap.NOMBRES_LOGOS_AUTORIZADOS_PRINCIPAL)

    def test_logo_restoration_preserves_non_authorized_original_logos(self):
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
            current,
            reference,
            nombres_autorizados={"Canal Permitido"},
            logos_bloqueados_por_identidad=ap.extraer_logos_bloqueados_por_identidad(reference),
        )
        permitido = next(x for x in result if x.startswith("#EXTINF") and "Canal Permitido" in x)
        bloqueado = next(x for x in result if x.startswith("#EXTINF") and "Canal Bloqueado" in x)
        self.assertIn('tvg-logo="https://logos.example/permitido.png"', permitido)
        self.assertIn('tvg-logo="https://logos.example/bloqueado.png"', bloqueado)

    def test_non_authorized_logo_survives_stream_url_rotation_by_tvg_id(self):
        reference = [
            '#EXTINF:-1 tvg-id="babyfirst.us" tvg-name="BabyFirst SD" tvg-logo="https://images.pluto.tv/babyfirst.png" group-title="Infantiles",BabyFirst SD',
            "https://old.example/babyfirst.m3u8",
        ]
        current = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="babyfirst.us" tvg-name="BabyFirst SD" tvg-logo="https://1000logos.net/babyfirst.png" group-title="Infantiles",BabyFirst SD',
            "https://new.example/babyfirst.m3u8",
        ]
        result, stats = ap.restaurar_logos_historicos(
            current,
            reference,
            nombres_autorizados={"Canal Permitido"},
            logos_bloqueados_por_identidad=ap.extraer_logos_bloqueados_por_identidad(reference),
        )
        entry = next(x for x in result if x.startswith("#EXTINF"))
        self.assertIn('tvg-logo="https://images.pluto.tv/babyfirst.png"', entry)
        self.assertNotIn("1000logos.net", entry)
        self.assertEqual(stats["protegidos"], 1)

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

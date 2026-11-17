import unittest

import blindajes_principal as blindajes


def entry(category, name, url, channel_id="", logo="", legacy=""):
    attrs = []
    if channel_id:
        attrs.append(f'tvg-id="{channel_id}"')
    attrs.append(f'group-title="{category}"')
    if logo:
        attrs.append(f'tvg-logo="{logo}"')
    if legacy:
        attrs.append(f'logo="{legacy}"')
    return [f'#EXTINF:-1 {" ".join(attrs)},{name}', url]


class LogoSafeguardTests(unittest.TestCase):
    def test_stream_and_name_changes_keep_both_original_logo_attributes(self):
        old_logo = "https://logos.example/original.png"
        old_legacy = "https://logos.example/legacy.png"
        original = ["#EXTM3U"] + entry(
            "Deportes", "Canal Original", "https://old.example/live.m3u8",
            "canal.unico", old_logo, old_legacy,
        )
        current = ["#EXTM3U"] + entry(
            "Deportes", "Canal Renombrado", "https://new.example/live.m3u8",
            "canal.unico", "https://source.example/wrong.png",
            "https://source.example/wrong-legacy.png",
        )
        output, stats = blindajes.blindar_logos(current, original)
        extinf = next(line for line in output if line.startswith("#EXTINF"))
        self.assertIn(f'tvg-logo="{old_logo}"', extinf)
        self.assertIn(f'logo="{old_legacy}"', extinf)
        self.assertEqual(stats["logos_restaurados"], 1)

    def test_category_name_identity_keeps_logo_when_url_rotates(self):
        logo = "https://logos.example/channel.png"
        original = ["#EXTM3U"] + entry(
            "Documentales y Cultura", "Canal Cultura",
            "https://old.example/cultura.m3u8", logo=logo,
        )
        current = ["#EXTM3U"] + entry(
            "Documentales y Cultura", "Canal Cultura",
            "https://new.example/cultura.m3u8", logo="https://source.example/changed.png",
        )
        output, _ = blindajes.blindar_logos(current, original)
        self.assertIn(f'tvg-logo="{logo}"', next(x for x in output if x.startswith("#EXTINF")))

    def test_new_channel_does_not_inherit_source_logo(self):
        original = ["#EXTM3U"] + entry(
            "Deportes", "Canal Existente", "https://old.example/a.m3u8",
            "existente", "https://logos.example/existing.png",
        )
        current = original + entry(
            "Deportes", "Canal Nuevo", "https://new.example/b.m3u8",
            "nuevo", "https://source.example/automatic.png",
        )
        output, stats = blindajes.blindar_logos(current, original)
        new_extinf = next(x for x in output if x.startswith("#EXTINF") and x.endswith(",Canal Nuevo"))
        self.assertNotIn("tvg-logo=", new_extinf)
        self.assertEqual(stats["logos_fuente_retirados"], 1)

    def test_existing_channel_without_logo_stays_without_logo(self):
        original = ["#EXTM3U"] + entry(
            "Comedia", "Canal sin logo", "https://old.example/a.m3u8", "sin.logo",
        )
        current = ["#EXTM3U"] + entry(
            "Comedia", "Canal sin logo", "https://new.example/a.m3u8",
            "sin.logo", "https://source.example/automatic.png",
        )
        output, _ = blindajes.blindar_logos(current, original)
        extinf = next(x for x in output if x.startswith("#EXTINF"))
        self.assertNotIn("tvg-logo=", extinf)


class LockedAnimeTests(unittest.TestCase):
    def test_anime_is_restored_byte_for_byte_from_reference(self):
        original_anime = entry(
            "Anime", "Dragon Ball Z", "https://anime.example/original.m3u8",
            "anime.dbz", "https://logos.example/dbz.png",
        )
        original = ["#EXTM3U"] + original_anime + entry(
            "CHILE TV", "TVN", "https://chile.example/tvn.m3u8",
        )
        changed = ["#EXTM3U"] + entry(
            "Anime", "Dragon Ball Z HD", "https://anime.example/changed.m3u8",
            "anime.dbz", "https://logos.example/wrong.png",
        ) + entry("CHILE TV", "TVN", "https://chile.example/tvn.m3u8")
        output = blindajes.restaurar_categoria_bloqueada(changed, original, "Anime")
        anime_blocks = [
            block for block in blindajes._split_blocks(output)[1]
            if block["category_key"] == "anime"
        ]
        self.assertEqual(anime_blocks[0]["lines"], original_anime)


class GlobalCategoryOrderTests(unittest.TestCase):
    def test_fixed_categories_are_ordered_and_countries_remain_last(self):
        categories = [
            "Informativos", "Argentina 🇦🇷", "Anime", "CHILE TV", "Perú",
            "Competencia", "Infantiles", "Música", "Cine / Películas",
            "Entretenimiento / Cine / Series", "Bolivia",
        ]
        sample = ["#EXTM3U"]
        for category in categories:
            sample.extend(entry(category, f"Canal {category}", f"https://{len(sample)}.example/live.m3u8"))
        output = blindajes.ordenar_categorias_definitivo(sample)
        actual = [
            block["category"]
            for block in blindajes._split_blocks(output)[1]
        ]
        self.assertEqual(actual, [
            "CHILE TV", "Anime", "Competencia", "Infantiles",
            "Entretenimiento / Cine / Series", "Cine / Películas",
            "Informativos", "Música", "Argentina 🇦🇷", "Perú", "Bolivia",
        ])
        self.assertTrue(blindajes.validar_orden_categorias(output))

    def test_channel_order_inside_each_category_is_preserved(self):
        sample = ["#EXTM3U"]
        sample += entry("Series", "Serie B", "https://example.com/b.m3u8")
        sample += entry("CHILE TV", "TVN", "https://example.com/tvn.m3u8")
        sample += entry("Series", "Serie A", "https://example.com/a.m3u8")
        output = blindajes.ordenar_categorias_definitivo(sample)
        names = [
            block["name"] for block in blindajes._split_blocks(output)[1]
            if block["category_key"] == "series"
        ]
        self.assertEqual(names, ["serie b", "serie a"])


if __name__ == "__main__":
    unittest.main()

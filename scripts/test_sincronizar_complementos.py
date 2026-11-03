import unittest

import alimentar_principal as ap
from sincronizar_complementos import reconcile_lines


def entry(channel_id, category, name, url):
    return [
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" group-title="{category}",{name}',
        url,
    ]


def candidate(channel_id, category, name, url, source=None):
    source = source or ap.FUENTE_IPTVSV
    extinf = f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" group-title="{category}",{name}'
    return {
        "extinf": extinf,
        "extras": [],
        "url": url,
        "categoria": category,
        "nombre": name,
        "source": source,
        "is_pluto": False,
        "identity": "id:" + ap.normalizar(channel_id) if channel_id else "name:" + ap.normalizar(name),
    }


class ComplementSyncTests(unittest.TestCase):
    def setUp(self):
        self.base = ["#EXTM3U"] + entry("sports.one", "Deportes", "Canal Uno", "https://old.example/one.m3u8") + entry(
            "kids.two", "Infantiles", "Canal Kids", "https://keep.example/kids.m3u8"
        )

    def test_changed_url_updates_existing_channel(self):
        source = [candidate("sports.one", "Deportes", "Canal Uno", "https://new.example/one.m3u8")]
        output, stats = reconcile_lines(self.base, source)
        self.assertIn("https://new.example/one.m3u8", output)
        self.assertNotIn("https://old.example/one.m3u8", output)
        self.assertEqual(stats["url_actualizadas"], 1)

    def test_changed_category_moves_existing_channel(self):
        source = [candidate("sports.one", "Infantiles", "Canal Uno", "https://old.example/one.m3u8")]
        output, stats = reconcile_lines(self.base, source)
        index = output.index(next(line for line in output if line.startswith("#EXTINF") and 'tvg-id="sports.one"' in line))
        self.assertIn('group-title="Infantiles"', output[index])
        self.assertEqual(stats["categorias_movidas"], 1)

    def test_changed_tvg_id_can_match_by_unique_name(self):
        source = [candidate("sports.one.rotated", "Deportes", "Canal Uno", "https://new.example/one.m3u8")]
        output, stats = reconcile_lines(self.base, source)
        self.assertIn('tvg-id="sports.one.rotated"', output[1])
        self.assertIn("https://new.example/one.m3u8", output)
        self.assertNotIn("https://old.example/one.m3u8", output)
        self.assertEqual(stats["url_actualizadas"], 1)

    def test_all_alternatives_move_with_the_channel_category(self):
        base = ["#EXTM3U"] + entry("sports.one", "Deportes", "Canal Uno", "https://old.example/one.m3u8") + entry(
            "sports.one", "General", "Canal Uno", "https://alt.example/one.m3u8"
        ) + entry("kids.two", "Infantiles", "Canal Kids", "https://keep.example/kids.m3u8")
        source = [candidate("sports.one", "Infantiles", "Canal Uno", "https://new.example/one.m3u8")]
        output, stats = reconcile_lines(base, source)
        matching = [line for line in output if line.startswith("#EXTINF") and 'tvg-id="sports.one"' in line]
        self.assertEqual(len(matching), 2)
        self.assertTrue(all('group-title="Infantiles"' in line for line in matching))
        self.assertIn("https://new.example/one.m3u8", output)
        self.assertIn("https://alt.example/one.m3u8", output)
        self.assertEqual(stats["categorias_movidas"], 2)

    def test_new_channel_is_added(self):
        source = [candidate("new.kids", "Infantiles", "Nuevo Infantil", "https://new.example/kids.m3u8")]
        output, stats = reconcile_lines(self.base, source)
        self.assertTrue(any('tvg-id="new.kids"' in line for line in output))
        self.assertIn("https://new.example/kids.m3u8", output)
        self.assertEqual(stats["canales_nuevos"], 1)

    def test_missing_from_source_is_not_deleted(self):
        source = [candidate("sports.one", "Deportes", "Canal Uno", "https://new.example/one.m3u8")]
        output, _ = reconcile_lines(self.base, source)
        self.assertIn("https://keep.example/kids.m3u8", output)

    def test_existing_channel_uses_its_recorded_source_owner(self):
        manifest = {"id:sports.one": {"source": ap.FUENTE_MAGMA}}
        source = [
            candidate("sports.one", "Deportes", "Canal Uno", "https://iptvsv.example/live.m3u8", ap.FUENTE_IPTVSV),
            candidate("sports.one", "Deportes", "Canal Uno", "https://magma.example/live.m3u8", ap.FUENTE_MAGMA),
        ]
        output, stats = reconcile_lines(self.base, source, manifest)
        self.assertIn("https://magma.example/live.m3u8", output)
        self.assertNotIn("https://old.example/one.m3u8", output)
        self.assertEqual(manifest["id:sports.one"]["source"], ap.FUENTE_MAGMA)
        self.assertEqual(stats["url_actualizadas"], 1)

    def test_other_source_cannot_take_over_when_owner_is_temporarily_missing(self):
        manifest = {"id:sports.one": {"source": ap.FUENTE_MAGMA}}
        source = [
            candidate("sports.one", "Deportes", "Canal Uno", "https://iptvsv.example/live.m3u8", ap.FUENTE_IPTVSV),
        ]
        output, stats = reconcile_lines(self.base, source, manifest)
        self.assertIn("https://old.example/one.m3u8", output)
        self.assertNotIn("https://iptvsv.example/live.m3u8", output)
        self.assertEqual(stats["url_actualizadas"], 0)

    def test_ambiguous_name_does_not_overwrite(self):
        base = ["#EXTM3U"] + entry("id.a", "Deportes", "Canal Repetido", "https://a.example/live.m3u8") + entry(
            "id.b", "Deportes", "Canal Repetido", "https://b.example/live.m3u8"
        )
        source = [candidate("", "Infantiles", "Canal Repetido", "https://new.example/live.m3u8")]
        output, stats = reconcile_lines(base, source)
        self.assertIn("https://a.example/live.m3u8", output)
        self.assertIn("https://b.example/live.m3u8", output)
        self.assertNotIn("https://new.example/live.m3u8", output)
        self.assertEqual(stats["ambiguos"], 1)


if __name__ == "__main__":
    unittest.main()

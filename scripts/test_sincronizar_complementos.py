import unittest

import alimentar_principal as ap
from sincronizar_complementos import FUENTES_PLUTO_COMPLETAS, reconcile_lines


def entry(channel_id, category, name, url):
    return [
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" group-title="{category}",{name}',
        url,
    ]


def candidate(channel_id, category, name, url, source=None):
    source = source or ap.FUENTE_IPTVSV
    extinf = (
        f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" '
        f'group-title="{category}",{name}'
    )
    identity = (
        "id:" + ap.normalizar(channel_id)
        if channel_id
        else "name:" + ap.normalizar(name)
    )
    return {
        "extinf": extinf,
        "extras": [],
        "url": url,
        "categoria": category,
        "nombre": name,
        "source": source,
        "is_pluto": source in FUENTES_PLUTO_COMPLETAS,
        "identity": identity,
    }


class RestorationOrderTests(unittest.TestCase):
    def test_iptvsv_category_change_is_reclassified_instead_of_blocked(self):
        url = "http://45.5.118.152:8000/play/chichi.m3u8"
        current = ["#EXTM3U"] + entry(
            "chichi.id", "TV Chichicasteca", "Canal Chichicasteca", url
        )
        source = [{
            "url": url,
            "categoria": "TV Chichicasteca",
            "nombre": "Canal Chichicasteca",
        }]
        categories = ap.categorias_de_lineas(current)
        audit = ap.validar_integridad_iptvsv(current, source, categories)
        self.assertEqual(audit["categorias_pendientes_mover"], 1)

        moved, count, conflicts = ap.reclasificar_iptvsv_existente(
            current, source, categories
        )
        self.assertEqual(count, 1)
        self.assertEqual(conflicts, 0)
        self.assertTrue(any('group-title="Guatemala"' in line for line in moved))

    def test_do_not_restore_old_url_when_same_tvg_id_has_new_url(self):
        original = entry("music.id", "Música", "MTV Classic", "https://old.example/mtv.m3u8")
        current = ["#EXTM3U"] + entry("music.id", "Música", "MTV Classic", "https://new.example/mtv.m3u8")
        output, restored = ap.restaurar_no_pluto_existente(
            current,
            {"https://old.example/mtv.m3u8": original},
        )
        self.assertEqual(restored, 0)
        self.assertIn("https://new.example/mtv.m3u8", output)
        self.assertNotIn("https://old.example/mtv.m3u8", output)

    def test_restore_missing_channel_at_its_original_relative_position(self):
        first = entry("music.a", "Música", "Canal A", "https://a.example/a.m3u8")
        missing = entry("music.b", "Música", "Canal B", "https://b.example/b.m3u8")
        last = entry("music.c", "Música", "Canal C", "https://c.example/c.m3u8")
        current = ["#EXTM3U"] + first + last
        initial = {
            "https://a.example/a.m3u8": first,
            "https://b.example/b.m3u8": missing,
            "https://c.example/c.m3u8": last,
        }
        output, restored = ap.restaurar_no_pluto_existente(current, initial)
        self.assertEqual(restored, 1)
        self.assertEqual(
            ap.firma_orden_canales(output),
            ["id:music.a", "id:music.b", "id:music.c"],
        )


class ComplementSyncTests(unittest.TestCase):
    def setUp(self):
        self.base = (
            ["#EXTM3U"]
            + entry("sports.one", "Deportes", "Canal Uno", "https://old.example/one.m3u8")
            + entry("kids.two", "Infantiles", "Canal Kids", "https://keep.example/kids.m3u8")
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
        index = output.index(
            next(
                line for line in output
                if line.startswith("#EXTINF") and 'tvg-id="sports.one"' in line
            )
        )
        self.assertIn('group-title="Infantiles"', output[index])
        self.assertEqual(stats["categorias_movidas"], 1)

    def test_changed_tvg_id_can_match_by_unique_name(self):
        source = [
            candidate(
                "sports.one.rotated",
                "Deportes",
                "Canal Uno",
                "https://new.example/one.m3u8",
            )
        ]
        output, stats = reconcile_lines(self.base, source)
        self.assertIn('tvg-id="sports.one.rotated"', output[1])
        self.assertIn("https://new.example/one.m3u8", output)
        self.assertNotIn("https://old.example/one.m3u8", output)
        self.assertEqual(stats["url_actualizadas"], 1)

    def test_all_existing_alternatives_move_with_channel_category(self):
        base = (
            ["#EXTM3U"]
            + entry("sports.one", "Deportes", "Canal Uno", "https://old.example/one.m3u8")
            + entry("sports.one", "General", "Canal Uno", "https://alt.example/one.m3u8")
            + entry("kids.two", "Infantiles", "Canal Kids", "https://keep.example/kids.m3u8")
        )
        source = [
            candidate("sports.one", "Infantiles", "Canal Uno", "https://new.example/one.m3u8")
        ]
        output, stats = reconcile_lines(base, source)
        matching = [
            line for line in output
            if line.startswith("#EXTINF") and 'tvg-id="sports.one"' in line
        ]
        self.assertEqual(len(matching), 2)
        self.assertTrue(all('group-title="Infantiles"' in line for line in matching))
        self.assertIn("https://new.example/one.m3u8", output)
        self.assertIn("https://alt.example/one.m3u8", output)
        self.assertEqual(stats["categorias_movidas"], 2)

    def test_url_update_preserves_existing_option_label(self):
        base = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-id="cartoonito.id" tvg-name="Cartoonito HD" group-title="Infantiles",Cartoonito HD [Opc.4]',
            "https://old.example/cartoonito.m3u8",
        ]
        source = [
            candidate(
                "cartoonito.id",
                "Infantiles",
                "Cartoonito HD",
                "https://new.example/cartoonito.m3u8",
            )
        ]
        output, stats = reconcile_lines(base, source)
        extinf = next(line for line in output if 'tvg-id="cartoonito.id"' in line)
        self.assertTrue(extinf.endswith(",Cartoonito HD [Opc.4]"))
        self.assertIn("https://new.example/cartoonito.m3u8", output)
        self.assertNotIn("https://old.example/cartoonito.m3u8", output)
        self.assertEqual(stats["url_actualizadas"], 1)

    def test_new_channel_is_added(self):
        source = [
            candidate(
                "new.kids",
                "Infantiles",
                "Nuevo Infantil",
                "https://new.example/kids.m3u8",
            )
        ]
        output, stats = reconcile_lines(self.base, source)
        self.assertTrue(any('tvg-id="new.kids"' in line for line in output))
        self.assertIn("https://new.example/kids.m3u8", output)
        self.assertEqual(stats["canales_nuevos"], 1)

    def test_new_source_category_is_created(self):
        source = [
            candidate(
                "new.local",
                "Canales Locales",
                "Canal Local",
                "https://new.example/local.m3u8",
                ap.FUENTE_MAGMA,
            )
        ]
        output, stats = reconcile_lines(self.base, source)
        extinf = next(line for line in output if 'tvg-id="new.local"' in line)
        self.assertIn('group-title="Canales Locales"', extinf)
        self.assertEqual(stats["canales_nuevos"], 1)

    def test_missing_from_source_is_not_deleted(self):
        source = [
            candidate(
                "sports.one",
                "Deportes",
                "Canal Uno",
                "https://new.example/one.m3u8",
            )
        ]
        output, _ = reconcile_lines(self.base, source)
        self.assertIn("https://keep.example/kids.m3u8", output)

    def test_existing_channel_uses_its_recorded_source_owner(self):
        manifest = {"id:sports.one": {"source": ap.FUENTE_MAGMA}}
        source = [
            candidate(
                "sports.one",
                "Deportes",
                "Canal Uno",
                "https://iptvsv.example/live.m3u8",
                ap.FUENTE_IPTVSV,
            ),
            candidate(
                "sports.one",
                "Deportes",
                "Canal Uno",
                "https://magma.example/live.m3u8",
                ap.FUENTE_MAGMA,
            ),
        ]
        output, stats = reconcile_lines(self.base, source, manifest)
        self.assertIn("https://magma.example/live.m3u8", output)
        self.assertNotIn("https://old.example/one.m3u8", output)
        self.assertEqual(manifest["id:sports.one"]["source"], ap.FUENTE_MAGMA)
        self.assertEqual(stats["url_actualizadas"], 1)

    def test_other_source_cannot_take_over_when_owner_is_temporarily_missing(self):
        manifest = {"id:sports.one": {"source": ap.FUENTE_MAGMA}}
        source = [
            candidate(
                "sports.one",
                "Deportes",
                "Canal Uno",
                "https://iptvsv.example/live.m3u8",
                ap.FUENTE_IPTVSV,
            ),
        ]
        output, stats = reconcile_lines(self.base, source, manifest)
        self.assertIn("https://old.example/one.m3u8", output)
        self.assertNotIn("https://iptvsv.example/live.m3u8", output)
        self.assertEqual(stats["url_actualizadas"], 0)

    def test_ambiguous_name_does_not_overwrite(self):
        base = (
            ["#EXTM3U"]
            + entry("id.a", "Deportes", "Canal Repetido", "https://a.example/live.m3u8")
            + entry("id.b", "Deportes", "Canal Repetido", "https://b.example/live.m3u8")
        )
        source = [
            candidate(
                "",
                "Deportes",
                "Canal Repetido",
                "https://new.example/live.m3u8",
                ap.FUENTE_MAGMA,
            )
        ]
        output, stats = reconcile_lines(base, source)
        self.assertIn("https://a.example/live.m3u8", output)
        self.assertIn("https://b.example/live.m3u8", output)
        self.assertNotIn("https://new.example/live.m3u8", output)
        self.assertEqual(stats["sin_categoria"], 0)
        self.assertEqual(stats["ambiguos"], 1)

    def test_chichicasteca_channels_move_to_guatemala(self):
        base = (
            ["#EXTM3U"]
            + entry(
                "",
                "TV Chichicasteca",
                "CANAL 2 (TELEVISION CHICHICASTECA)",
                "http://45.5.118.152:8000/play/a06h/index.m3u8",
            )
            + entry("kids.two", "Infantiles", "Heidi", "https://keep.example/heidi.m3u8")
        )
        source = [
            candidate(
                "",
                "TV Chichicasteca",
                "CANAL 2 (TELEVISION CHICHICASTECA)",
                "http://45.5.118.152:8000/play/a06h/index.m3u8",
                ap.FUENTE_IPTVSV,
            )
        ]
        output, stats = reconcile_lines(base, source)
        extinf = next(line for line in output if "TELEVISION CHICHICASTECA" in line)
        self.assertIn('group-title="Guatemala"', extinf)
        self.assertFalse(any('group-title="TV Chichicasteca"' in line for line in output))
        self.assertIn("https://keep.example/heidi.m3u8", output)
        self.assertEqual(stats["canales_chichicasteca_a_guatemala"], 1)

    def test_only_los_pitufos_is_removed_and_heidi_remains(self):
        base = (
            ["#EXTM3U"]
            + entry("pitufos.id", "Infantiles", "Los Pitufos", "https://bad.example/pitufos.m3u8")
            + entry("pitufos.id", "Infantiles", "Los Pitufos [Pluto ES]", "https://bad.example/pitufos-es.m3u8")
            + entry("heidi.id", "Infantiles", "Heidi", "https://good.example/heidi.m3u8")
        )
        source = [
            candidate(
                "pitufos.id",
                "Infantil",
                "Los Pitufos",
                "https://new.example/pitufos.m3u8",
                ap.FUENTES_PLUTO[2],
            )
        ]
        output, stats = reconcile_lines(base, source)
        self.assertFalse(any("Los Pitufos" in line for line in output))
        self.assertIn("https://good.example/heidi.m3u8", output)
        self.assertEqual(stats["los_pitufos_eliminados"], 2)

    def test_pluto_es_anime_excluded_but_latam_and_mx_anime_are_added(self):
        base = (
            ["#EXTM3U"]
            + entry(
                "es.only",
                "Anime",
                "Anime solo España",
                "https://stitcher.pluto.tv/channel/es-only/master.m3u8",
            )
            + entry(
                "shared.anime",
                "Anime",
                "Anime compartido",
                "https://stitcher.pluto.tv/channel/shared/master.m3u8",
            )
        )
        source = [
            candidate(
                "es.only",
                "Anime",
                "Anime solo España",
                "https://stitcher.pluto.tv/channel/es-only-new/master.m3u8",
                ap.FUENTES_PLUTO[1],
            ),
            candidate(
                "shared.anime",
                "Anime",
                "Anime compartido",
                "https://stitcher.pluto.tv/channel/shared-es/master.m3u8",
                ap.FUENTES_PLUTO[1],
            ),
            candidate(
                "shared.anime",
                "Anime",
                "Anime compartido",
                "https://stitcher.pluto.tv/channel/shared-latam/master.m3u8",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                "mx.only",
                "Anime",
                "Anime México",
                "https://stitcher.pluto.tv/channel/mx-only/master.m3u8",
                ap.FUENTES_PLUTO[2],
            ),
        ]
        manifest = {"id:shared.anime": {"source": ap.FUENTES_PLUTO[1]}}
        output, stats = reconcile_lines(base, source, manifest)
        self.assertFalse(any('tvg-id="es.only"' in line for line in output))
        self.assertTrue(any('tvg-id="shared.anime"' in line for line in output))
        self.assertTrue(any('tvg-id="mx.only"' in line for line in output))
        self.assertEqual(manifest["id:shared.anime"]["source"], ap.FUENTES_PLUTO[0])
        self.assertEqual(stats["pluto_es_anime_eliminados"], 1)

    def test_existing_channel_order_is_preserved_and_new_channels_append(self):
        base = (
            ["#EXTM3U"]
            + entry("one", "Deportes", "Uno", "https://one.example/live.m3u8")
            + entry("two", "Infantiles", "Dos", "https://two.example/live.m3u8")
            + entry("three", "Deportes", "Tres", "https://three.example/live.m3u8")
        )
        source = [
            candidate("two", "Anime", "Dos", "https://two.example/live.m3u8"),
            candidate("four", "Deportes", "Cuatro", "https://four.example/live.m3u8"),
        ]
        output, _ = reconcile_lines(base, source)
        names = [
            line.split(",", 1)[1]
            for line in output
            if line.startswith("#EXTINF:")
        ]
        self.assertEqual(names, ["Uno", "Dos", "Tres", "Cuatro"])


if __name__ == "__main__":
    unittest.main()

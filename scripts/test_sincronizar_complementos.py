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
    url_id = ""
    if source in FUENTES_PLUTO_COMPLETAS:
        import re
        match = re.search(r"/(?:channel/|plu-)([a-f0-9]{20,})(?:/|\.m3u8)", url, re.I)
        url_id = match.group(1) if match else ""
    identity = (
        "id:" + ap.normalizar(url_id or channel_id)
        if (url_id or channel_id)
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


class OriginalPlaylistOrderTests(unittest.TestCase):
    def test_restore_category_and_channel_order_and_append_new_channels(self):
        original = ["#EXTM3U"] + (
            entry("cat1.a", "Categoría A", "Canal A", "https://a.example/a.m3u8")
            + entry("cat1.b", "Categoría A", "Canal B", "https://b.example/b.m3u8")
            + entry("cat2.c", "Categoría B", "Canal C", "https://c.example/c.m3u8")
        )
        current = ["#EXTM3U"] + (
            entry("cat2.new", "Categoría B", "Nuevo B", "https://new.example/b.m3u8")
            + entry("cat1.b", "Categoría A", "Canal B", "https://b.example/b.m3u8")
            + entry("cat2.c", "Categoría B", "Canal C", "https://c.example/c.m3u8")
            + entry("cat1.a", "Categoría A", "Canal A", "https://a.example/a.m3u8")
            + entry("cat1.new", "Categoría A", "Nuevo A", "https://new.example/a.m3u8")
        )
        output, stats = ap.restaurar_orden_original_por_categoria(current, original)
        extinfs = [line for line in output if line.startswith("#EXTINF")]
        categories = [ap.extraer_categoria(line) for line in extinfs]
        names = [ap.extraer_nombre(line) for line in extinfs]
        self.assertEqual(categories, ["Categoría A", "Categoría A", "Categoría A", "Categoría B", "Categoría B"])
        self.assertEqual(names, ["Canal A", "Canal B", "Nuevo A", "Canal C", "Nuevo B"])
        self.assertGreaterEqual(stats["bloques_reordenados"], 1)

    def test_moved_channel_appends_after_original_channels_in_destination(self):
        original = ["#EXTM3U"] + (
            entry("a.one", "País A", "Canal A", "https://a.example/a.m3u8")
            + entry("a.two", "País A", "Canal B", "https://b.example/b.m3u8")
            + entry("b.one", "País B", "Canal C", "https://c.example/c.m3u8")
        )
        current = ["#EXTM3U"] + (
            entry("a.one", "País A", "Canal A", "https://a.example/a.m3u8")
            + entry("a.new", "País B", "Nuevo B", "https://new.example/b.m3u8")
            + entry("a.two", "País B", "Canal B", "https://b.example/b.m3u8")
            + entry("b.one", "País B", "Canal C", "https://c.example/c.m3u8")
        )
        output, _ = ap.restaurar_orden_original_por_categoria(current, original)
        extinfs = [line for line in output if line.startswith("#EXTINF")]
        categories = [ap.extraer_categoria(line) for line in extinfs]
        names = [ap.extraer_nombre(line) for line in extinfs]
        self.assertEqual(categories, ["País A", "País B", "País B", "País B"])
        self.assertEqual(names, ["Canal A", "Canal C", "Canal B", "Nuevo B"])


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
            ["#EXTM3U"] + original,
        )
        self.assertEqual(restored, 0)
        self.assertIn("https://new.example/mtv.m3u8", output)
        self.assertNotIn("https://old.example/mtv.m3u8", output)

    def test_restore_missing_channel_at_its_original_relative_position(self):
        first = entry("music.a", "Música", "Canal A", "https://a.example/a.m3u8")
        missing = entry("music.b", "Música", "Canal B", "https://b.example/b.m3u8")
        last = entry("music.c", "Música", "Canal C", "https://c.example/c.m3u8")
        current = ["#EXTM3U"] + first + last
        initial = ["#EXTM3U"] + first + missing + last
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

    def test_principal_uses_external_mx_without_jwt(self):
        self.assertEqual(ap.FUENTES_PLUTO_PRINCIPAL, ap.FUENTES_PLUTO[:2])
        self.assertNotIn(ap.FUENTES_PLUTO[2], ap.FUENTES_PLUTO_PRINCIPAL)
        self.assertIn(ap.FUENTE_PLUTO_ALTERNATIVAS, FUENTES_PLUTO_COMPLETAS)
        self.assertNotIn(ap.FUENTES_PLUTO[2], FUENTES_PLUTO_COMPLETAS)
        self.assertEqual(ap.FUENTES_PLUTO_CATALOGO, ap.FUENTES_PLUTO_PRINCIPAL)

    def test_alimentador_removes_only_es_pitufos_and_reorders_kids(self):
        base = ["#EXTM3U"] + (
            entry(
                "yugioh.es",
                "Anime",
                "Yu-Gi-Oh! Español",
                "https://stitcher.pluto.tv/channel/yugioh-es/master.m3u8?country=ES&marketingRegion=ES",
            )
            + entry(
                "yugioh.latam",
                "Anime",
                "Yu-Gi-Oh",
                "https://stitcher.pluto.tv/channel/yugioh-latam/master.m3u8?country=MX&marketingRegion=MX",
            )
            + entry(
                "pitufos.es",
                "Infantiles",
                "Los Pitufos",
                "https://stitcher.pluto.tv/channel/pitufos-es/master.m3u8?country=ES&marketingRegion=ES",
            )
            + entry(
                "pitufos.latam",
                "Retro",
                "Los Pitufos",
                "https://stitcher.pluto.tv/channel/pitufos-latam/master.m3u8?country=MX&marketingRegion=MX",
            )
            + entry("popeye.id", "Retro", "Popeye", "https://stitcher.pluto.tv/channel/popeye/master.m3u8?country=MX")
            + entry("heidi.id", "Infantiles", "Heidi", "https://stitcher.pluto.tv/channel/heidi/master.m3u8?country=ES")
            + entry("other.id", "Infantiles", "Otro infantil", "https://kids.example/other.m3u8")
            + entry("competition.id", "Competencia", "Evento", "https://sports.example/event.m3u8")
        )
        output = ap.aplicar_ajustes_referencia(base, set())
        self.assertNotIn("yugioh-es", "\n".join(output))
        self.assertIn("https://stitcher.pluto.tv/channel/yugioh-latam/master.m3u8?country=MX&marketingRegion=MX", output)
        self.assertNotIn("pitufos-es", "\n".join(output))
        self.assertIn("https://stitcher.pluto.tv/channel/pitufos-latam/master.m3u8?country=MX&marketingRegion=MX", output)
        infant_names = [
            ap.normalizar(ap.extraer_nombre(line))
            for line in output
            if line.startswith("#EXTINF") and ap.normalizar(ap.extraer_categoria(line)) in {"infantil", "infantiles"}
        ]
        unique_names = []
        for name in infant_names:
            if name not in unique_names:
                unique_names.append(name)
        self.assertEqual(unique_names[:3], ["popeye", "los pitufos", "heidi"])

    def test_reemplazo_preserves_external_mx_jmp2_urls(self):
        class EmptySession:
            def get(self, *args, **kwargs):
                class Response:
                    text = "#EXTM3U"
                    def raise_for_status(self):
                        return None
                return Response()

        url = "https://jmp2.uk/plu-6870072ca9d5c45c3e9466f1.m3u8"
        base = ["#EXTM3U", '#EXTINF:-1 tvg-id="6870072ca9d5c45c3e9466f1" tvg-name="Pokémon" group-title="Anime",Pokémon', url]
        output, stats = ap.reemplazar_pluto_tercero_por_propio(base, EmptySession())
        self.assertEqual(output, base)
        self.assertEqual(stats["mx_externos_conservados"], 1)

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

    def test_only_los_pitufos_es_is_removed_and_normal_channel_remains(self):
        base = (
            ["#EXTM3U"]
            + entry("pitufos.id", "Infantiles", "Los Pitufos", "https://bad.example/pitufos.m3u8")
            + entry("pitufos.es.id", "Infantiles", "Los Pitufos (ES)", "https://bad.example/pitufos-es.m3u8")
            + entry("heidi.id", "Infantiles", "Heidi", "https://good.example/heidi.m3u8")
        )
        source = [
            candidate(
                "pitufos.id",
                "Infantiles",
                "Los Pitufos",
                "https://new.example/pitufos.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            )
        ]
        output, stats = reconcile_lines(base, source)
        self.assertTrue(any("Los Pitufos" in line and "(ES)" not in line for line in output))
        self.assertIn("https://new.example/pitufos.m3u8", output)
        self.assertFalse(any("Los Pitufos (ES)" in line for line in output))
        self.assertIn("https://good.example/heidi.m3u8", output)
        self.assertEqual(stats["los_pitufos_eliminados"], 1)

    def test_all_source_urls_are_grouped_and_numbered_as_alternatives(self):
        base = ["#EXTM3U"] + entry(
            "pokemon.id", "Infantiles", "Pokémon", "https://old.example/pokemon.m3u8"
        )
        source = [
            candidate("pokemon.id", "Infantiles", "Pokémon", "https://magma.example/pokemon.m3u8", ap.FUENTE_MAGMA),
            candidate("pokemon.id", "Infantiles", "Pokémon", "https://mx.example/pokemon.m3u8", ap.FUENTE_PLUTO_ALTERNATIVAS),
            candidate("pokemon.id", "Infantiles", "Pokémon", "https://latam.example/pokemon.m3u8", ap.FUENTES_PLUTO[0]),
        ]
        source[2]["extinf"] = source[2]["extinf"].replace(
            'group-title="Infantiles"',
            'tvg-logo="https://logos.example/pokemon.png" group-title="Infantiles"',
        )
        output, stats = reconcile_lines(base, source)
        extinfs = [line for line in output if line.startswith("#EXTINF") and 'tvg-id="pokemon.id"' in line]
        urls = [output[output.index(line) + 1] for line in extinfs]
        self.assertEqual(urls, [
            "https://latam.example/pokemon.m3u8",
            "https://mx.example/pokemon.m3u8",
            "https://magma.example/pokemon.m3u8",
        ])
        self.assertIn(",Pokémon", extinfs[0])
        self.assertIn(",Pokémon [Opción 2]", extinfs[1])
        self.assertIn(",Pokémon [Opción 3]", extinfs[2])
        self.assertTrue(all('tvg-logo="https://logos.example/pokemon.png"' in line for line in extinfs))
        self.assertEqual(stats["alternativas_agregadas"], 2)

    def test_pokemon_with_different_source_ids_is_one_three_option_group(self):
        base = ["#EXTM3U"] + entry(
            "pokemon.old", "Anime", "Pokémon", "https://old.example/pokemon.m3u8"
        )
        pluto_id = "6870072ca9d5c45c3e9466f1"
        source = [
            candidate(
                pluto_id,
                "Anime",
                "Pokémon",
                f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{pluto_id}/master.m3u8?jwt=latam",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                "PlutoTVPokemon.us@US",
                "Anime",
                "Pokémon",
                f"https://jmp2.uk/plu-{pluto_id}.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
            candidate(
                "",
                "Anime",
                "Pokémon",
                "https://magma.example/pokemon.m3u8",
                ap.FUENTE_MAGMA,
            ),
        ]
        source[0]["extinf"] = source[0]["extinf"].replace(
            'group-title="Anime"',
            'tvg-logo="https://logos.example/pokemon.png" group-title="Anime"',
        )
        output, stats = reconcile_lines(base, source)
        extinfs = [
            line for line in output
            if line.startswith("#EXTINF") and f'tvg-id="{pluto_id}"' in line
        ]
        urls = [output[output.index(line) + 1] for line in extinfs]
        self.assertEqual(urls, [
            f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{pluto_id}/master.m3u8?jwt=latam",
            f"https://jmp2.uk/plu-{pluto_id}.m3u8",
            "https://magma.example/pokemon.m3u8",
        ])
        self.assertIn(",Pokémon", extinfs[0])
        self.assertIn(",Pokémon [Opción 2]", extinfs[1])
        self.assertIn(",Pokémon [Opción 3]", extinfs[2])
        self.assertTrue(all("MAGNA" not in line and "Pluto" not in line for line in extinfs))
        self.assertTrue(all('tvg-logo="https://logos.example/pokemon.png"' in line for line in extinfs))
        self.assertEqual(stats["alternativas_agregadas"], 2)

    def test_pluto_mx_without_group_title_inherits_unique_latam_category(self):
        base = ["#EXTM3U"] + entry(
            "pokemon.old", "Anime", "Pokémon", "https://old.example/pokemon.m3u8"
        )
        pluto_id = "6870072ca9d5c45c3e9466f1"
        source = [
            candidate(
                pluto_id,
                "Anime",
                "Pokémon",
                f"https://stitcher.pluto.tv/channel/{pluto_id}/master.m3u8?country=MX&jwt=latam",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                "PlutoTVPokemon.us@US",
                "",
                "Pokémon",
                f"https://jmp2.uk/plu-{pluto_id}.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
            candidate(
                "",
                "Anime",
                "Pokémon",
                "https://magma.example/pokemon.m3u8",
                ap.FUENTE_MAGMA,
            ),
        ]
        source[0]["extinf"] = source[0]["extinf"].replace(
            'group-title="Anime"',
            'tvg-logo="https://logos.example/pokemon.png" group-title="Anime"',
        )
        output, stats = reconcile_lines(base, source)
        extinfs = [
            line for line in output
            if line.startswith("#EXTINF") and f'tvg-id="{pluto_id}"' in line
        ]
        urls = [output[output.index(line) + 1] for line in extinfs]
        self.assertEqual(urls, [
            f"https://stitcher.pluto.tv/channel/{pluto_id}/master.m3u8?country=MX&jwt=latam",
            f"https://jmp2.uk/plu-{pluto_id}.m3u8",
            "https://magma.example/pokemon.m3u8",
        ])
        self.assertEqual(stats["candidatos_validos_por_fuente"]["Pluto MX"], 1)
        self.assertEqual(stats["sin_categoria_por_fuente"].get("Pluto MX", 0), 0)

    def test_pluto_es_url_is_removed_even_when_same_id_exists_in_latam(self):
        pluto_id = "5fceaab478f2af00080ff51f"
        base = ["#EXTM3U"] + (
            entry(
                pluto_id,
                "Anime",
                "Yu-Gi-Oh",
                f"https://stitcher.pluto.tv/channel/{pluto_id}/master.m3u8?country=ES&marketingRegion=ES",
            )
            + entry(
                pluto_id,
                "Anime",
                "Yu-Gi-Oh",
                f"https://stitcher.pluto.tv/channel/{pluto_id}/master.m3u8?country=MX&marketingRegion=MX",
            )
        )
        source = [
            candidate(
                pluto_id,
                "Anime",
                "Yu-Gi-Oh",
                f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{pluto_id}/master.m3u8?country=MX&jwt=latam",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                pluto_id,
                "Anime",
                "Yu-Gi-Oh",
                f"https://jmp2.uk/plu-{pluto_id}.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
            candidate(
                pluto_id,
                "Anime",
                "Yu-Gi-Oh",
                f"https://stitcher.pluto.tv/channel/{pluto_id}/master.m3u8?country=ES&marketingRegion=ES",
                ap.FUENTES_PLUTO[1],
            ),
        ]
        output, _ = reconcile_lines(base, source)
        self.assertFalse(any("country=ES" in line or "marketingRegion=ES" in line for line in output))
        self.assertTrue(any("country=MX&jwt=latam" in line for line in output))
        self.assertTrue(any(f"https://jmp2.uk/plu-{pluto_id}.m3u8" in line for line in output))

    def test_yugioh_espanol_is_removed_but_latam_mx_and_magna_stay_grouped(self):
        base = ["#EXTM3U"] + (
            entry(
                "yugioh.es",
                "Anime",
                "Yu-Gi-Oh! Español",
                "https://old.example/yugioh-es.m3u8",
            )
            + entry(
                "yugioh.old",
                "Anime",
                "Yu-Gi-Oh",
                "https://old.example/yugioh.m3u8",
            )
        )
        pluto_id = "5fceaab478f2af00080ff51f"
        source = [
            candidate(
                pluto_id,
                "Anime",
                "Yu-Gi-Oh",
                f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{pluto_id}/master.m3u8?jwt=latam",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                "YuGiOh.us@SD",
                "Anime",
                "Yu-Gi-Oh",
                f"https://jmp2.uk/plu-{pluto_id}.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
            candidate(
                "",
                "Anime",
                "Yu-Gi-Oh!",
                "https://magma.example/yugioh.m3u8",
                ap.FUENTE_MAGMA,
            ),
        ]
        output, stats = reconcile_lines(base, source)
        self.assertFalse(any("Español" in line for line in output))
        extinfs = [
            line for line in output
            if line.startswith("#EXTINF") and f'tvg-id="{pluto_id}"' in line
        ]
        urls = [output[output.index(line) + 1] for line in extinfs]
        self.assertEqual(urls, [
            f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{pluto_id}/master.m3u8?jwt=latam",
            f"https://jmp2.uk/plu-{pluto_id}.m3u8",
            "https://magma.example/yugioh.m3u8",
        ])
        self.assertIn(",Yu-Gi-Oh", extinfs[0])
        self.assertIn(",Yu-Gi-Oh [Opción 2]", extinfs[1])
        self.assertIn(",Yu-Gi-Oh [Opción 3]", extinfs[2])
        self.assertEqual(stats["alternativas_agregadas"], 2)

    def test_pluto_kids_are_moved_to_infantiles_and_es_pitufos_is_removed(self):
        base = ["#EXTM3U"] + (
            entry(
                "pitufos.es",
                "Infantiles",
                "Los Pitufos",
                "https://stitcher.pluto.tv/channel/pitufos-es/master.m3u8?country=ES&marketingRegion=ES",
            )
            + entry("heidi.old", "Infantiles", "Heidi", "https://old.example/heidi.m3u8")
            + entry("kids.other", "Infantiles", "Otro infantil", "https://kids.example/other.m3u8")
        )
        popeye_id = "677d93afe650a700081e5f18"
        pitufos_id = "68a3a97fd8f7693ae3f8575f"
        heidi_id = "68779a09c691b3f0964127c6"
        source = [
            candidate(
                popeye_id,
                "Retro",
                "Popeye",
                f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{popeye_id}/master.m3u8?jwt=latam",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                "",
                "",
                "Popeye",
                f"https://jmp2.uk/plu-{popeye_id}.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
            candidate(
                pitufos_id,
                "Retro",
                "Los Pitufos",
                f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{pitufos_id}/master.m3u8?jwt=latam",
                ap.FUENTES_PLUTO[0],
            ),
            candidate(
                "",
                "",
                "Los Pitufos",
                f"https://jmp2.uk/plu-{pitufos_id}.m3u8",
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
            candidate(
                "",
                "Infantiles",
                "Los Pitufos",
                "https://magma.example/pitufos.m3u8",
                ap.FUENTE_MAGMA,
            ),
            candidate(
                "68d27949793c71d988ca624c",
                "Infantil",
                "Los Pitufos",
                "https://stitcher.pluto.tv/channel/pitufos-es/master.m3u8?country=ES&marketingRegion=ES",
                ap.FUENTES_PLUTO[1],
            ),
            candidate(
                heidi_id,
                "Infantil",
                "Heidi",
                f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/channel/{heidi_id}/master.m3u8?jwt=es",
                ap.FUENTES_PLUTO[1],
            ),
        ]
        output, _ = reconcile_lines(base, source)
        self.assertFalse(any("pitufos-es" in line and "country=ES" in line for line in output))
        self.assertIn(f"https://jmp2.uk/plu-{pitufos_id}.m3u8", output)
        self.assertIn("https://magma.example/pitufos.m3u8", output)
        self.assertIn(f"https://jmp2.uk/plu-{popeye_id}.m3u8", output)
        infant_names = [
            ap.extraer_nombre(line)
            for line in output
            if line.startswith("#EXTINF") and ap.normalizar(ap.extraer_categoria(line)) in {"infantil", "infantiles"}
        ]
        unique_names = []
        for name in infant_names:
            base_name = name.split(" [Opción ", 1)[0]
            if base_name not in unique_names:
                unique_names.append(base_name)
        self.assertEqual(unique_names[:3], ["Popeye", "Los Pitufos", "Heidi"])

    def test_popeye_from_retro_moves_to_infantiles_before_pitufos_and_heidi(self):
        lines = (
            "#EXTM3U\\n"
            + entry("popeye.id", "Retro", "Popeye", "https://kids.example/popeye.m3u8")
            + entry("pitufos.id", "Infantiles", "Los Pitufos", "https://kids.example/pitufos.m3u8")
            + entry("heidi.id", "Infantiles", "Heidi", "https://kids.example/heidi.m3u8")
        ).splitlines()
        output = sync._prioritize_infantiles(lines)
        parsed = sync._read_blocks(output)[1]
        names = [ap.extraer_nombre(block["extinf"]) for block in parsed if ap.normalizar(ap.extraer_categoria(block["extinf"])) == "infantiles"]
        self.assertEqual(names[:3], ["Popeye", "Los Pitufos", "Heidi"])

    def test_infantiles_priority_order_is_popeye_pitufos_heidi(self):
        base = ["#EXTM3U"] + (
            entry("kids.heidi", "Infantiles", "Heidi", "https://kids.example/heidi.m3u8")
            + entry("kids.other", "Infantiles", "Otro infantil", "https://kids.example/other.m3u8")
            + entry("kids.popeye", "Infantiles", "Popeye", "https://kids.example/popeye.m3u8")
            + entry("kids.pitufos", "Infantiles", "Los Pitufos", "https://kids.example/pitufos.m3u8")
        )
        output, _ = reconcile_lines(base, [])
        names = [
            ap.extraer_nombre(line)
            for line in output
            if line.startswith("#EXTINF") and ap.normalizar(ap.extraer_categoria(line)) == "infantiles"
        ]
        self.assertEqual(names[:3], ["Popeye", "Los Pitufos", "Heidi"])

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
                ap.FUENTE_PLUTO_ALTERNATIVAS,
            ),
        ]
        manifest = {"id:shared.anime": {"source": ap.FUENTES_PLUTO[1]}}
        output, stats = reconcile_lines(base, source, manifest)
        self.assertFalse(any('tvg-id="es.only"' in line for line in output))
        self.assertTrue(any('tvg-id="shared.anime"' in line for line in output))
        self.assertTrue(any('tvg-id="mx.only"' in line for line in output))
        self.assertEqual(manifest["id:shared.anime"]["source"], ap.FUENTES_PLUTO[0])
        self.assertIn("https://stitcher.pluto.tv/channel/shared-latam/master.m3u8", output)
        self.assertNotIn("https://stitcher.pluto.tv/channel/shared-es/master.m3u8", output)
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

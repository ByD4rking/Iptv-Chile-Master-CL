import unittest
import re
import alimentar_principal as ap
import sincronizar_complementos as sc


def block(channel_id, category, name, url):
    id_attr = f' tvg-id="{channel_id}"' if channel_id else ""
    logo_id = channel_id or "channel"
    return [
        f'#EXTINF:-1{id_attr} tvg-name="{name}" tvg-logo="https://logo.example/{logo_id}.png" group-title="{category}",{name}',
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

    def test_generated_main_playlist_matches_requested_reference_rules(self):
        from pathlib import Path
        import re

        path = Path(__file__).resolve().parents[1] / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
        if not path.is_file():
            self.skipTest("La M3U real no está presente en este entorno.")
        parsed = self.entries(path.read_text(encoding="utf-8-sig").splitlines())
        playable = []
        for item in parsed:
            extinf = item[0]
            category = re.search(r'group-title="([^"]*)"', extinf, re.I)
            display = extinf.split(",", 1)[1].strip() if "," in extinf else ""
            url = next((line.strip() for line in item[1:] if line.startswith(("http://", "https://"))), "")
            playable.append((category.group(1) if category else "", display, url, extinf))

        kids = [item for item in playable if item[0].strip().lower() in {"infantiles", "infantil"}]
        kid_names = []
        for item in kids:
            base_name = re.sub(
                r"\s*\[(?:opci[oó]n|opc\.?|option)\s*\d+\]$",
                "",
                item[1],
                flags=re.I,
            ).strip().lower()
            if base_name not in kid_names:
                kid_names.append(base_name)
        self.assertEqual(kid_names[:3], ["popeye", "los pitufos", "heidi"])

        self.assertFalse(any("los pitufos" in x[1].lower() and (
            "pluto es" in x[1].lower() or "country=es" in x[2].lower() or "marketingregion=es" in x[2].lower()
        ) for x in playable))

        delmi = [x for x in playable if "delmi" in x[1].lower()]
        if delmi:
            self.assertTrue(any(x[1] == "Delmi TV 2" and x[0].strip().lower() == "anime" for x in delmi))

        cyg = [(i, x) for i, x in enumerate(playable) if re.sub(r"\s*\[.*?\]$", "", x[1], flags=re.I).strip().lower() == "cygtvcl"]
        if len(cyg) >= 2:
            positions = [i for i, _ in cyg]
            self.assertEqual(positions, list(range(positions[0], positions[0] + len(positions))))

        cartoonito = [x for x in playable if "cartoonito" in x[1].lower()]
        self.assertTrue(cartoonito, "Se perdió Cartoonito HD y su alternativa histórica.")
        self.assertTrue(any("opc.4" in x[1].lower() or "opción 2" in x[1].lower() for x in cartoonito),
                        "No se conservó/reagrupó la alternativa histórica de Cartoonito.")

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

    def test_restored_option_is_inserted_after_complete_m3u_block(self):
        primary = block("cartoonito.id", "Infantiles", "Cartoonito HD", "https://a.example/cartoonito.m3u8")
        option = block("cartoonito.id", "Infantiles", "Cartoonito HD [Opc.4]", "https://four.example/cartoonito.m3u8")
        output, restored = ap.restaurar_no_pluto_existente(
            ["#EXTM3U"] + primary,
            {"https://four.example/cartoonito.m3u8": option},
        )
        self.assertEqual(restored, 1)
        parsed = self.entries(output)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0][-1], "https://a.example/cartoonito.m3u8")
        self.assertEqual(parsed[1][0].split(",", 1)[1], "Cartoonito HD [Opc.4]")
        self.assertEqual(parsed[1][-1], "https://four.example/cartoonito.m3u8")

    def test_restore_does_not_reuse_position_of_reassigned_single_id(self):
        # Incluso una única aparición histórica del ID puede pertenecer a otro
        # nombre. C y G TV no debe heredar la posición de Canal ajeno.
        original = ["#EXTM3U"]
        original += block("1626", "CHILE TV", "Canal ajeno", "https://a.example/ajeno.m3u8")
        original += block("cadena.id", "CHILE TV", "Cadenartv", "https://b.example/cadenartv.m3u8")
        current = ["#EXTM3U"]
        current += block("1626", "CHILE TV", "C y G TV", "https://c.example/cygtv.m3u8")
        current += block("cadena.id", "CHILE TV", "Cadenartv", "https://b.example/cadenartv.m3u8")
        # Simula la última consolidación de alternativas que se ejecutaba
        # después de restaurar el orden y podía volver a adelantar el bloque.
        grouped = ap.agrupar_alternativas_por_identidad(current)
        restored = ap.restaurar_orden_original_por_categoria(grouped, original)
        parsed = self.entries(restored)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertLess(names.index("Cadenartv"), names.index("C y G TV"))
        # La auditoría tampoco debe confundir el ID reasignado con el canal antiguo.
        ap.validar_orden_canales(original, restored)

    def test_grouping_does_not_assign_new_id_to_historical_primary(self):
        lines = ["#EXTM3U"]
        lines += block("", "CHILE TV", "Canal A", "https://a.example/canal-a.m3u8")
        lines += block("1626", "CHILE TV", "Canal A", "https://b.example/canal-a.m3u8")
        output = ap.agrupar_alternativas_por_identidad(lines)
        parsed = self.entries(output)
        self.assertEqual(len(parsed), 2)
        self.assertNotIn("tvg-id=", parsed[0][0])
        self.assertIn('tvg-id="1626"', parsed[1][0])
        self.assertIn("[Opción 2]", parsed[1][0])
        ap.validar_orden_canales(lines, output)

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


    def test_restore_recognizes_historical_opc_dot_suffix(self):
        original = ["#EXTM3U"]
        original += block("", "CHILE TV", "La Red SD (Nacional)[Opc.2]", "https://a.example/la-red-2.m3u8")
        original += block("", "CHILE TV", "La Red SD (Nacional)[Opc.3]", "https://a.example/la-red-3.m3u8")
        original += block("", "CHILE TV", "ChileVisión HD (Geo-Blocked)", "https://a.example/chv.m3u8")
        current = ["#EXTM3U"]
        current += block("", "CHILE TV", "ChileVisión HD (Geo-Blocked)", "https://a.example/chv.m3u8")
        current += block("", "CHILE TV", "La Red SD (Nacional)", "https://a.example/la-red-2.m3u8")
        current += block("", "CHILE TV", "La Red SD (Nacional) [Opción 2]", "https://a.example/la-red-3.m3u8")
        restored = ap.restaurar_orden_original_por_categoria(current, original)
        parsed = self.entries(restored)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertLess(names.index("La Red SD (Nacional)"), names.index("ChileVisión HD (Geo-Blocked)"))
        ap.validar_orden_canales(original, restored)

    def test_remove_los_pitufos_es_by_url_region_even_without_es_label(self):
        lines = ["#EXTM3U"]
        lines += block("pitufos.es", "Infantiles", "Los Pitufos", "https://pluto.example/live.m3u8?country=ES&marketingRegion=ES")
        lines += block("pitufos.mx", "Infantiles", "Los Pitufos", "https://pluto.example/live.m3u8?country=MX&marketingRegion=MX")
        output = sc.quitar_los_pitufos_es(lines)
        parsed = self.entries(output)
        self.assertEqual(len(parsed), 1)
        self.assertIn("country=MX", parsed[0][-1])


    def test_restore_keeps_first_position_when_historical_channel_gains_id(self):
        original = ["#EXTM3U"]
        original += block("", "CHILE TV", "C y G TV", "https://a.example/cygtv-legacy.m3u8")
        original += block("", "CHILE TV", "Cadena-RTV", "https://a.example/cadena.m3u8")
        original += block("1626", "CHILE TV", "C y G TV", "https://a.example/cygtv-id.m3u8")
        current = ["#EXTM3U"]
        current += block("", "CHILE TV", "Cadena-RTV", "https://a.example/cadena.m3u8")
        current += block("1626", "CHILE TV", "C y G TV", "https://a.example/cygtv-id.m3u8")
        restored = ap.restaurar_orden_original_por_categoria(current, original)
        parsed = self.entries(restored)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertLess(names.index("C y G TV"), names.index("Cadena-RTV"))
        ap.validar_orden_canales(original, restored)


    def test_pluto_es_excludes_anime_and_los_pitufos_but_not_other_channels(self):
        fuente_es = ap.FUENTES_PLUTO[1]
        fuente_latam = ap.FUENTES_PLUTO[0]
        pitufos = {
            "categoria": "Infantiles",
            "nombre": "Los Pitufos",
            "extinf": '#EXTINF:-1 tvg-name="Los Pitufos",Los Pitufos',
        }
        anime = {
            "categoria": "Anime",
            "nombre": "Anime ES",
            "extinf": '#EXTINF:-1 tvg-name="Anime ES",Anime ES',
        }
        otro_infantil = {
            "categoria": "Infantiles",
            "nombre": "Heidi",
            "extinf": '#EXTINF:-1 tvg-name="Heidi",Heidi',
        }
        self.assertTrue(ap.canal_excluido_pluto_es(fuente_es, pitufos))
        self.assertTrue(ap.canal_excluido_pluto_es(fuente_es, anime))
        self.assertFalse(ap.canal_excluido_pluto_es(fuente_es, otro_infantil))
        self.assertFalse(ap.canal_excluido_pluto_es(fuente_latam, pitufos))


    def test_restore_matches_delmi_v2_historical_label(self):
        original = ["#EXTM3U"]
        original += block("", "Anime", "Delmi TV [V2]", "https://a.example/delmi-v2.m3u8")
        original += block("", "Anime", "Doraemon", "https://a.example/doraemon.m3u8")
        current = ["#EXTM3U"]
        current += block("", "Anime", "Doraemon", "https://a.example/doraemon.m3u8")
        current += block("", "Anime", "Delmi TV 2", "https://a.example/delmi-v2.m3u8")
        restored = ap.restaurar_orden_original_por_categoria(current, original)
        parsed = self.entries(restored)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertLess(names.index("Delmi TV 2"), names.index("Doraemon"))
        ap.validar_orden_canales(original, restored)


    def test_restore_matches_historical_magma_suffix(self):
        original = ["#EXTM3U"]
        original += block("", "Anime", "Doraemon", "https://a.example/doraemon.m3u8")
        original += block("", "Anime", "Dragon Ball [MAGMA]", "https://a.example/dragonball-magma.m3u8")
        current = ["#EXTM3U"]
        current += block("", "Anime", "Dragon Ball", "https://a.example/dragonball-magma.m3u8")
        current += block("", "Anime", "Doraemon", "https://a.example/doraemon.m3u8")
        restored = ap.restaurar_orden_original_por_categoria(current, original)
        parsed = self.entries(restored)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertLess(names.index("Doraemon"), names.index("Dragon Ball"))
        ap.validar_orden_canales(original, restored)


    def test_pluto_ids_protect_nonpluto_alternatives_from_order_audit(self):
        pluto_id = "5ee92e72fb286e0007285fec"
        original = ["#EXTM3U"]
        original += block("", "Anime", "Naruto Peliculas", "https://a.example/naruto-peliculas.m3u8")
        current = ["#EXTM3U"]
        current += block(pluto_id, "Anime", "Naruto", "https://a.example/naruto-alt.m3u8")
        current += block(pluto_id, "Anime", "Naruto", f"https://jmp2.uk/plu-{pluto_id}.m3u8")
        current += block("", "Anime", "Naruto Peliculas", "https://a.example/naruto-peliculas.m3u8")
        ids = ap.obtener_ids_pluto_existentes(current)
        self.assertIn(pluto_id, ids)
        ap.validar_orden_canales(original, current, ids_pluto_omitidos=ids)


    def test_spanish_is_part_of_channel_name_not_a_provider_suffix(self):
        self.assertEqual(ap.normalizar_nombre_canal("DW Español"), "dwespanol")
        self.assertNotEqual(
            ap.normalizar_nombre_canal("DW Español"),
            ap.normalizar_nombre_canal("DW"),
        )


    def test_grouping_unifies_spacing_and_symbol_variants_of_same_channel(self):
        lines = ["#EXTM3U"]
        lines += block("", "CHILE TV", "Solo TV", "https://a.example/solo-tv.m3u8")
        lines += block("", "CHILE TV", "SoloTV ✪", "https://b.example/solotv.m3u8")
        output = ap.agrupar_alternativas_por_identidad(lines)
        parsed = self.entries(output)
        self.assertEqual(len(parsed), 2)
        tvg_names = [
            re.search(r'tvg-name="([^"]*)"', item[0], re.I).group(1)
            for item in parsed
        ]
        self.assertEqual(tvg_names[0], tvg_names[1])
        self.assertEqual(parsed[1][0].split(",", 1)[1], "Solo TV [Opción 2]")

    def test_grouping_preserves_each_alternative_logo_independently(self):
        lines = ["#EXTM3U"]
        lines += [
            '#EXTINF:-1 group-title="Infantiles" tvg-name="Discovery Kids" tvg-logo="https://logo.example/one.png" logo="https://logo.example/one.png",Discovery Kids',
            "https://a.example/discovery-1.m3u8",
            '#EXTINF:-1 group-title="Infantiles" tvg-name="Discovery Kids" tvg-logo="https://logo.example/two.png" logo="https://logo.example/two.png",Discovery Kids',
            "https://a.example/discovery-2.m3u8",
        ]
        parsed = self.entries(ap.agrupar_alternativas_por_identidad(lines))
        self.assertEqual(len(parsed), 2)
        self.assertIn('tvg-logo="https://logo.example/one.png"', parsed[0][0])
        self.assertIn('logo="https://logo.example/one.png"', parsed[0][0])
        self.assertIn('tvg-logo="https://logo.example/two.png"', parsed[1][0])
        self.assertIn('logo="https://logo.example/two.png"', parsed[1][0])

    def test_final_orchestrator_grouping_preserves_individual_logos(self):
        lines = ["#EXTM3U"]
        lines += [
            '#EXTINF:-1 group-title="Infantiles" tvg-name="Disney Channel" tvg-logo="https://logo.example/disney.png",Disney Channel',
            "https://a.example/disney-1.m3u8",
            '#EXTINF:-1 group-title="Infantiles" tvg-name="Disney Channel" tvg-logo="https://logo.example/disney-alt.png",Disney Channel',
            "https://a.example/disney-2.m3u8",
        ]
        parsed = self.entries(sc._group_and_label_alternatives(lines, {}))
        self.assertEqual(len(parsed), 2)
        self.assertIn('tvg-logo="https://logo.example/disney.png"', parsed[0][0])
        self.assertIn('tvg-logo="https://logo.example/disney-alt.png"', parsed[1][0])


    def test_hd_sd_variants_remain_separate(self):
        lines = ["#EXTM3U"]
        lines += block("", "Cine / Películas", "Cine Marvel", "https://cine.example/sd.m3u8")
        lines += block("", "Cine / Películas", "Cine Marvel HD", "https://cine.example/hd.m3u8")
        parsed = self.entries(ap.agrupar_alternativas_por_identidad(lines))
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertEqual(names, ["Cine Marvel", "Cine Marvel HD"])

    def test_restaurar_logos_historicos_recovers_missing_but_never_overwrites_existing(self):
        old = ["#EXTM3U",
            '#EXTINF:-1 tvg-id="channel.one" tvg-logo="https://logo.example/old.png" group-title="Series",Canal Uno',
            "https://old.example/one.m3u8"]
        current = ["#EXTM3U",
            '#EXTINF:-1 tvg-id="channel.one" group-title="Series",Canal Uno',
            "https://new.example/one.m3u8",
            '#EXTINF:-1 tvg-id="channel.one" tvg-logo="https://logo.example/current.png" group-title="Series",Canal Uno [Opción 2]',
            "https://new.example/two.m3u8"]
        restored, stats = ap.restaurar_logos_historicos(current, old)
        self.assertIn('tvg-logo="https://logo.example/old.png"', restored[1])
        self.assertIn('tvg-logo="https://logo.example/current.png"', restored[3])
        self.assertEqual(stats["lista_anterior"], 1)


    def test_restaurar_logos_uses_historical_reference_even_if_category_changed(self):
        previous = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-logo="https://logo.example/peppa.png" group-title="Infantil",Peppa Pig',
            "https://old.example/peppa.m3u8",
        ]
        current = [
            "#EXTM3U",
            '#EXTINF:-1 group-title="Infantiles",Peppa Pig',
            "https://new.example/peppa.m3u8",
        ]
        restored, stats = ap.restaurar_logos_historicos(current, previous)
        self.assertIn('tvg-logo="https://logo.example/peppa.png"', restored[1])
        self.assertEqual(stats["lista_anterior"], 1)
    def test_spanish_country_has_priority_over_anime_thematic_category(self):
        categories = ["Anime", "España"]
        self.assertEqual(ap.determinar_destino("Anime", "Canal Anime", "espana", categories), "España")
        self.assertEqual(ap.destino_especial_total_otros("Anime España", "TOTAL", categories), "España")

    def test_spanish_country_channels_are_moved_out_of_anime(self):
        lines = ["#EXTM3U"]
        lines += block("", "Anime", "Beyblade (España)", "https://example.test/beyblade-es.m3u8")
        lines += block("", "Anime", "Anime Vision Classics (España)[Opc.1]", "https://example.test/animevision-es.m3u8")
        lines += block("", "Anime", "Dragon Ball LATAM", "https://example.test/dragon-latam.m3u8")
        output = ap.aplicar_ajustes_referencia(lines, set())
        parsed = self.entries(output)
        spanish_names = [item[0].split(",", 1)[1] for item in parsed if 'group-title="España"' in item[0]]
        anime_names = [item[0].split(",", 1)[1] for item in parsed if 'group-title="Anime"' in item[0]]
        self.assertIn("Beyblade (España)", spanish_names)
        self.assertIn("Anime Vision Classics (España)[Opc.1]", spanish_names)
        self.assertIn("Dragon Ball LATAM", anime_names)
    def test_parenthetical_opc_suffix_is_preserved_as_variant_name(self):
        self.assertEqual(sc._without_option_suffix("Cartoonito HD (Opc.3)"), "Cartoonito HD (Opc.3)")
        self.assertEqual(ap.normalizar_nombre_canal("Cartoonito HD (Opc.3)"),
                         "cartoonitohdopc3")
        self.assertNotEqual(
            ap.normalizar_nombre_canal("Cartoonito HD (Opc.3)"),
            ap.normalizar_nombre_canal("Cartoonito HD (Opc.4)"),
        )

    def test_regroup_after_final_order_restore_keeps_naruto_alternatives_adjacent(self):
        naruto_id = "5ee92e72fb286e0007285fec"
        original = ["#EXTM3U"]
        original += block("", "Anime", "Naruto", "https://a.example/naruto-old.m3u8")
        original += block("", "Anime", "Naruto Peliculas", "https://a.example/naruto-movies.m3u8")
        original += block(naruto_id, "Anime", "Naruto", "https://a.example/naruto-pluto-old.m3u8")
        current = ["#EXTM3U"]
        current += block(naruto_id, "Anime", "Naruto [Opción 3]", "https://a.example/naruto-alt.m3u8")
        current += block("", "Anime", "Naruto Peliculas", "https://a.example/naruto-movies.m3u8")
        current += block(naruto_id, "Anime", "Naruto", "https://a.example/naruto-pluto.m3u8")
        restored = ap.restaurar_orden_original_por_categoria(current, original)
        regrouped = sc._group_and_label_alternatives(restored, {})
        parsed = self.entries(regrouped)
        positions = [
            i for i, item in enumerate(parsed)
            if item[0].split(",", 1)[1].startswith("Naruto")
            and "Peliculas" not in item[0].split(",", 1)[1]
        ]
        self.assertEqual(positions, list(range(positions[0], positions[0] + len(positions))))


if __name__ == "__main__":
    unittest.main()

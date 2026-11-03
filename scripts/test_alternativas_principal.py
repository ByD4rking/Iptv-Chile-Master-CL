import unittest
import alimentar_principal as ap


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

    def test_restore_does_not_reuse_position_of_same_id_for_another_channel(self):
        # La fuente histórica reutiliza tvg-id=1626 en dos nombres distintos.
        # La posición del primer ID no debe arrastrar C y G TV por delante
        # de Cadenartv cuando se reconstruye el orden de CHILE TV.
        original = ["#EXTM3U"]
        original += block("1626", "CHILE TV", "Canal ajeno", "https://a.example/ajeno.m3u8")
        original += block("cadena.id", "CHILE TV", "Cadenartv", "https://b.example/cadenartv.m3u8")
        original += block("1626", "CHILE TV", "C y G TV", "https://c.example/cygtv.m3u8")
        current = ["#EXTM3U"]
        current += block("1626", "CHILE TV", "C y G TV", "https://c.example/cygtv.m3u8")
        current += block("cadena.id", "CHILE TV", "Cadenartv", "https://b.example/cadenartv.m3u8")
        restored = ap.restaurar_orden_original_por_categoria(current, original)
        parsed = self.entries(restored)
        names = [item[0].split(",", 1)[1] for item in parsed]
        self.assertLess(names.index("Cadenartv"), names.index("C y G TV"))

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


if __name__ == "__main__":
    unittest.main()

import unittest
from scripts.auditar_logos import audit, parse_playlist, check_url
import alimentar_principal as ap

class LogoAuditTests(unittest.TestCase):
    def test_parse_and_deduplicate_logo_urls(self):
        text = '\n'.join([
            '#EXTM3U',
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/a.png",Canal A',
            'https://stream.test/a.m3u8',
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/a.png",Canal A Opción 2',
            'https://stream.test/b.m3u8',
            '#EXTINF:-1 group-title="Música" tvg-logo="",Canal B',
            'https://stream.test/c.m3u8',
        ])
        rows = parse_playlist(text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["group"], "Anime")
        self.assertEqual(rows[2]["logo"], "")

    def test_confirmed_broken_logo_is_replaced_and_both_attributes_match(self):
        broken = "https://img.test/broken.png"
        working = "https://img.test/working.png"
        current = [
            "#EXTM3U",
            f'#EXTINF:-1 group-title="Anime" tvg-id="canal.a" tvg-logo="{broken}" logo="{broken}",Canal A',
            "https://stream.test/current.m3u8",
        ]
        reference = [
            f'#EXTINF:-1 group-title="Anime" tvg-id="canal.a" tvg-logo="{working}",Canal A',
            "https://stream.test/reference.m3u8",
        ]
        result, stats = ap.restaurar_logos_historicos(
            current,
            reference,
            logos_rotos_confirmados={broken},
            validar_logo=lambda url: url == working,
        )
        self.assertIn(f'tvg-logo="{working}"', result[1])
        self.assertIn(f'logo="{working}"', result[1])
        self.assertEqual(stats["rotos_sin_reemplazo"], 0)

    def test_explicit_logo_override_replaces_only_the_matching_stream(self):
        stream = "https://stream.test/bitme.m3u8"
        old = "https://img.test/old.webp"
        new = "https://img.test/new.png"
        current = [
            "#EXTM3U",
            f'#EXTINF:-1 group-title="Anime" tvg-logo="{old}",Bitme HD (México)',
            stream,
            f'#EXTINF:-1 group-title="Anime" tvg-logo="{old}",Otra señal',
            "https://stream.test/other.m3u8",
        ]
        result, stats = ap.restaurar_logos_historicos(
            current,
            [],
            logos_forzados_por_url={stream: new},
            validar_logo=lambda url: url == new,
        )
        self.assertIn(f'tvg-logo="{new}"', result[1])
        self.assertIn(f'tvg-logo="{old}"', result[3])
        self.assertEqual(stats["forzados"], 1)

    def test_working_logo_is_preserved_even_if_reference_differs(self):
        working = "https://img.test/working.png"
        other = "https://img.test/other.png"
        current = [
            "#EXTM3U",
            f'#EXTINF:-1 group-title="Anime" tvg-id="canal.a" tvg-logo="{working}",Canal A',
            "https://stream.test/current.m3u8",
        ]
        reference = [
            f'#EXTINF:-1 group-title="Anime" tvg-id="canal.a" tvg-logo="{other}",Canal A',
            "https://stream.test/reference.m3u8",
        ]
        result, _ = ap.restaurar_logos_historicos(
            current,
            reference,
            validar_logo=lambda url: url == other,
        )
        self.assertIn(f'tvg-logo="{working}"', result[1])
        self.assertNotIn(f'tvg-logo="{other}"', result[1])

    def test_country_flag_is_not_used_as_a_channel_logo(self):
        current = [
            "#EXTM3U",
            '#EXTINF:-1 group-title="Bolivia" tvg-id="canal.24",Canal 24 Multivision',
            "https://stream.test/canal24.m3u8",
        ]
        reference = [
            '#EXTINF:-1 group-title="Bolivia" tvg-id="canal.24" tvg-logo="https://flagcdn.com/w320/bo.png",Canal 24 Multivision',
            "https://stream.test/other.m3u8",
        ]
        result, stats = ap.restaurar_logos_historicos(current, reference)
        self.assertNotIn("tvg-logo=", result[1])
        self.assertEqual(stats["sin_referencia"], 1)

    def test_confirmed_broken_logo_without_verified_alternative_is_cleared(self):
        broken = "https://img.test/broken.png"
        current = [
            "#EXTM3U",
            f'#EXTINF:-1 group-title="Anime" tvg-logo="{broken}" logo="{broken}",Canal A',
            "https://stream.test/current.m3u8",
        ]
        result, stats = ap.restaurar_logos_historicos(
            current,
            [],
            logos_rotos_confirmados={broken},
            validar_logo=lambda url: False,
        )
        self.assertNotIn("tvg-logo=", result[1])
        self.assertNotIn('logo="', result[1])
        self.assertEqual(stats["rotos_sin_reemplazo"], 1)
        self.assertEqual(stats["pendientes_detalle"], ["Canal A [Anime]"])

    def test_unescaped_unicode_in_logo_url_is_reported_as_broken_not_crashing(self):
        result = check_url("https://cdn.example/logo/Bio\u00adBio.png")
        self.assertEqual(result["status"], "broken")
        self.assertIn("no codificados", result["detail"])

    def test_audit_does_not_modify_and_reports_statuses(self):
        text = '\n'.join([
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/good.png",Bueno',
            'https://stream.test/good.m3u8',
            '#EXTINF:-1 group-title="Anime" tvg-logo="https://img.test/bad.png",Malo',
            'https://stream.test/bad.m3u8',
            '#EXTINF:-1 group-title="Música" tvg-logo="",Sin logo',
            'https://stream.test/none.m3u8',
        ])
        before = text
        def fake(url):
            return {"status": "ok" if url.endswith("good.png") else "broken", "detail": "test"}
        result = audit(text, checker=fake)
        self.assertEqual(result["channels"], 3)
        self.assertEqual(result["unique_logo_urls"], 2)
        self.assertEqual(result["logo_urls"]["ok"], 1)
        self.assertEqual(result["logo_urls"]["broken"], 1)
        self.assertEqual(len(result["missing_logo_entries"]), 1)
        self.assertEqual(text, before)

if __name__ == "__main__":
    unittest.main()

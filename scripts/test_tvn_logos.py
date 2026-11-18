import unittest

from scripts.blindajes_principal import blindar_logos, validar_logos_tvn_autorizados

TVN_LOGO = "https://i.imgur.com/3FKZHL4.png"
TV_CHILE_LOGO = "https://i.imgur.com/oYFto0V.png"


def channel(name, logo):
    return [
        f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="CHILE TV",{name}',
        f"https://example.com/{name.lower().replace(' ', '-')}.m3u8",
    ]


class TvnLogoTests(unittest.TestCase):
    def test_both_tvn_signals_copy_logo_even_without_historical_identity_match(self):
        # El logo canónico se toma de la señal TVN ya existente.
        reference = ["#EXTM3U"] + channel("TVN (1080p)", TVN_LOGO)

        # Las dos señales objetivo tienen IDs/URLs distintos y logos incorrectos.
        current = ["#EXTM3U"]
        current += channel("TVN HD (LOCAL)", "https://i.imgur.com/old-tvn.png")
        current += channel("TV Chile (1080p) [Geo-blocked]", "https://i.imgur.com/oYFto0V.png")

        result, stats = blindar_logos(current, reference)
        extinf = [line for line in result if line.startswith("#EXTINF")]
        self.assertEqual(len(extinf), 2)
        self.assertIn(f'tvg-logo="{TVN_LOGO}"', extinf[0])
        self.assertIn(f'tvg-logo="{TV_CHILE_LOGO}"', extinf[1])
        self.assertEqual(stats["logos_autorizados"], 2)
        self.assertTrue(validar_logos_tvn_autorizados(result))

    def test_other_existing_logo_is_preserved(self):
        other_logo = "https://example.com/other.png"
        reference = ["#EXTM3U"] + channel("Canal de prueba", other_logo)
        current = ["#EXTM3U"] + channel("Canal de prueba", "https://example.com/wrong.png")
        result, _ = blindar_logos(current, reference)
        extinf = next(line for line in result if line.startswith("#EXTINF"))
        self.assertIn(f'tvg-logo="{other_logo}"', extinf)


if __name__ == "__main__":
    unittest.main()

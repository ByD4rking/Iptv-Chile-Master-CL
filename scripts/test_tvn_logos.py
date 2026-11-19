import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.blindajes_principal import (
    blindar_logos,
    validar_logos_chile_tv,
    validar_logos_tvn_autorizados,
)

TVN_LOGO = "https://i.imgur.com/3FKZHL4.png"
TV_CHILE_LOGO = TVN_LOGO


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
        current += channel("TV Chile (1080p)", "https://i.imgur.com/oYFto0V.png")

        result, stats = blindar_logos(current, reference)
        extinf = [line for line in result if line.startswith("#EXTINF")]
        self.assertEqual(len(extinf), 2)
        self.assertIn(f'tvg-logo="{TVN_LOGO}"', extinf[0])
        self.assertIn(f'tvg-logo="{TVN_LOGO}"', extinf[1])
        self.assertEqual(stats["logos_autorizados"], 2)
        self.assertTrue(validar_logos_tvn_autorizados(result))

    def test_tv_chile_geo_blocked_alias_also_uses_canonical_tvn_logo(self):
        reference = ["#EXTM3U"] + channel("TVN (1080p)", TVN_LOGO)
        current = ["#EXTM3U"]
        current += channel("TVN HD (LOCAL)", TVN_LOGO)
        current += channel(
            "TV Chile (1080p) [Geo-blocked]", "https://i.imgur.com/oYFto0V.png"
        )
        result, stats = blindar_logos(current, reference)
        extinf = [line for line in result if line.startswith("#EXTINF")]
        tvn_local = next(line for line in extinf if "TVN HD (LOCAL)" in line)
        tv_chile = next(line for line in extinf if "TV Chile (1080p)" in line)
        self.assertIn(f'tvg-logo="{TVN_LOGO}"', tvn_local)
        self.assertIn(f'tvg-logo="{TVN_LOGO}"', tv_chile)
        self.assertEqual(stats["logos_autorizados"], 2)
        self.assertTrue(validar_logos_tvn_autorizados(result))

    def test_other_existing_logo_is_preserved(self):
        other_logo = "https://example.com/other.png"
        reference = ["#EXTM3U"] + channel("Canal de prueba", other_logo)
        current = ["#EXTM3U"] + channel("Canal de prueba", "https://example.com/wrong.png")
        result, _ = blindar_logos(current, reference)
        extinf = next(line for line in result if line.startswith("#EXTINF"))
        self.assertIn(f'tvg-logo="{other_logo}"', extinf)


    def test_chile_tv_logo_is_frozen_by_channel_id_when_stream_url_rotates(self):
        logo = "https://logos.example/mega-original.png"
        reference = [
            "#EXTM3U",
            f'#EXTINF:-1 channelId="mega-cl" tvg-name="Mega" tvg-logo="{logo}" logo="{logo}" group-title="CHILE TV",Mega',
            "https://old.example/mega.m3u8",
        ]
        current = [
            "#EXTM3U",
            '#EXTINF:-1 channelId="mega-cl" tvg-name="Mega" tvg-logo="https://wrong.example/mega.png" logo="https://wrong.example/mega.png" group-title="CHILE TV",Mega',
            "https://new.example/mega.m3u8",
        ]
        result, _ = blindar_logos(current, reference)
        entry = next(line for line in result if line.startswith("#EXTINF"))
        self.assertIn(f'tvg-logo="{logo}"', entry)
        self.assertIn(f'logo="{logo}"', entry)
        self.assertTrue(validar_logos_chile_tv(result, reference))

    def test_manual_logo_override_is_easy_and_survives_chile_tv_validation(self):
        old_logo = "https://logos.example/mega-original.png"
        new_logo = "https://logos.example/mega-manual.png"
        reference = ["#EXTM3U"] + channel("Mega", old_logo)
        current = ["#EXTM3U"] + channel("Mega", "https://logos.example/mega-source.png")

        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "logos_autorizados.json"
            config.write_text(
                json.dumps({"logos": {"CHILE TV::Mega": new_logo}}),
                encoding="utf-8",
            )
            with patch("scripts.blindajes_principal.LOGOS_AUTORIZADOS_PATH", config):
                result, stats = blindar_logos(current, reference)
                entry = next(line for line in result if line.startswith("#EXTINF"))
                self.assertIn('tvg-logo="' + new_logo + '"', entry)
                self.assertEqual(stats["logos_autorizados"], 1)
                self.assertTrue(validar_logos_chile_tv(result, reference))

    def test_energeek_radio_keeps_its_exact_source_logo_in_chile_tv(self):
        logo = "https://cdn.m3u.cl/logo/1266_EnerGeek_Radio.png"
        reference = ["#EXTM3U"] + channel("Mega", "https://logos.example/mega.png")
        current = [
            "#EXTM3U",
            f'#EXTINF:-1 tvg-name="EnerGeek Radio ✪ | CL" tvg-logo="{logo}" logo="{logo}" group-title="CHILE TV",EnerGeek Radio ✪ | CL',
            "https://example.com/energeek-radio.m3u8",
        ]

        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "logos_autorizados.json"
            config.write_text(
                json.dumps({"logos": {"CHILE TV::EnerGeek Radio ✪ | CL": logo}}),
                encoding="utf-8",
            )
            with patch("scripts.blindajes_principal.LOGOS_AUTORIZADOS_PATH", config):
                result, stats = blindar_logos(current, reference)
                entry = next(line for line in result if line.startswith("#EXTINF"))
                self.assertIn('tvg-logo="' + logo + '"', entry)
                self.assertIn('logo="' + logo + '"', entry)
                self.assertEqual(stats["logos_autorizados"], 1)
                self.assertTrue(validar_logos_chile_tv(result, reference))

    def test_chile_tv_validator_rejects_any_unapproved_logo_change(self):
        reference = ["#EXTM3U"] + channel("Mega", "https://logos.example/mega.png")
        changed = ["#EXTM3U"] + channel("Mega", "https://logos.example/wrong.png")
        with self.assertRaisesRegex(AssertionError, "Logo alterado en CHILE TV"):
            validar_logos_chile_tv(changed, reference)

    def test_chile_tv_validator_rejects_logo_on_unmatched_new_channel(self):
        reference = ["#EXTM3U"] + channel("Mega", "https://logos.example/mega.png")
        current = [
            "#EXTM3U",
            '#EXTINF:-1 tvg-name="Canal nuevo" tvg-logo="https://logos.example/new.png" group-title="CHILE TV",Canal nuevo',
            "https://new.example/channel.m3u8",
        ]
        with self.assertRaisesRegex(AssertionError, "Logo no autorizado en señal nueva"):
            validar_logos_chile_tv(current, reference)


if __name__ == "__main__":
    unittest.main()

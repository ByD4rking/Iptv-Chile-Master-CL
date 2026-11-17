import re
import unittest
from pathlib import Path

import alimentar_principal as ap

PLAYLIST = Path("IPTV-CHILE-MAESTRA_CORREGIDO.m3u")
EXPECTED = [
    re.compile(r"^CNN Chile", re.I),
    re.compile(r"^24 Horas TVN", re.I),
    re.compile(r"^Meganoticias", re.I),
    re.compile(r"^TN(?:\s|$)", re.I),
    re.compile(r"^N\+ México", re.I),
    re.compile(r"^Noticias Caracol", re.I),
    re.compile(r"^RCN Noticias", re.I),
    re.compile(r"^TeleSUR$", re.I),
    re.compile(r"^CNN en Español", re.I),
    re.compile(r"^BBC News Mundo", re.I),
    re.compile(r"^DW Espa[nñ]ol|^DW Espanol", re.I),
    re.compile(r"^France 24 Español", re.I),
    re.compile(r"^Euronews Español", re.I),
    re.compile(r"^RTVE Canal 24 Horas", re.I),
    re.compile(r"^CGTN Español", re.I),
    re.compile(r"^Telemundo Noticias Ahora", re.I),
]


def informativos_names(lines):
    result = []
    for line in lines:
        if not line.startswith("#EXTINF"):
            continue
        group = re.search(r'group-title="([^"]*)"', line, re.I)
        if group and group.group(1).casefold() == "informativos":
            result.append(line.split(",", 1)[1].strip() if "," in line else "")
    return result


class InformativosOrderTests(unittest.TestCase):
    def test_priority_channels_are_contiguous_and_in_requested_order(self):
        entries = informativos_names(PLAYLIST.read_text(encoding="utf-8-sig").splitlines())
        self.assertTrue(entries, "No existe la categoría Informativos")
        self.assertEqual(entries[0], "CNN Chile")
        positions = []
        priority_positions = []
        for pattern in EXPECTED:
            found = [i for i, name in enumerate(entries) if pattern.search(name)]
            if found:
                positions.append(found[0])
                priority_positions.extend(found)
        self.assertEqual(positions, sorted(positions), "El orden prioritario de Informativos cambió")
        self.assertTrue(priority_positions, "No se encontraron canales prioritarios")
        last_priority = max(priority_positions)
        for name in entries[:last_priority + 1]:
            self.assertTrue(
                any(pattern.search(name) for pattern in EXPECTED),
                f"Canal no prioritario intercalado antes de cerrar el bloque prioritario: {name}",
            )

    def test_regional_signals_are_last(self):
        entries = informativos_names(PLAYLIST.read_text(encoding="utf-8-sig").splitlines())
        regional = [i for i, name in enumerate(entries) if ap.es_regional_informativos(name)]
        nonregional = [i for i, name in enumerate(entries) if not ap.es_regional_informativos(name)]
        if regional and nonregional:
            self.assertLess(max(nonregional), min(regional), "Hay señales regionales antes de canales no regionales")

    def test_country_folders_are_last_and_chile_tv_is_first(self):
        sample = ["#EXTM3U"]
        categories = [
            "Informativos", "Argentina 🇦🇷", "Anime", "CHILE TV", "Perú", "Música",
            "Ecuador", "Venezuela", "República Dominicana", "Paraguay", "Bolivia",
            "Nueva Zelanda", "Afganistán", "Tailandia",
        ]
        for category in categories:
            sample.extend([
                f'#EXTINF:-1 group-title="{category}",Canal de prueba',
                "https://example.com/channel.m3u8",
            ])
        ordered = ap.mover_paises_al_final(sample)
        actual = [
            re.search(r'group-title="([^"]*)"', line).group(1)
            for line in ordered if line.startswith("#EXTINF")
        ]
        self.assertEqual(actual, [
            "CHILE TV", "Informativos", "Anime", "Música", "Argentina 🇦🇷",
            "Perú", "Ecuador", "Venezuela", "República Dominicana", "Paraguay",
            "Bolivia", "Nueva Zelanda", "Afganistán", "Tailandia",
        ])

    def test_published_playlist_has_chile_first_and_country_blocks_at_the_end(self):
        lines = PLAYLIST.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(
            ap.mover_paises_al_final(lines),
            lines,
            "La maestra publicada todavía tiene carpetas de países intercaladas",
        )
        first = next(line for line in lines if line.startswith("#EXTINF"))
        self.assertIn('group-title="CHILE TV"', first)

    def test_prioritizer_keeps_options_and_moves_regional_signals_to_the_end(self):
        sample = ["#EXTM3U"]
        for category, name in [
            ("Informativos", "N+ Foro (Televisa) (Nacional)"),
            ("Informativos", "Telemundo Noticias Al día"),
            ("Informativos", "Telemundo Noticias Texas"),
            ("Argentina", "TN HD (Buenos Aires) [Opción 2]"),
            ("Argentina", "TN 🇦🇷"),
            ("México", "N+ México"),
            ("Informativos", "CNN en Español [Opción 2]"),
            ("Informativos", "CNN Chile"),
            ("Informativos", "RTVE Canal 24 Horas (España)"),
            ("Informativos", "TeleSUR"),
            ("Informativos", "Telesur | VE"),
            ("Informativos", "Telesur English | VE"),
            ("Informativos", "Telesur Costa Rica | CR"),
            ("Informativos", "Telemundo Noticias Ahora"),
            ("Informativos", "T13 En Vivo (Chile - Nacional)"),
            ("Informativos", "Canal 33 Tijuana (Baja California)"),
            ("Informativos", "Mi Radio"),
            ("Informativos", "Thema Coquimbo"),
            ("Informativos", "Meganoticias"),
        ]:
            sample.extend([
                f'#EXTINF:-1 group-title="{category}",{name}',
                "https://example.com/channel.m3u8",
            ])
        ordered = ap.ordenar_informativos(sample)
        names = informativos_names(ordered)
        for expected_name in (
            "TN HD (Buenos Aires) [Opción 2]",
            "TN 🇦🇷",
            "N+ México",
        ):
            extinf = next(
                line for line in ordered
                if line.startswith("#EXTINF") and line.endswith("," + expected_name)
            )
            self.assertIn('group-title="Informativos"', extinf)
        self.assertEqual(names, [
            "CNN Chile",
            "Meganoticias",
            "TN HD (Buenos Aires) [Opción 2]",
            "TN 🇦🇷",
            "N+ México",
            "TeleSUR",
            "CNN en Español [Opción 2]",
            "RTVE Canal 24 Horas (España)",
            "Telemundo Noticias Ahora",
            "N+ Foro (Televisa) (Nacional)",
            "T13 En Vivo (Chile - Nacional)",
            "Telesur English | VE",
            "Telemundo Noticias Al día",
            "Telemundo Noticias Texas",
            "Telesur | VE",
            "Telesur Costa Rica | CR",
            "Canal 33 Tijuana (Baja California)",
            "Mi Radio",
            "Thema Coquimbo",
        ])

    def test_general_is_absent_from_principal(self):
        lines = PLAYLIST.read_text(encoding="utf-8-sig").splitlines()
        general = [
            line for line in lines
            if line.startswith("#EXTINF")
            and re.search(r'group-title="General"', line, re.I)
        ]
        self.assertEqual(general, [], "La categoría General no debe existir")

    def test_audaz_tv_is_reclassified_as_religious(self):
        sample = [
            "#EXTM3U",
            '#EXTINF:-1 group-title="General" tvg-logo="https://example.com/logo.png",Vivo TV',
            "https://cloud2.streaminglivehd.com:1936/8264/8264/playlist.m3u8",
            '#EXTINF:-1 group-title="Religiosos",Canal religioso',
            "https://example.com/religioso.m3u8",
        ]
        result = ap.blindar_categoria_general(sample)
        self.assertIn('group-title="Religiosos"', result[1])
        self.assertIn("Audaz TV (Venezuela)", result[1])
        self.assertFalse(any(re.search(r'group-title="General"', line, re.I) for line in result))

    def test_news_theme_overrides_source_country(self):
        destination = ap.determinar_destino("Argentina", "TN 🇦🇷", "argentina", ["Informativos", "Argentina"])
        self.assertEqual(destination, "Informativos")

    def test_unknown_general_channel_blocks_generation(self):
        sample = [
            "#EXTM3U",
            '#EXTINF:-1 group-title="General",Canal sin país',
            "https://example.com/unknown.m3u8",
        ]
        with self.assertRaises(RuntimeError):
            ap.blindar_categoria_general(sample)


if __name__ == "__main__":
    unittest.main()

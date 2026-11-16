import re
import unittest
from pathlib import Path

PLAYLIST = Path("IPTV-CHILE-MAESTRA_CORREGIDO.m3u")
EXPECTED = [
    re.compile(r"^CNN Chile$"),
    re.compile(r"^24 Horas TVN"),
    re.compile(r"^Meganoticias$"),
    re.compile(r"^TN"),
    re.compile(r"^N\+ México$"),
    re.compile(r"^RCN Noticias$"),
    re.compile(r"^TeleSUR$"),
    re.compile(r"^CNN en Español"),
    re.compile(r"^DW Espa[nñ]ol|^DW Espanol"),
    re.compile(r"^France 24 Español$"),
    re.compile(r"^Euronews Español$"),
    re.compile(r"^RTVE Canal 24 Horas"),
    re.compile(r"^CGTN Español"),
    re.compile(r"^Telemundo Noticias Ahora$"),
]

class InformativosOrderTests(unittest.TestCase):
    def test_priority_channels_are_first_and_ordered(self):
        entries = []
        for line in PLAYLIST.read_text(encoding="utf-8").splitlines():
            if not line.startswith("#EXTINF"):
                continue
            group = re.search(r'group-title="([^"]*)"', line, re.I)
            if not group or group.group(1).casefold() != "informativos":
                continue
            entries.append(line.split(",", 1)[1].strip() if "," in line else "")
        self.assertTrue(entries, "No existe la categoría Informativos")
        self.assertEqual(entries[0], "CNN Chile")
        positions = []
        for pattern in EXPECTED:
            found = next((i for i, name in enumerate(entries) if pattern.search(name)), None)
            self.assertIsNotNone(found, f"Falta canal prioritario: {pattern.pattern}")
            positions.append(found)
        self.assertEqual(positions, sorted(positions), "El orden prioritario de Informativos cambió")

if __name__ == "__main__":
    unittest.main()

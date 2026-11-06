#!/usr/bin/env python3
"""Protege la identidad de logos de las familias IPTV corregidas."""
import re
import unittest
from pathlib import Path

PLAYLIST = Path(__file__).resolve().parents[1] / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u"
ATTR = re.compile(r'\b(tvg-logo|logo)="([^"]*)"')

def load_rows():
    rows = []
    for line in PLAYLIST.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.startswith("#EXTINF:"):
            continue
        attrs = {key: value for key, value in ATTR.findall(line)}
        group = re.search(r'\bgroup-title="([^"]*)"', line)
        rows.append({
            "name": line.split(",", 1)[1].strip() if "," in line else "",
            "group": group.group(1) if group else "",
            "logo": attrs.get("tvg-logo") or attrs.get("logo") or "",
        })
    return rows

class LogoIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_rows()

    def family(self, group, prefix, minimum):
        rows = [r for r in self.rows if r["group"] == group and r["name"].casefold().startswith(prefix.casefold())]
        self.assertGreaterEqual(len(rows), minimum, f"faltan variantes de {prefix}: {len(rows)}")
        logos = {r["logo"] for r in rows}
        self.assertEqual(len(logos), 1, f"las variantes de {prefix} no comparten logo: {logos}")
        logo = next(iter(logos))
        self.assertTrue(logo.startswith(("http://", "https://")), f"logo inválido para {prefix}")
        self.assertNotIn("dummyimage.com", logo, f"placeholder en {prefix}")

    def test_familias_chile(self):
        self.family("CHILE TV", "Mega HD (Nacional)", 3)
        self.family("CHILE TV", "La Red", 4)
        self.family("CHILE TV", "ChileVisión HD", 4)
        self.family("CHILE TV", "TVN HD (Nacional)", 5)

    def test_bitme_y_locomotion(self):
        self.family("Anime", "Bitme HD (México)", 3)
        self.family("Anime", "Canal Locomotion", 5)

    def test_energeek_fan_usa_logo_consistente(self):
        rows = [r for r in self.rows if "energeek fan" in r["name"].casefold()]
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(len({r["logo"] for r in rows}), 1)
        self.assertTrue(all(r["logo"].startswith(("http://", "https://")) for r in rows))

    def test_canales_pedidos_tienen_logo_real(self):
        for group, name in [("Competencia", "Fear Factor"), ("Anime", "Primired Anime")]:
            rows = [r for r in self.rows if r["group"] == group and name.casefold() in r["name"].casefold()]
            self.assertTrue(rows, f"no se encontró {name}")
            for row in rows:
                self.assertTrue(row["logo"].startswith(("http://", "https://")))
                self.assertNotIn("dummyimage.com", row["logo"])

if __name__ == "__main__":
    unittest.main()

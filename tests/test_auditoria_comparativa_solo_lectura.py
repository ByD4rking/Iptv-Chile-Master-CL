import tempfile
import unittest
from pathlib import Path

from scripts.auditoria_comparativa_solo_lectura import (
    classify_error, compare, parse_playlist,
)


class AuditoriaComparativaSoloLecturaTests(unittest.TestCase):
    def write(self, folder, name, text):
        path = Path(folder) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_detecta_cambio_tvg_logo_sin_confundirlo_con_logo_legacy(self):
        with tempfile.TemporaryDirectory() as folder:
            before = self.write(folder, "before.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="canal.1" tvg-logo="https://a/logo.png" group-title="Chile",Canal Uno\nhttps://stream/a\n')
            after = self.write(folder, "after.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="canal.1" tvg-logo="https://b/logo.png" group-title="Chile",Canal Uno\nhttps://stream/a\n')
            result = compare(parse_playlist(before), parse_playlist(after))
            self.assertEqual(result["logo_changed_channels"], 1)
            self.assertIn("tvg_logo", result["logo_changes"][0]["logo_changes"])
            self.assertNotIn("legacy_logo", result["logo_changes"][0]["logo_changes"])

    def test_playlist_identica_no_reporta_cambios(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "same.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="id1" tvg-logo="https://a/logo.png",Canal\nhttps://stream/a\n')
            result = compare(parse_playlist(path), parse_playlist(path))
            self.assertEqual(result["logo_changed_channels"], 0)
            self.assertEqual(result["added"], 0)
            self.assertEqual(result["removed"], 0)

    def test_clasifica_restricciones_y_transitorios_sin_marcar_caida_permanente(self):
        self.assertEqual(classify_error("HTTP 403 Forbidden"), "restriccion_acceso")
        self.assertEqual(classify_error("Timeout al conectar"), "transitorio")
        self.assertEqual(classify_error("HTTP 404 Not Found"), "permanente_confirmado")
        self.assertEqual(classify_error("respuesta no contiene cabecera #EXTM3U"), "respuesta_invalida")


if __name__ == "__main__":
    unittest.main()

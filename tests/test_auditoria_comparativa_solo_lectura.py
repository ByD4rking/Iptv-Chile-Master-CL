import json
import tempfile
import unittest
from pathlib import Path

from scripts.auditoria_comparativa_solo_lectura import (
    classify_error,
    classify_source_report,
    compare_playlists,
    parse_playlist,
)


class AuditoriaComparativaSoloLecturaTests(unittest.TestCase):
    def write(self, folder, name, content):
        path = Path(folder) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_detecta_tvg_logo_y_logo_legacy_por_separado(self):
        with tempfile.TemporaryDirectory() as folder:
            before = self.write(folder, "before.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="canal.1" tvg-logo="https://a/logo.png" logo="https://a/legacy.png" group-title="Chile",Canal Uno\nhttps://stream/a\n')
            after = self.write(folder, "after.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="canal.1" tvg-logo="https://b/logo.png" logo="https://a/legacy.png" group-title="Chile",Canal Uno\nhttps://stream/a\n')
            result = compare_playlists(parse_playlist(before), parse_playlist(after))
            self.assertEqual(result["logo_changed_channels"], 1)
            changes = result["logo_changes"][0]["logo_changes"]
            self.assertIn("tvg_logo", changes)
            self.assertNotIn("logo", changes)

    def test_detecta_cambio_de_logo_legacy_aunque_tvg_logo_no_cambie(self):
        with tempfile.TemporaryDirectory() as folder:
            before = self.write(folder, "before.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="canal.2" tvg-logo="https://a/logo.png" logo="https://a/legacy.png",Canal Dos\nhttps://stream/a\n')
            after = self.write(folder, "after.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="canal.2" tvg-logo="https://a/logo.png" logo="https://b/legacy.png",Canal Dos\nhttps://stream/a\n')
            result = compare_playlists(parse_playlist(before), parse_playlist(after))
            self.assertEqual(set(result["logo_changes"][0]["logo_changes"]), {"logo"})

    def test_playlist_identica_no_reporta_cambios(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.write(folder, "same.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="id1" tvg-logo="https://a/logo.png",Canal\nhttps://stream/a\n')
            result = compare_playlists(parse_playlist(path), parse_playlist(path))
            self.assertEqual(result["logo_changed_channels"], 0)
            self.assertEqual(result["added"], 0)
            self.assertEqual(result["removed"], 0)

    def test_detecta_altas_y_bajas_sin_reescribir_nada(self):
        with tempfile.TemporaryDirectory() as folder:
            before = self.write(folder, "before.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="old",Canal Antiguo\nhttps://stream/a\n')
            after = self.write(folder, "after.m3u",
                '#EXTM3U\n#EXTINF:-1 tvg-id="new",Canal Nuevo\nhttps://stream/b\n')
            original = before.read_bytes()
            result = compare_playlists(parse_playlist(before), parse_playlist(after))
            self.assertEqual(result["added"], 1)
            self.assertEqual(result["removed"], 1)
            self.assertEqual(before.read_bytes(), original)

    def test_un_404_aislado_no_se_confirma_hasta_repetirse(self):
        self.assertEqual(classify_error("HTTP 404 Not Found", 1), "permanente_candidato")
        self.assertEqual(classify_error("HTTP 404 Not Found", 2), "permanente_confirmado")
        self.assertEqual(classify_error("HTTP 410 Gone", 3), "permanente_confirmado")

    def test_restricciones_y_fallos_transitorios_no_son_permanentes(self):
        self.assertEqual(classify_error("HTTP 403 Forbidden"), "restriccion_acceso")
        self.assertEqual(classify_error("HTTP 401 Unauthorized"), "restriccion_acceso")
        self.assertEqual(classify_error("Timeout al conectar"), "transitorio")
        self.assertEqual(classify_error("HTTP 503 Service Unavailable"), "transitorio")
        self.assertEqual(classify_error("HTTP 429 Too Many Requests"), "transitorio")

    def test_respuesta_m3u_invalida_se_distingue_de_stream_caido(self):
        self.assertEqual(classify_error("respuesta no contiene cabecera #EXTM3U"), "respuesta_invalida")
        self.assertEqual(classify_error("HTTP 200 content-type text/html"), "respuesta_invalida")

    def test_reporte_clasifica_observaciones_y_redacta_tokens(self):
        report = {
            "errors": [
                {"source": "A", "error": "HTTP 404 https://example.test/list.m3u?jwt=secret", "observations": 1},
                {"source": "B", "error": "HTTP 404 Not Found", "observations": 3},
            ]
        }
        rows = classify_source_report(report)
        self.assertEqual(rows[0]["classification"], "permanente_candidato")
        self.assertEqual(rows[1]["classification"], "permanente_confirmado")
        self.assertNotIn("secret", rows[0]["detail"])
        self.assertIn("jwt=%2A%2A%2A", rows[0]["detail"])


if __name__ == "__main__":
    unittest.main()

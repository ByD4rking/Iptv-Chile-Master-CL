import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from m3ucl_html_fallback import build_latam_m3u
import alimentar_principal as ap
import auditar_fuentes as af
from unittest.mock import patch


def cell(channel_id, name, url, category="Peliculas y Series", logo="//cdn.m3u.cl/logo/test.png"):
    encoded = base64.b64encode(url.encode("utf-8")).decode("ascii")
    return (
        "<td class='videojs' "
        f"reproducir_canal='{encoded}' "
        f"reproducir_nombre_canal='{name}' "
        f"reproducir_logo_canal='{logo}' "
        f"id_canal='{channel_id}' nombre_lista='LATAM' "
        f"nombre_categoria='{category}'></td>"
    )


class M3UCLHtmlFallbackTests(unittest.TestCase):
    def test_rebuilds_valid_m3u_with_metadata_and_decoded_stream(self):
        html = "<table><tr>" + cell(
            "123", "Canal LATAM", "https://stream.example/live.m3u8"
        ) + "</tr></table>"

        result = build_latam_m3u(html).decode("utf-8")

        self.assertTrue(result.startswith("#EXTM3U\n"))
        self.assertIn('tvg-id="m3ucl-latam-123"', result)
        self.assertIn('tvg-logo="https://cdn.m3u.cl/logo/test.png"', result)
        self.assertIn('group-title="Peliculas y Series"', result)
        self.assertIn("Canal LATAM", result)
        self.assertIn("https://stream.example/live.m3u8", result)

    def test_deduplicates_repeated_rows_by_provider_channel_id(self):
        html = "<table>" + cell("123", "Canal", "https://stream.example/a.m3u8") + cell(
            "123", "Canal", "https://stream.example/a.m3u8"
        ) + "</table>"

        result = build_latam_m3u(html).decode("utf-8")

        self.assertEqual(result.count("#EXTINF:"), 1)

    def test_rejects_non_http_streams_and_missing_channel_rows(self):
        html = "<table>" + cell("123", "Canal", "javascript:alert(1)") + "</table>"
        with self.assertRaisesRegex(ValueError, "no contiene canales utilizables"):
            build_latam_m3u(html)

    def test_keeps_ampersands_and_quotes_safe_in_m3u_attributes(self):
        html = "<table>" + cell(
            "124", 'Canal "Uno"', "https://stream.example/live.m3u8",
            category='Musica & TV', logo="//cdn.m3u.cl/logo/a.png"
        ) + "</table>"

        result = build_latam_m3u(html).decode("utf-8")

        self.assertIn('tvg-name="Canal &quot;Uno&quot;"', result)
        self.assertIn('group-title="Musica &amp; TV"', result)

    def test_preserves_distinct_stream_options_for_same_provider_channel(self):
        html = "<table>" + cell(
            "123", "Canal", "https://stream.example/primary.m3u8"
        ) + cell(
            "123", "Canal", "https://stream.example/alternate.m3u8"
        ) + "</table>"

        result = build_latam_m3u(html).decode("utf-8")

        self.assertEqual(result.count("#EXTINF:"), 2)
        self.assertIn("https://stream.example/primary.m3u8", result)
        self.assertIn("https://stream.example/alternate.m3u8", result)

    def test_principal_uses_official_page_when_static_latam_file_is_missing(self):
        page = "<table>" + cell(
            "321", "Canal de prueba", "https://stream.example/latam.m3u8"
        ) + "</table>"

        class Response:
            status_code = 200
            def __init__(self, text):
                self.text = text
                self.url = "https://m3u.cl/lista-iptv-latam.php"
            def raise_for_status(self):
                return None

        class Session:
            def __init__(self):
                self.responses = [Response("Warning: missing file")] * 3 + [Response(page)]
                self.calls = []
            def get(self, url, timeout=30, headers=None):
                self.calls.append(url)
                return self.responses.pop(0)

        session = Session()
        response = ap.obtener_respuesta_fuente(session, "https://m3u.cl/lista/LATAM.m3u")

        self.assertTrue(response.text.startswith("#EXTM3U"))
        self.assertIn("https://stream.example/latam.m3u8", response.text)
        self.assertEqual(session.calls[-1], "https://m3u.cl/lista-iptv-latam.php")

    def test_source_audit_uses_official_page_fallback(self):
        page = ("<table>" + cell(
            "654", "Canal auditoria", "https://stream.example/audit.m3u8"
        ) + "</table>").encode("utf-8")

        class HttpResponse:
            def __init__(self, data):
                self.data = data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size=-1):
                return self.data[:size]

        responses = [
            HttpResponse(b"Warning: missing file"),
            HttpResponse(b"Warning: missing file"),
            HttpResponse(b"Warning: missing file"),
            HttpResponse(page),
        ]
        with patch.object(af, "urlopen", side_effect=responses), patch.object(af.time, "sleep"):
            result = af.fetch_url("https://m3u.cl/lista/LATAM.m3u")

        self.assertTrue(result.startswith(b"#EXTM3U"))
        self.assertIn(b"https://stream.example/audit.m3u8", result)


if __name__ == "__main__":
    unittest.main()

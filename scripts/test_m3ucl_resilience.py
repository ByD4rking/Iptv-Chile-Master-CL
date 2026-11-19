import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import alimentar_principal as ap


class Response:
    def __init__(self, status=200, text="#EXTM3U\n"):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, timeout=30, headers=None):
        self.calls.append({"url": url, "timeout": timeout, "headers": headers})
        result = self.responses.pop(0)
        return result


class M3UCLResilienceTests(unittest.TestCase):
    def test_m3ucl_retries_normal_header_variants_until_valid_m3u(self):
        session = Session([
            Response(403, "Forbidden"),
            Response(403, "Forbidden"),
            Response(200, "#EXTM3U\n#EXTINF:-1,Canal Chile\nhttps://example.test/live.m3u8\n"),
        ])
        response = ap.obtener_respuesta_fuente(
            session, "https://m3u.cl/lista/CL.m3u"
        )
        self.assertTrue(response.text.startswith("#EXTM3U"))
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(session.calls[1]["headers"]["Referer"], "https://m3u.cl/")
        self.assertEqual(session.calls[2]["headers"]["Referer"], "https://m3u.cl/")

    def test_m3ucl_does_not_accept_html_or_error_body_as_playlist(self):
        session = Session([
            Response(200, "<html>Access denied</html>"),
            Response(200, "Forbidden"),
            Response(200, "Not an M3U"),
        ])
        with self.assertRaisesRegex(RuntimeError, "no entregó una playlist válida"):
            ap.obtener_respuesta_fuente(
                session, "https://m3u.cl/lista/CL.m3u"
            )
        self.assertEqual(len(session.calls), 3)

    def test_other_sources_keep_their_existing_single_request_behavior(self):
        session = Session([Response(200, "#EXTM3U\n")])
        response = ap.obtener_respuesta_fuente(
            session, "https://example.org/playlist.m3u"
        )
        self.assertTrue(response.text.startswith("#EXTM3U"))
        self.assertEqual(len(session.calls), 1)
        self.assertIsNone(session.calls[0]["headers"])


if __name__ == "__main__":
    unittest.main()

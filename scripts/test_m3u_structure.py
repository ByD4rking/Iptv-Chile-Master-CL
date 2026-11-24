"""Pruebas de validación estructural M3U: aceptar listas reales y rechazar HTML/truncadas."""
import unittest

from scripts.m3u_structure import normalize_m3u_bytes, validate_m3u_bytes


class M3UStructureTests(unittest.TestCase):
    def test_normaliza_bom_crlf_y_espacios_sin_cambiar_canales(self):
        raw = b"\xef\xbb\xbf  \r\n#EXTM3U  \r\n#EXTINF:-1, Canal Uno  \r\nhttps://stream.example/uno.m3u8  \r\n"
        normalized = normalize_m3u_bytes(raw)
        self.assertTrue(normalized.startswith(b"#EXTM3U\n"))
        self.assertEqual(validate_m3u_bytes(normalized), 1)
        self.assertIn(b"https://stream.example/uno.m3u8\n", normalized)
        self.assertNotIn(b"\r", normalized)

    def test_rechaza_bytes_utf8_corruptos(self):
        with self.assertRaisesRegex(ValueError, "UTF-8 válido"):
            normalize_m3u_bytes(b"#EXTM3U\n#EXTINF:-1,Canal\nhttps://x.test/\xff\n")

    def test_acepta_playlist_con_directivas_entre_extinf_y_uri(self):
        data = (
            b"#EXTM3U\n"
            b'#EXTINF:-1 tvg-id="uno",Canal Uno\n'
            b"#EXTVLCOPT:http-reconnect=true\n"
            b"https://stream.example/uno.m3u8\n"
            b'#EXTINF:-1,Canal Dos\n'
            b"https://stream.example/dos.m3u8\n"
        )
        self.assertEqual(validate_m3u_bytes(data), 2)

    def test_rechaza_respuesta_vacia(self):
        with self.assertRaisesRegex(ValueError, "vacía"):
            validate_m3u_bytes(b"")

    def test_rechaza_html_aunque_tenga_contenido(self):
        with self.assertRaisesRegex(ValueError, "HTML"):
            validate_m3u_bytes(b"<!doctype html><html><body>403</body></html>")

    def test_rechaza_cabecera_ausente_o_no_inicial(self):
        with self.assertRaisesRegex(ValueError, "cabecera"):
            validate_m3u_bytes(b"respuesta de error sin cabecera\n")
    
    def test_rechaza_extinf_sin_uri(self):
        with self.assertRaisesRegex(ValueError, "sin URI"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTINF:-1,Canal\n#EXTINF:-1,Otro\nhttps://x.test/live.m3u8\n")

    def test_acepta_esquemas_iptv_no_http(self):
        self.assertEqual(validate_m3u_bytes(
            b"#EXTM3U\n#EXTINF:-1,Canal RTSP\nrtsp://stream.example/live\n"
            b"#EXTINF:-1,Canal RTMP\nrtmp://stream.example/live\n"
        ), 2)

    def test_rechaza_esquema_no_admitido(self):
        with self.assertRaisesRegex(ValueError, "URI de canal inválida"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTINF:-1,Canal\njavascript://alert\n")

    def test_rechaza_uri_sin_esquema(self):
        with self.assertRaisesRegex(ValueError, "URI de canal inválida"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTINF:-1,Canal\nstream.example/live\n")

    def test_rechaza_cabecera_m3u_con_sufijo_invalido(self):
        with self.assertRaisesRegex(ValueError, "cabecera"):
            validate_m3u_bytes(b"#EXTM3Ugarbage\n#EXTINF:-1,Canal\nhttps://x.test/live\n")

    def test_rechaza_ruido_antes_del_primer_canal(self):
        data = b"#EXTM3U\nrespuesta 403 del servidor\n#EXTINF:-1,Canal\nhttps://x.test/live\n"
        with self.assertRaisesRegex(ValueError, "contenido suelto"):
            validate_m3u_bytes(data)

    def test_rechaza_ruido_entre_canales(self):
        data = (b"#EXTM3U\n#EXTINF:-1,Canal Uno\nhttps://x.test/uno\n"
                b"texto inesperado\n#EXTINF:-1,Canal Dos\nhttps://x.test/dos\n")
        with self.assertRaisesRegex(ValueError, "contenido suelto"):
            validate_m3u_bytes(data)

    def test_rechaza_uri_suelta_sin_extinf(self):
        with self.assertRaisesRegex(ValueError, "contenido suelto"):
            validate_m3u_bytes(b"#EXTM3U\nhttps://x.test/orphan\n#EXTINF:-1,Canal\nhttps://x.test/live\n")

    def test_rechaza_uri_http_sin_host(self):
        with self.assertRaisesRegex(ValueError, "URI de canal inválida"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTINF:-1,Canal\nhttps:///sin-host\n")

    def test_no_expone_tokens_en_mensajes_de_error(self):
        data = b"#EXTM3U\n#EXTINF:-1,Canal\ntexto-no-es-uri\n"
        with self.assertRaises(ValueError) as ctx:
            validate_m3u_bytes(data, source="https://cdn.example/list.m3u?jwt=super-secret")
        self.assertNotIn("super-secret", str(ctx.exception))
        self.assertIn("cdn.example", str(ctx.exception))
    def test_rechaza_extinf_con_duracion_no_numerica(self):
        with self.assertRaisesRegex(ValueError, "duración #EXTINF inválida"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTINF:abc,Canal\nhttps://x.test/live\n")

    def test_rechaza_etiqueta_extinf_mal_formada(self):
        with self.assertRaisesRegex(ValueError, "etiqueta #EXTINF mal formada"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTINFmal,Canal\nhttps://x.test/live\n")
    def test_rechaza_lista_sin_canales(self):
        with self.assertRaisesRegex(ValueError, "no contiene pares"):
            validate_m3u_bytes(b"#EXTM3U\n#EXTVLCOPT:http-reconnect=true\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)

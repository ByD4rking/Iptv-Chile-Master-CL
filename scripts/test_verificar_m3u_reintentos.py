#!/usr/bin/env python3
"""Pruebas deterministas de reintentos del verificador IPTV."""

import unittest
from unittest.mock import patch
import requests
import verificar_m3u
import aprendizaje


class ReintentosVerificadorTests(unittest.TestCase):
    def canal(self):
        return {"url": "https://iptv.example/live.m3u8", "nombre": "Canal test"}

    @patch("verificar_m3u.time.sleep")
    @patch("verificar_m3u._intentar_una_vez")
    def test_reintenta_error_de_conexion_transitorio(self, intento, dormir):
        intento.side_effect = [requests.ConnectionError("reset TCP"), ("OK", None, 200)]
        resultado = verificar_m3u.verificar_canal(
            self.canal(), timeout=2, reintentos=2, espera_reintento=0.5
        )
        self.assertEqual(resultado["estado"], "OK")
        self.assertEqual(intento.call_count, 2)
        dormir.assert_called_once_with(0.5)

    def test_historial_aprendizaje_se_lee_una_vez_por_ejecucion(self):
        aprendizaje.cargar.cache_clear()
        with patch.object(aprendizaje.ARCHIVO, "exists", return_value=True), patch.object(
            aprendizaje.ARCHIVO, "read_text",
            return_value='{"_meta":{"version":2},"https://iptv.example/live":{"n":1,"ok":1,"fail":0,"last":"2026-10-09T00:00:00+00:00"}}',
        ) as lectura:
            aprendizaje.cargar()
            aprendizaje.cargar()
            self.assertEqual(lectura.call_count, 1)
        aprendizaje.cargar.cache_clear()

    @patch("verificar_m3u.time.sleep")
    @patch("verificar_m3u._intentar_una_vez")
    def test_backoff_exponencial(self, intento, dormir):
        intento.side_effect = [
            requests.Timeout("timeout 1"),
            requests.Timeout("timeout 2"),
            requests.Timeout("timeout 3"),
        ]
        resultado = verificar_m3u.verificar_canal(
            self.canal(), timeout=1, reintentos=2, espera_reintento=0.25
        )
        self.assertEqual(resultado["estado"], "ERROR")
        self.assertEqual(intento.call_count, 3)
        self.assertEqual([c.args[0] for c in dormir.call_args_list], [0.25, 0.5])


if __name__ == "__main__":
    unittest.main(verbosity=2)

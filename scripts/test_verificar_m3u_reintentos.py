#!/usr/bin/env python3
"""Pruebas deterministas de reintentos del verificador IPTV."""

import unittest
from unittest.mock import patch
import requests
import verificar_m3u


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

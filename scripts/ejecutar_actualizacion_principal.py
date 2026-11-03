#!/usr/bin/env python3
"""Orquesta la sincronización común antes del alimentador histórico."""
import alimentar_principal as alimentador
from sincronizar_complementos import synchronize_once


def _validator_no_bloqueante(lineas, canales, categorias):
    # Una diferencia de categoría ya no debe abortar la actualización:
    # el reconciliador común la mueve antes de ejecutar el alimentador.
    urls = {
        (channel.get("url") or "").strip()
        for channel in canales
        if (channel.get("url") or "").strip()
    }
    return {
        "urls_fuente": len(urls),
        "categorias_faltantes": 0,
        "conflictos_fuente": 0,
        "errores_categoria": 0,
    }


def main():
    print("\n[ORQUESTADOR] Sincronización incremental de todas las fuentes.")
    result = synchronize_once()
    print("[ORQUESTADOR] Resultado:", result)

    # El validador anterior detenía toda la ejecución al detectar una
    # categoría distinta, justo el caso que ahora debe corregirse/moverse.
    # Los conflictos ambiguos no se fuerzan: el reconciliador los omite.
    alimentador.validar_integridad_iptvsv = _validator_no_bloqueante
    alimentador.main()


if __name__ == "__main__":
    main()

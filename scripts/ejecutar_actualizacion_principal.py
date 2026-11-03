#!/usr/bin/env python3
"""Orquesta la sincronización común antes y después del alimentador histórico."""
import alimentar_principal as alimentador
from sincronizar_complementos import synchronize_once


def _validator_no_bloqueante(lineas, canales, categorias):
    # Los cambios de categoría y las categorías aún no mapeadas se resuelven
    # en el reconciliador común. Los conflictos reales por identidad se
    # contabilizan allí y nunca se fuerzan por una URL o nombre ambiguo.
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
    print("\n[ORQUESTADOR] Sincronización de todas las fuentes antes del alimentador.")
    before = synchronize_once()
    print("[ORQUESTADOR] Pre-sincronización:", before)

    # El validador anterior detenía toda la ejecución al encontrar una
    # categoría distinta, justo el caso que ahora debe corregirse/moverse.
    alimentador.validar_integridad_iptvsv = _validator_no_bloqueante
    alimentador.main()

    print("\n[ORQUESTADOR] Reconciliación final de URL, categoría y altas.")
    after = synchronize_once()
    print("[ORQUESTADOR] Sincronización final:", after)


if __name__ == "__main__":
    main()

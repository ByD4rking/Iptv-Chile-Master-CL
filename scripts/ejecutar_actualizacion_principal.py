#!/usr/bin/env python3
"""Sincroniza fuentes nuevas antes de ejecutar el alimentador histórico.

La primera reconciliación crea categorías nuevas y mueve los canales por
identidad. Después, el alimentador aplica sus validaciones y mantenimiento
histórico usando ya las categorías reconciliadas. El workflow vuelve a
reconciliar al final para dejar los cambios de fuentes en el resultado final.
"""
from sincronizar_complementos import synchronize_once
import alimentar_principal as alimentador


def main():
    print("\\n[ORQUESTADOR] Sincronización incremental previa.")
    result = synchronize_once()
    print("[ORQUESTADOR] Resultado previo:", result)
    alimentador.main()


if __name__ == "__main__":
    main()

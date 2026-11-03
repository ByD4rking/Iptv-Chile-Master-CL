#!/usr/bin/env python3
"""Ejecuta el alimentador histórico y luego la reconciliación incremental.

El alimentador histórico conserva su propia auditoría del orden original. Por
eso corre primero sobre la maestra sin premodificaciones; después el
sincronizador actualiza URLs, categorías y canales nuevos sin reordenar los
bloques existentes. El workflow vuelve a reconciliar después de unificar CHILE.
"""
import alimentar_principal as alimentador
from sincronizar_complementos import synchronize_once


def main():
    print("\n[ORQUESTADOR] Ejecutando alimentador histórico con su auditoría de orden.")
    alimentador.main(restaurar_faltantes=False)

    print("\n[ORQUESTADOR] Reconciliando fuentes complementarias.")
    result = synchronize_once()
    print("[ORQUESTADOR] Resultado de sincronización:", result)
    return result


if __name__ == "__main__":
    main()

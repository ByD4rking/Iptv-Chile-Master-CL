#!/usr/bin/env python3
"""Ejecuta el alimentador histórico; la reconciliación unificada corre al final.

El orden es intencional: primero se ejecutan las validaciones y protecciones
históricas del alimentador; después el workflow sincroniza las fuentes nuevas
sin reorganizar los bloques que ya existen en la playlist principal.
"""
import alimentar_principal as alimentador


def main():
    alimentador.main()


if __name__ == "__main__":
    main()

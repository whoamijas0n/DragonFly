#!/usr/bin/env python3
"""
DragonFly System - Red Team Toolbox (Raspberry Pi Edition)
Punto de entrada para Raspberry Pi Zero 2 WH con pantalla táctil de 320x240 en Raspberry Pi OS Lite.
"""

import sys
import os

# Asegurar que el directorio de trabajo sea la raíz del proyecto para rutas relativas
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.chdir(PROJECT_DIR)

from dragonfly.ui.raspi.app import run_raspi_app

if __name__ == "__main__":
    run_raspi_app()

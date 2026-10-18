#!/usr/bin/env python3
"""
DragonFly System - Red Team Toolbox (Desktop Edition)
Punto de entrada para estaciones de trabajo Linux (Kali, Parrot, Ubuntu, Arch, Fedora).
"""

import sys
import os

# Asegurar que la raíz del proyecto esté en el PYTHONPATH
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from dragonfly.core.subprocess_utils import ignore_job_control_signals
from dragonfly.ui.desktop.app import run_desktop_app

# Evita que sudo/hijos con use_pty congelen la interfaz con SIGTTIN/SIGTTOU.
ignore_job_control_signals()

if __name__ == "__main__":
    run_desktop_app()

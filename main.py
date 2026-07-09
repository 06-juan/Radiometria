# main.py
"""
Punto de entrada de la aplicación de Radiometría Fototérmica.

Uso:
    python main.py             # Intenta conectar hardware real
    python main.py --sim       # Fuerza modo simulación sin hardware
"""

import sys
import argparse

from PyQt6.QtWidgets import QApplication
from src.ui.orchestrator import MeasurementOrchestrator


def main():
    # Separar argumentos de Qt de los nuestros
    parser = argparse.ArgumentParser(
        description="Radiometría Fototérmica — Control de mesa XY y lock-in SR830"
    )
    parser.add_argument(
        "--sim",
        action="store_true",
        help="Activar modo simulación sin hardware real (Arduino / SR830)",
    )
    args, qt_args = parser.parse_known_args()

    app = QApplication(qt_args)
    window = MeasurementOrchestrator(sim_mode=args.sim)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

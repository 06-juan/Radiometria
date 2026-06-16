# main.py
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.orchestrator import MeasurementOrchestrator

if __name__ == "__main__":
    app = QApplication(sys.path)
    window = MeasurementOrchestrator()
    window.show()
    sys.exit(app.exec())

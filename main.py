import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())

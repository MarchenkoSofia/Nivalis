import sys
import os

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PyQt6.QtWidgets import QApplication
from nivalis.platform_win import init_display_awareness
from nivalis.overlay import NivalisOverlay

def main():
    init_display_awareness()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _overlay = NivalisOverlay()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
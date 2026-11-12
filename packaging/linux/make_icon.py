"""Рисует PNG-иконку приложения (для AppImage / .desktop)."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from PyQt6.QtGui import QGuiApplication  # noqa: E402
from nivalis.tray import generate_icon_pixmap  # noqa: E402

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "nivalis.png"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    app = QGuiApplication(sys.argv)
    if not generate_icon_pixmap(size).save(out, "PNG"):
        sys.exit(f"не удалось сохранить {out}")
    print(out)

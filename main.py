import sys
import os

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

if sys.platform.startswith("linux"):
    # Wayland не даёт обычным приложениям ни держать окно поверх всех, ни видеть
    # чужие окна. Через XWayland оверлей работает как в X11-сессии.
    if (os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY")
            and not os.environ.get("QT_QPA_PLATFORM")):
        os.environ["QT_QPA_PLATFORM"] = "xcb"

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from nivalis.platform import init_display_awareness, check_environment
from nivalis.overlay import NivalisOverlay

INSTANCE_KEY = "nivalis-single-instance"


def _already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    alive = sock.waitForConnected(300)
    sock.abort()
    return alive


def main():
    init_display_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("Nivalis")
    app.setQuitOnLastWindowClosed(False)

    if _already_running():
        print("Nivalis уже запущен.", file=sys.stderr)
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_KEY)  # остаток от упавшего процесса
    server.listen(INSTANCE_KEY)

    problem = check_environment()
    if problem:
        QMessageBox.critical(None, "Nivalis", problem)
        return 1

    _overlay = NivalisOverlay()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

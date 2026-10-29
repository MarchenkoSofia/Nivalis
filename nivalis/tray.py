from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt

def generate_tray_icon() -> QIcon:
    px = QPixmap(32, 32)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setBrush(QColor("#38bdf8"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, 28, 28)
    p.setPen(QColor("#ffffff"))
    p.drawLine(16, 6, 16, 26)
    p.drawLine(6, 16, 26, 16)
    p.drawLine(9, 9, 23, 23)
    p.drawLine(9, 23, 23, 9)
    p.end()
    return QIcon(px)

class TrayManager:
    def __init__(self, overlay):
        self.overlay = overlay
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(generate_tray_icon())
        self.tray.setToolTip("Nivalis — Atmosphere Engine")
        self.build_menu()
        self.tray.show()

    def build_menu(self):
        m = QMenu()
        
        self.a_pass = m.addAction("👁️ Прозрачный режим")
        self.a_pass.setCheckable(True)
        self.a_pass.setChecked(True)
        self.a_pass.triggered.connect(lambda: self.set_tool(None))

        self.a_shovel = m.addAction("🥄 Лопатка (счищать)")
        self.a_shovel.setCheckable(True)
        self.a_shovel.triggered.connect(lambda: self.set_tool("shovel"))

        self.a_saw = m.addAction("🪚 Пила (валить ели)")
        self.a_saw.setCheckable(True)
        self.a_saw.triggered.connect(lambda: self.set_tool("saw"))

        m.addSeparator()

        a_thaw = m.addAction("💧 Запустить оттепель")
        a_thaw.triggered.connect(lambda: self.overlay.weather.trigger_thaw(28.0))

        a_santa = m.addAction("🎅 Вызвать упряжку")
        a_santa.triggered.connect(self.overlay.force_spawn_santa)

        self.a_turbo = m.addAction("⚡ Ускоренный рост елей")
        self.a_turbo.setCheckable(True)
        self.a_turbo.triggered.connect(self.toggle_turbo)

        m.addSeparator()
        a_quit = m.addAction("❌ Выход")
        a_quit.triggered.connect(self.overlay.close_application)

        self.tray.setContextMenu(m)

    def set_tool(self, tool_id):
        self.overlay.set_active_tool(tool_id)
        self.a_pass.setChecked(tool_id is None)
        self.a_shovel.setChecked(tool_id == "shovel")
        self.a_saw.setChecked(tool_id == "saw")

    def toggle_turbo(self):
        self.overlay.turbo_growth = self.a_turbo.isChecked()
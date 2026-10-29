from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QCheckBox, QPushButton, QGroupBox, QFormLayout
)
from .config import SETTINGS


class SettingsDialog(QWidget):
    def __init__(self, overlay):
        super().__init__(None)
        self.overlay = overlay
        self.setWindowTitle("Nivalis — Настройки климата и событий")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setFixedSize(430, 560)
        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f1f5f9;
                font-family: 'Segoe UI';
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #334155;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #38bdf8;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QCheckBox {
                spacing: 8px;
            }
        """)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)

        grp_weather = QGroupBox("Погода и температура")
        fl_weather = QFormLayout(grp_weather)

        self.cb_manual = QCheckBox("Ручное управление погодой")
        self.cb_manual.setChecked(SETTINGS.manual_weather)
        self.cb_manual.toggled.connect(self._on_change)
        fl_weather.addRow(self.cb_manual)

        self.lbl_temp = QLabel()
        self.sl_temp = QSlider(Qt.Orientation.Horizontal)
        self.sl_temp.setRange(-180, 80)
        self.sl_temp.setValue(int(SETTINGS.manual_temperature * 10))
        self.sl_temp.valueChanged.connect(self._on_change)
        fl_weather.addRow(self.lbl_temp, self.sl_temp)

        self.lbl_offset = QLabel()
        self.sl_offset = QSlider(Qt.Orientation.Horizontal)
        self.sl_offset.setRange(-80, 80)
        self.sl_offset.setValue(int(SETTINGS.temp_offset * 10))
        self.sl_offset.valueChanged.connect(self._on_change)
        fl_weather.addRow(self.lbl_offset, self.sl_offset)

        self.lbl_cpu = QLabel()
        self.sl_cpu = QSlider(Qt.Orientation.Horizontal)
        self.sl_cpu.setRange(0, 150)
        self.sl_cpu.setValue(int(SETTINGS.cpu_chill_gain * 10))
        self.sl_cpu.valueChanged.connect(self._on_change)
        fl_weather.addRow(self.lbl_cpu, self.sl_cpu)

        self.lbl_int = QLabel()
        self.sl_int = QSlider(Qt.Orientation.Horizontal)
        self.sl_int.setRange(5, 100)
        self.sl_int.setValue(int(SETTINGS.manual_intensity * 100))
        self.sl_int.valueChanged.connect(self._on_change)
        fl_weather.addRow(self.lbl_int, self.sl_int)

        root.addWidget(grp_weather)

        grp_trees = QGroupBox("Рост ёлочек")
        fl_trees = QFormLayout(grp_trees)

        self.lbl_thresh = QLabel()
        self.sl_thresh = QSlider(Qt.Orientation.Horizontal)
        self.sl_thresh.setRange(10, 90)
        self.sl_thresh.setValue(int(SETTINGS.tree_snow_threshold))
        self.sl_thresh.valueChanged.connect(self._on_change)
        fl_trees.addRow(self.lbl_thresh, self.sl_thresh)

        self.lbl_tcount = QLabel()
        self.sl_tcount = QSlider(Qt.Orientation.Horizontal)
        self.sl_tcount.setRange(1, 25)
        self.sl_tcount.setValue(SETTINGS.tree_max_count)
        self.sl_tcount.valueChanged.connect(self._on_change)
        fl_trees.addRow(self.lbl_tcount, self.sl_tcount)

        self.lbl_tspeed = QLabel()
        self.sl_tspeed = QSlider(Qt.Orientation.Horizontal)
        self.sl_tspeed.setRange(1, 50)
        self.sl_tspeed.setValue(int(SETTINGS.tree_growth_speed))
        self.sl_tspeed.valueChanged.connect(self._on_change)
        fl_trees.addRow(self.lbl_tspeed, self.sl_tspeed)

        root.addWidget(grp_trees)

        grp_santa = QGroupBox("Дед Мороз и события")
        fl_santa = QFormLayout(grp_santa)

        self.cb_req_tree = QCheckBox("Ждать, пока вырастет ёлка с огнями")
        self.cb_req_tree.setChecked(SETTINGS.santa_require_lit_tree)
        self.cb_req_tree.toggled.connect(self._on_change)
        fl_santa.addRow(self.cb_req_tree)

        self.lbl_scd = QLabel()
        self.sl_scd = QSlider(Qt.Orientation.Horizontal)
        self.sl_scd.setRange(5, 90)
        self.sl_scd.setValue(int(SETTINGS.santa_min_interval))
        self.sl_scd.valueChanged.connect(self._on_change)
        fl_santa.addRow(self.lbl_scd, self.sl_scd)

        btn_row = QHBoxLayout()
        btn_tree = QPushButton("🌲 Посадить ёлку")
        btn_tree.clicked.connect(self.overlay.force_spawn_tree)
        btn_santa = QPushButton("🎅 Вызвать сани")
        btn_santa.clicked.connect(self.overlay.force_spawn_santa)
        btn_thaw = QPushButton("💧 Оттепель")
        btn_thaw.clicked.connect(
            lambda: self.overlay.weather.trigger_thaw(25.0))
        btn_row.addWidget(btn_tree)
        btn_row.addWidget(btn_santa)
        btn_row.addWidget(btn_thaw)
        fl_santa.addRow(btn_row)

        root.addWidget(grp_santa)
        self._refresh_labels()

    def _on_change(self):
        SETTINGS.manual_weather = self.cb_manual.isChecked()
        SETTINGS.manual_temperature = self.sl_temp.value() / 10.0
        SETTINGS.temp_offset = self.sl_offset.value() / 10.0
        SETTINGS.cpu_chill_gain = self.sl_cpu.value() / 10.0
        SETTINGS.manual_intensity = self.sl_int.value() / 100.0

        SETTINGS.tree_snow_threshold = float(self.sl_thresh.value())
        SETTINGS.tree_max_count = self.sl_tcount.value()
        SETTINGS.tree_growth_speed = float(self.sl_tspeed.value())

        SETTINGS.santa_require_lit_tree = self.cb_req_tree.isChecked()
        SETTINGS.santa_min_interval = float(self.sl_scd.value())

        self.overlay.weather.force_sync()
        self._refresh_labels()

    def _refresh_labels(self):
        manual = SETTINGS.manual_weather
        self.sl_temp.setEnabled(manual)
        self.sl_int.setEnabled(manual)
        self.sl_offset.setEnabled(not manual)
        self.sl_cpu.setEnabled(not manual)

        self.lbl_temp.setText(
            f"Ручная темп.: {SETTINGS.manual_temperature:+.1f}°C")
        self.lbl_offset.setText(
            f"Сдвиг авто-темп.: {SETTINGS.temp_offset:+.1f}°C")
        self.lbl_cpu.setText(
            f"Охлаждение от CPU: -{SETTINGS.cpu_chill_gain:.1f}°C")
        self.lbl_int.setText(
            f"Сила снегопада: {int(SETTINGS.manual_intensity * 100)}%")
        self.lbl_thresh.setText(
            f"Сугроб для ёлки: {int(SETTINGS.tree_snow_threshold)} px")
        self.lbl_tcount.setText(f"Макс. ёлок: {SETTINGS.tree_max_count}")
        self.lbl_tspeed.setText(
            f"Скорость роста: x{int(SETTINGS.tree_growth_speed)}")
        self.lbl_scd.setText(
            f"Интервал саней: {int(SETTINGS.santa_min_interval)} с")

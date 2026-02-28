# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Persistent Example - Viewer Task"""
import time
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider, QHBoxLayout
from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QFont
from py_alaska import task, gconfig
from py_alaska.qt import ui_thread

_window = None


def set_window(w):
    global _window
    _window = w


class MainWindow(QWidget):
    def __init__(self, **kw):
        super().__init__()
        set_window(self)
        self.setWindowTitle("Persistent Counter")
        self.setMinimumSize(300, 150)

        layout = QVBoxLayout(self)

        # Count 표시
        self.count_label = QLabel("Count: 0")
        self.count_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # Interval 슬라이더
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Interval:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 30)  # 0.1s ~ 3.0s
        initial = int(gconfig.data_get("user_config.interval", 1.0) * 10)
        self.slider.setValue(initial)
        self.slider.valueChanged.connect(self._on_interval_changed)
        slider_layout.addWidget(self.slider)
        self.interval_label = QLabel(f"{initial/10:.1f}s")
        slider_layout.addWidget(self.interval_label)
        layout.addLayout(slider_layout)

    def _on_interval_changed(self, value):
        interval = value / 10.0
        self.interval_label.setText(f"{interval:.1f}s")
        gconfig.data_set("user_config.interval", interval)

    def update_count(self, count):
        self.count_label.setText(f"Count: {count}")


@task(name="ViewerTask")
class ViewerTask(QObject):
    def __init__(self):
        super().__init__()

    def run(self):
        self.runtime.signal.on("count", self.on_count)
        while self.running:
            time.sleep(0.1)

    @ui_thread
    def on_count(self, signal):
        if _window:
            _window.update_count(signal.data)

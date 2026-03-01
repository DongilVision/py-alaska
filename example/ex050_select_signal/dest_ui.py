# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Selective Signal Example - Dest UI Task"""
import time
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout
from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QFont
from py_alaska import task
from py_alaska import ui_thread

_window = None


def set_window(window):
    global _window
    _window = window


class ResultWindow(QWidget):
    """결과 표시 윈도우"""

    def __init__(self, title="Selective Signal Monitor"):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(400, 300)
        self.ok_count = 0
        self.ng_count = 0
        self.worker_stats = {t: {"ok": 0, "ng": 0} for t in "abcd"}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Total
        total_group = QGroupBox("Total Results")
        total_layout = QHBoxLayout(total_group)
        self.total_ok = self._label("OK: 0", "#4CAF50", 24)
        self.total_ng = self._label("NG: 0", "#F44336", 24)
        total_layout.addWidget(self.total_ok)
        total_layout.addWidget(self.total_ng)
        layout.addWidget(total_group)

        # Workers
        worker_group = QGroupBox("Worker Statistics")
        grid = QGridLayout(worker_group)
        self.labels = {}
        for i, t in enumerate("abcd"):
            grid.addWidget(QLabel(f"Worker {t.upper()}"), i, 0)
            ok = self._label("OK: 0", "#4CAF50", 12)
            ng = self._label("NG: 0", "#F44336", 12)
            grid.addWidget(ok, i, 1)
            grid.addWidget(ng, i, 2)
            self.labels[t] = {"ok": ok, "ng": ng}
        layout.addWidget(worker_group)
        layout.addStretch()

    def _label(self, text, color, size):
        label = QLabel(text)
        label.setFont(QFont("Arial", size, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {color}; padding: 5px;")
        if size > 20:
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def update_result(self, job_type, result):
        if result == "ok":
            self.ok_count += 1
        else:
            self.ng_count += 1
        self.worker_stats[job_type][result] += 1

        self.total_ok.setText(f"OK: {self.ok_count}")
        self.total_ng.setText(f"NG: {self.ng_count}")
        s = self.worker_stats[job_type]
        self.labels[job_type]["ok"].setText(f"OK: {s['ok']}")
        self.labels[job_type]["ng"].setText(f"NG: {s['ng']}")


@task(name="DestTask", debug=True)
class DestTask(QObject):
    """결과 수신 Task"""

    def __init__(self):
        super().__init__()

    def run(self):
        while self.running:
            time.sleep(0.1)

    @ui_thread
    def on_result(self, signal):
        if _window:
            d = signal.data
            _window.update_result(d["job_type"], d["result"])

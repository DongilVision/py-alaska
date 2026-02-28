# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""ScoreTask - QWidget + Task 통합: score.update signal 수신 → UI 직접 업데이트"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from py_alaska import task
from py_alaska.qt import ui_thread


@task(debug="signal")
class ScoreTask(QWidget):
    """점수 표시 윈도우 + signal 수신 Task"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Score Monitor")
        self.setMinimumSize(300, 200)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Score")
        glayout = QVBoxLayout(group)

        self.label_score = self._label("Current: 0", "#2196F3", 20)
        self.label_total = self._label("Total: 0", "#4CAF50", 20)
        self.label_count = self._label("Count: 0", "#FF9800", 16)

        glayout.addWidget(self.label_score)
        glayout.addWidget(self.label_total)
        glayout.addWidget(self.label_count)

        layout.addWidget(group)
        layout.addStretch()

    def _label(self, text, color, size):
        label = QLabel(text)
        label.setFont(QFont("Arial", size, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {color}; padding: 5px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    @ui_thread
    def on_score_update(self, signal):
        d = signal.data
        self.label_score.setText(f"Current: {d['score']}")
        self.label_total.setText(f"Total: {d['total']}")
        self.label_count.setText(f"Count: {d['count']}")

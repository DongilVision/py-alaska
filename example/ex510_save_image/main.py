# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-02
"""
main — 이미지 저장 예제 진입점
================================
AlaskaApp.run()으로 카메라 뷰어(좌) + 저장 UI(우) 실행.

Classes:
    MainWindow  QMainWindow — 좌/우 QSplitter (70:30)
"""
import multiprocessing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QMainWindow, QSplitter
from PySide6.QtCore import Qt
from py_alaska import AlaskaApp


class MainWindow(QMainWindow):
    def __init__(self, **kwargs):
        super().__init__()
        self.setWindowTitle(kwargs.get("title", "Save Image"))
        self.resize(1200, 700)

        splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(splitter)

        viewer = AlaskaApp.get_task("viewer")
        save_ui = AlaskaApp.get_task("save_ui")

        if viewer:
            splitter.addWidget(viewer)
        if save_ui:
            splitter.addWidget(save_ui)

        splitter.setSizes([840, 360])  # 70:30
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    AlaskaApp.run(
        Path(__file__).parent / "config.json",
        main_window_class=MainWindow,
        title="Save Image (DeviceProperty)"
    )

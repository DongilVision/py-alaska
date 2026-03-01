# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Performance Test - Signal/RMI Performance Measurement (Qt GUI)"""
import sys
import multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import AlaskaApp
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import QTimer


class MainWindow(QMainWindow):
    """Performance Test Main Window"""

    def __init__(self, title="Performance Test"):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(900, 700)
        self.setMinimumSize(800, 600)

        # Setup GUI widget after TaskManager is ready
        QTimer.singleShot(100, self._setup_gui)

    def _setup_gui(self):
        """Setup performance GUI widget"""
        if not AlaskaApp.manager:
            QTimer.singleShot(100, self._setup_gui)
            return

        gui = AlaskaApp.get_task("gui")
        if gui:
            self.setCentralWidget(gui)

            # Inject RMI clients
            try:
                gui.p1 = AlaskaApp.get_client("p1")
                gui.t1 = AlaskaApp.get_client("t1")
                print("[MainWindow] RMI clients injected")
            except Exception as e:
                print(f"[MainWindow] Client injection error: {e}")
        else:
            print("[MainWindow] GUI task not found")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    AlaskaApp.run(
        Path(__file__).parent / "config.json",
        MainWindow,
        title="Performance Test"
    )

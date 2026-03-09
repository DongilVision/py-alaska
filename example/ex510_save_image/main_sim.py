# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-07
"""
main_sim — SimCam / Real Camera 배타 전환 진입점
================================================
두 카메라(sim_cam, imi_cam_dp)를 등록하고,
Camera 콤보로 선택된 카메라만 기동, 비선택 카메라는 정지한다.

동작:
    SimCam 선택  → sim/sim_cam 기동,   cam/imi_cam_dp 정지
    Real Camera  → cam/imi_cam_dp 기동, sim/sim_cam 정지

구성:
    ┌──────────────┬────────────────────────────┐
    │ [Camera: ▾]  │                            │
    ├──────────────┤  viewer_sim / viewer_cam    │
    │   SimUI      │  (QStackedWidget 전환)     │
    ├──────────────┤                            │
    │ SaveImageUI  │                            │
    └──────────────┴────────────────────────────┘

task_config 구조:
    sim/sim_cam         — SimCam (이미지 Replay)
    cam/imi_cam_dp      — Real Camera (IMI)
    viewer_sim          — sim 전용 viewer (target: client:sim)
    viewer_cam          — cam 전용 viewer (target: client:cam)
    sim_ui              — SimCam 제어 UI (target: client:sim)
    saver, save_ui      — 이미지 저장

Classes:
    MainWindow  QMainWindow — 좌/우 QSplitter (30:70)
                              좌: Camera 선택 + SimUI + SaveImageUI
                              우: viewer (콤보로 전환)
"""
import multiprocessing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QHBoxLayout, QComboBox, QLabel, QStackedWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from py_alaska import AlaskaApp

# ── 카메라 모드 매핑 ───────────────────────────────────────────────────
# (combo_index, task_id_to_start, task_id_to_stop)
CAMERA_MODES = [
    {"name": "SimCam",      "task": "sim/sim_cam",     "off": "cam/imi_cam_dp"},
    {"name": "Real Camera", "task": "cam/imi_cam_dp",  "off": "sim/sim_cam"},
]

DARK_STYLE = """
QMainWindow { background-color: #222222; }
QWidget     { background-color: #222222; color: #d4d4d4; }
QComboBox   { background-color: #3c3c3c; border: 1px solid #555;
              border-radius: 4px; padding: 4px 8px; min-width: 120px; }
QLabel      { color: #d4d4d4; font-weight: bold; }
"""


class MainWindow(QMainWindow):
    def __init__(self, **kwargs):
        super().__init__()
        self.setWindowTitle(kwargs.get("title", "SimCam"))
        self.setStyleSheet(DARK_STYLE)
        self.resize(1400, 750)
        self._current_mode = 0  # 0=sim, 1=cam

        # 좌/우 분할
        main_splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(main_splitter)

        # ── 좌측 패널 (카메라 선택 + SimUI + SaveImageUI) ──
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # 카메라 선택 콤보
        selector = QWidget()
        selector.setStyleSheet(DARK_STYLE)
        sel_layout = QHBoxLayout(selector)
        sel_layout.setContentsMargins(6, 6, 6, 6)
        sel_layout.addWidget(QLabel("Camera:"))
        self.cam_combo = QComboBox()
        for mode in CAMERA_MODES:
            self.cam_combo.addItem(mode["name"])
        self.cam_combo.currentIndexChanged.connect(self._on_cam_changed)
        sel_layout.addWidget(self.cam_combo, 1)
        left_layout.addWidget(selector)

        # SimUI + SaveImageUI
        left_splitter = QSplitter(Qt.Vertical)

        sim_ui = AlaskaApp.get_task("sim_ui")
        if sim_ui:
            left_splitter.addWidget(sim_ui)

        save_ui = AlaskaApp.get_task("save_ui")
        if save_ui:
            left_splitter.addWidget(save_ui)

        left_splitter.setSizes([400, 350])
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 1)
        left_layout.addWidget(left_splitter, 1)

        main_splitter.addWidget(left_widget)

        # ── 우측: viewer (QStackedWidget로 전환) ──
        self.viewer_stack = QStackedWidget()

        viewer_sim = AlaskaApp.get_task("viewer_sim")
        viewer_cam = AlaskaApp.get_task("viewer_cam")

        # index 0 = sim, index 1 = cam
        self.viewer_stack.addWidget(viewer_sim if viewer_sim else QWidget())
        self.viewer_stack.addWidget(viewer_cam if viewer_cam else QWidget())
        self.viewer_stack.setCurrentIndex(0)

        main_splitter.addWidget(self.viewer_stack)

        main_splitter.setSizes([420, 980])
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 7)

        # 초기 상태: sim 기동, cam 정지
        self._stop_camera(CAMERA_MODES[1]["task"])

        # ── 단축키 ──
        self._fullscreen = False
        QShortcut(QKeySequence(Qt.Key_F5), self, activated=self._on_restart)
        QShortcut(QKeySequence(Qt.Key_F11), self, activated=self._on_toggle_fullscreen)

    # ── 카메라 전환 ───────────────────────────────────────────────────
    def _on_cam_changed(self, index):
        """카메라 전환 → 비선택 카메라 정지, 선택 카메라 기동, viewer 전환."""
        if index == self._current_mode:
            return
        self._current_mode = index

        mode = CAMERA_MODES[index]

        # 1. 비선택 카메라 정지
        self._stop_camera(mode["off"])

        # 2. 선택 카메라 기동
        self._start_camera(mode["task"])

        # 3. viewer 전환
        self.viewer_stack.setCurrentIndex(index)

    # ── 단축키 핸들러 ─────────────────────────────────────────────────
    def _on_restart(self):
        """F5: 앱 재실행."""
        import subprocess, os
        subprocess.Popen(
            [sys.executable, __file__],
            cwd=os.getcwd(),
        )
        AlaskaApp.quit()

    def _on_toggle_fullscreen(self):
        """F11: 전체화면 토글."""
        if self._fullscreen:
            self.showNormal()
        else:
            self.showFullScreen()
        self._fullscreen = not self._fullscreen

    # ── 카메라 제어 ──────────────────────────────────────────────────
    def _stop_camera(self, task_id):
        """카메라 태스크 정지 (stop_flag 설정)."""
        mgr = AlaskaApp.manager
        if not mgr:
            return
        with mgr._task_lock:
            ti = mgr._tasks.get(task_id)
        if ti and not ti.stop_flag.value:
            ti.stop_flag.value = True
            print(f"[MainWindow] Camera stopped: {task_id}")

    def _start_camera(self, task_id):
        """카메라 태스크 기동 (restart_task)."""
        mgr = AlaskaApp.manager
        if not mgr:
            return
        with mgr._task_lock:
            ti = mgr._tasks.get(task_id)
        if not ti:
            return
        if ti.stop_flag.value:
            mgr.restart_task(task_id)
            print(f"[MainWindow] Camera started: {task_id}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    AlaskaApp.run(
        Path(__file__).parent / "config_sim.json",
        main_window_class=MainWindow,
        title="Camera Viewer (Sim + Real)"
    )

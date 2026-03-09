# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-07
"""
SimUI — SimCam 제어 UI 패널
============================
SimCam 전용 재생 제어 UI. Play/Pause/Step/Seek + 모드/세션/루프 설정.

config.json 주입:
    target — inject("client:sim") — SimCam RMI 프록시

시그널 수신 (기존 camera.* 재사용):
    on_camera_connected     → UI 활성화 + get_info()
    on_camera_disconnected  → UI 비활성화
    on_camera_received      → 상태 갱신 (프레임/FPS/드롭)

설계서: doc/6020____sim_cam기능설계.txt §16
"""

import time

from py_alaska import task, ui_thread


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QComboBox, QDoubleSpinBox, QCheckBox,
)
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, Property, Signal as QtSignal


# ═══════════════════════════════════════════════════════════════════════════
# ToggleSwitch
# ═══════════════════════════════════════════════════════════════════════════
class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 21)
        self._handle_position = 2
        self._animation = QPropertyAnimation(self, b"handle_position", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.stateChanged.connect(self._on_state_changed)

    def _get_handle_position(self):
        return self._handle_position

    def _set_handle_position(self, pos):
        self._handle_position = pos
        self.update()

    handle_position = Property(float, _get_handle_position, _set_handle_position)

    def _on_state_changed(self, state):
        self._animation.setStartValue(self._handle_position)
        self._animation.setEndValue(22 if state else 2)
        self._animation.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(QColor("#0078d4") if self.isChecked() else QColor("#555")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, 40, 21), 10, 10)
        p.setBrush(QBrush(QColor("#fff")))
        p.drawEllipse(QRectF(self._handle_position, 2.5, 16, 16))

    def hitButton(self, pos):
        return self.rect().contains(pos)


# ═══════════════════════════════════════════════════════════════════════════
# 스타일
# ═══════════════════════════════════════════════════════════════════════════
DARK_STYLE = """
QWidget        { background-color: #222; color: #d4d4d4; }
QPushButton    { background-color: #0e639c; color: white;
                 border: none; border-radius: 3px; padding: 4px 8px; }
QPushButton:hover    { background-color: #1177bb; }
QPushButton:disabled { background-color: #333; color: #666; }
QComboBox      { background-color: #333; border: 1px solid #555;
                 border-radius: 3px; padding: 3px; }
QDoubleSpinBox { background-color: #333; border: 1px solid #555;
                 border-radius: 3px; padding: 3px; }
QSlider::groove:horizontal { background: #444; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal { background: #0078d4; width: 12px;
                             margin: -4px 0; border-radius: 6px; }
QSlider::sub-page:horizontal { background: #0078d4; border-radius: 2px; }
QLabel         { color: #ccc; font-size: 11px; }
"""

COLOR_PLAYING = "#4fc3f7"
COLOR_PAUSED = "#ffb74d"
COLOR_STOPPED = "#888"
COLOR_DISCONNECTED = "#ff4444"

STOP_BTN_STYLE = (
    "QPushButton { background-color: #c62828; color: white; "
    "border: none; border-radius: 3px; padding: 4px 8px; }"
    "QPushButton:hover { background-color: #e53935; }"
    "QPushButton:disabled { background-color: #333; color: #666; }")


# ═══════════════════════════════════════════════════════════════════════════
# SimUI Task
# ═══════════════════════════════════════════════════════════════════════════
@task()
class SimUI(QWidget):
    """SimCam 제어 UI 패널 (@task + QWidget)."""

    _status_ready = QtSignal(int, int, float, int)

    DISCONNECTED = "DISCONNECTED"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"

    def __init__(self):
        super().__init__()
        self.target = None
        self._state = self.DISCONNECTED
        self._total_frames = 0
        self._current_frame = 0
        self._base_fps = 30.0
        self._sessions = []
        self._frame_count = 0
        self._last_fps_time = 0.0
        self._display_fps = 0.0
        self._last_display_time = 0.0
        self._display_interval = 1.0 / 30

        self._init_ui()
        self._status_ready.connect(self._on_status_ready_ui)
        self._update_button_state()

    def run(self):
        pass

    # ═══════════════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════════════
    def _init_ui(self):
        self.setStyleSheet(DARK_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(2)

        # ── Title + Status ──
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("SimCam")
        lbl.setStyleSheet("font-size: 12px; font-weight: bold; color: #eee;")
        row.addWidget(lbl)
        row.addStretch()
        self.status_indicator = QLabel("  DISCONNECTED  ")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self._set_status_indicator(self.DISCONNECTED)
        row.addWidget(self.status_indicator)
        root.addLayout(row)

        # ── Transport ──
        tr = QHBoxLayout()
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(2)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._on_play)
        tr.addWidget(self.play_btn)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._on_pause)
        tr.addWidget(self.pause_btn)
        self.step_btn = QPushButton("Step")
        self.step_btn.clicked.connect(self._on_step)
        tr.addWidget(self.step_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setStyleSheet(STOP_BTN_STYLE)
        self.stop_btn.clicked.connect(self._on_stop)
        tr.addWidget(self.stop_btn)
        root.addLayout(tr)

        # ── Seek ──
        sk = QHBoxLayout()
        sk.setContentsMargins(0, 0, 0, 0)
        sk.setSpacing(2)
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        sk.addWidget(self.seek_slider, 1)
        self.frame_label = QLabel("0 / 0")
        self.frame_label.setFixedWidth(80)
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setStyleSheet("font-weight: bold;")
        sk.addWidget(self.frame_label)
        root.addLayout(sk)

        # ── Settings row 1: Mode + FPS ──
        r1 = QHBoxLayout()
        r1.setContentsMargins(0, 0, 0, 0)
        r1.setSpacing(2)
        r1.addWidget(QLabel("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["realtime", "original", "fast", "step"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        r1.addWidget(self.mode_combo)
        r1.addWidget(QLabel("FPS"))
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.1, 1000.0)
        self.fps_spin.setValue(30.0)
        self.fps_spin.setDecimals(1)
        self.fps_spin.editingFinished.connect(self._on_fps_editing_finished)
        r1.addWidget(self.fps_spin)
        root.addLayout(r1)

        # ── Settings row 2: Session + Loop + Speed ──
        r2 = QHBoxLayout()
        r2.setContentsMargins(0, 0, 0, 0)
        r2.setSpacing(2)
        r2.addWidget(QLabel("Session"))
        self.session_combo = QComboBox()
        self.session_combo.currentTextChanged.connect(self._on_session_changed)
        r2.addWidget(self.session_combo)
        r2.addWidget(QLabel("Loop"))
        self.loop_toggle = ToggleSwitch()
        self.loop_toggle.toggled.connect(self._on_loop_changed)
        r2.addWidget(self.loop_toggle)
        r2.addWidget(QLabel("Speed"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.25x", "0.5x", "1.0x", "2.0x", "4.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        r2.addWidget(self.speed_combo)
        root.addLayout(r2)

        # ── Status ──
        self.status_state_label = QLabel("State: DISCONNECTED")
        root.addWidget(self.status_state_label)
        self.status_detail_label = QLabel("Frame: 0/0   FPS: 0.0   Drops: 0")
        self.status_detail_label.setStyleSheet("color: #888; font-size: 10px;")
        root.addWidget(self.status_detail_label)

        root.addStretch()

    # ═══════════════════════════════════════════════════════════════════
    # 시그널 핸들러
    # ═══════════════════════════════════════════════════════════════════
    @ui_thread
    def on_camera_connected(self, signal):
        data = signal.data
        self._base_fps = data.get("fps", 30.0)
        mode = data.get("mode", "sim")
        self._state = self.PLAYING
        self._frame_count = 0
        self._last_fps_time = time.time()

        self._update_button_state()
        self._set_status_indicator(self.PLAYING)
        self.status_state_label.setText(f"State: PLAYING  (mode={mode})")
        self.fps_spin.setValue(self._base_fps)

        if self.target:
            try:
                info = self.target.get_info()
                self._total_frames = info.get("total", 0)
                self._sessions = info.get("sessions", [])

                self.seek_slider.setRange(0, max(self._total_frames - 1, 0))
                self.frame_label.setText(f"0 / {self._total_frames}")

                self.session_combo.blockSignals(True)
                self.session_combo.clear()
                for s in self._sessions:
                    self.session_combo.addItem(s)
                cs = info.get("session", "")
                if cs:
                    self.session_combo.setCurrentText(cs)
                self.session_combo.blockSignals(False)

                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentText(info.get("replay_mode", "realtime"))
                self.mode_combo.blockSignals(False)

                self.loop_toggle.blockSignals(True)
                self.loop_toggle.setChecked(bool(info.get("loop", False)))
                self.loop_toggle.blockSignals(False)
            except Exception:
                pass

    @ui_thread
    def on_camera_disconnected(self, signal):
        data = signal.data
        self._state = self.STOPPED
        self._update_button_state()
        self._set_status_indicator(self.STOPPED)
        self.status_state_label.setText(f"State: STOPPED ({data.get('reason', '')})")
        self.status_detail_label.setText(
            f"Frame: {data.get('captured', 0)}/{self._total_frames}   "
            f"FPS: -   Drops: {data.get('dropped', 0)}")

    def on_camera_received(self, signal):
        now = time.time()
        data = signal.data

        self._frame_count += 1
        elapsed = now - self._last_fps_time
        if elapsed >= 1.0:
            self._display_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_time = now

        if now - self._last_display_time < self._display_interval:
            return
        self._last_display_time = now

        self._current_frame = data.get("rx_count", 0)
        self._status_ready.emit(
            self._current_frame, self._total_frames,
            self._display_fps, data.get("rx_drop", 0))

    def _on_status_ready_ui(self, current, total, fps, drops):
        self.frame_label.setText(f"{current} / {total}")
        self.status_detail_label.setText(
            f"Frame: {current}/{total}   FPS: {fps:.1f}   Drops: {drops}")
        if not self.seek_slider.isSliderDown():
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(min(current, self.seek_slider.maximum()))
            self.seek_slider.blockSignals(False)

    # ═══════════════════════════════════════════════════════════════════
    # Transport
    # ═══════════════════════════════════════════════════════════════════
    def _on_play(self):
        if not self.target:
            return
        try:
            self.target.trigger_mode = False
        except Exception:
            return
        self._state = self.PLAYING
        self._update_button_state()
        self._set_status_indicator(self.PLAYING)
        self.status_state_label.setText("State: PLAYING")

    def _on_pause(self):
        if not self.target:
            return
        try:
            self.target.trigger_mode = True
        except Exception:
            return
        self._state = self.PAUSED
        self._update_button_state()
        self._set_status_indicator(self.PAUSED)
        self.status_state_label.setText("State: PAUSED")

    def _on_step(self):
        if not self.target:
            return
        try:
            self.target.one_shot()
        except Exception:
            pass

    def _on_stop(self):
        if not self.target:
            return
        try:
            self.target.pause()
        except Exception:
            pass
        self._state = self.STOPPED
        self._update_button_state()
        self._set_status_indicator(self.STOPPED)
        self.status_state_label.setText("State: STOPPED")

    # ═══════════════════════════════════════════════════════════════════
    # Seek
    # ═══════════════════════════════════════════════════════════════════
    def _on_seek_released(self):
        if self._state != self.PAUSED or not self.target:
            return
        try:
            self.target.seek(self.seek_slider.value())
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════
    # Settings
    # ═══════════════════════════════════════════════════════════════════
    def _on_mode_changed(self, mode):
        if not self.target:
            return
        try:
            self.target.set_replay_mode(mode)
        except Exception:
            pass
        if mode == "step":
            self._state = self.PAUSED
            self._update_button_state()
            self._set_status_indicator(self.PAUSED)

    def _on_fps_editing_finished(self):
        if not self.target:
            return
        self._base_fps = self.fps_spin.value()
        try:
            self.target.fps = self._base_fps
        except Exception:
            pass

    def _on_session_changed(self, name):
        if not self.target or not name:
            return
        try:
            self.target.set_session(name)
        except Exception:
            pass

    def _on_loop_changed(self, checked):
        if not self.target:
            return
        try:
            self.target.set_loop(checked)
        except Exception:
            pass

    def _on_speed_changed(self, text):
        if not self.target:
            return
        try:
            m = float(text.replace("x", ""))
        except ValueError:
            return
        new_fps = self._base_fps * m
        self.fps_spin.setValue(new_fps)
        try:
            self.target.fps = new_fps
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════
    # 상태 관리
    # ═══════════════════════════════════════════════════════════════════
    def _update_button_state(self):
        s = self._state
        self.play_btn.setEnabled(s in (self.PAUSED, self.STOPPED))
        self.pause_btn.setEnabled(s == self.PLAYING)
        self.step_btn.setEnabled(s == self.PAUSED)
        self.stop_btn.setEnabled(s in (self.PLAYING, self.PAUSED))
        self.seek_slider.setEnabled(s == self.PAUSED)

    def _set_status_indicator(self, state):
        colors = {
            self.PLAYING: COLOR_PLAYING,
            self.PAUSED: COLOR_PAUSED,
            self.STOPPED: COLOR_STOPPED,
            self.DISCONNECTED: COLOR_DISCONNECTED,
        }
        c = colors.get(state, COLOR_DISCONNECTED)
        self.status_indicator.setText(f" {state} ")
        self.status_indicator.setStyleSheet(
            f"background-color: {c}; color: white; "
            "border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 10px;")

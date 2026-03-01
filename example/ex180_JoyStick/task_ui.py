# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""UI Task - PySide6 조이스틱 상태 표시
   jog.connect → 연결/해제 상태
   jog.pos     → x, y, z, a, b, c 6축 좌표
   jog.shot    → 카메라 샷 카운트
   jog.inc     → 증분 선택값
   jog.raw     → 원시 HID 바이트 변화
"""
import sys, os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QGroupBox, QPushButton,
                                QPlainTextEdit, QGridLayout)
from PySide6.QtCore import Qt, QProcess
from PySide6.QtGui import QFont
from py_alaska import task
from py_alaska import ui_thread

_INC_LIST = [0.1, 1.0, 5.0, 10.0]

_AXIS_STYLE = ("border:1px solid #444; border-radius:4px; padding:8px;"
               " background:#1a1a1a; color:#0f0;")
_AXIS_STYLE_Z = ("border:1px solid #444; border-radius:4px; padding:8px;"
                 " background:#1a1a1a; color:#0ff;")
_BTN = ("QPushButton { background:#2a2a2a; color:#aaa; border:1px solid #444;"
        " border-radius:3px; padding:5px 8px; }"
        "QPushButton:checked { background:#4CAF50; color:white; font-weight:bold; }")


@task(debug="signal")
class UITask(QWidget):
    """조이스틱 CNC Jog 모니터"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JoyStick CNC Jog")
        self.setMinimumSize(640, 420)
        self._inc = 0.0
        self.setStyleSheet("""
            QWidget { background:black; color:#ccc; }
            QGroupBox { border:1px solid #444; border-radius:4px;
                        margin-top:10px; padding-top:16px; color:#888;
                        font-weight:bold; }
            QGroupBox::title { subcontrol-origin:margin; left:10px; }
        """)
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── 상단: 연결 상태 + 재시작 ──
        top = QHBoxLayout()
        self.lbl_conn = QLabel("OFF")
        self.lbl_conn.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.lbl_conn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_conn(False)
        top.addWidget(self.lbl_conn, stretch=1)

        btn_restart = QPushButton("Restart")
        btn_restart.setFont(QFont("Arial", 10))
        btn_restart.setStyleSheet(
            "QPushButton { background:#d32f2f; color:white; border:none;"
            " border-radius:4px; padding:6px 14px; font-weight:bold; }"
            "QPushButton:hover { background:#e53935; }")
        btn_restart.clicked.connect(self._restart_app)
        top.addWidget(btn_restart)
        root.addLayout(top)

        # ── 축 표시: 좌스틱(X,Y) | Z | 우스틱(A,B) | C ──
        grp_pos = QGroupBox("Position (mm)")
        gl = QGridLayout(grp_pos)
        gl.setSpacing(6)
        self.lbl_axes = {}

        # 좌스틱
        gl.addWidget(self._axis_header("L-Stick"), 0, 0, 1, 2)
        for col, axis in enumerate("XY"):
            lbl = self._axis_label(axis, _AXIS_STYLE)
            gl.addWidget(lbl, 1, col)
            self.lbl_axes[axis] = lbl

        # Z (중앙)
        gl.addWidget(self._axis_header("D-Pad"), 0, 2)
        lbl_z = self._axis_label("Z", _AXIS_STYLE_Z)
        gl.addWidget(lbl_z, 1, 2)
        self.lbl_axes["Z"] = lbl_z

        # 우스틱
        gl.addWidget(self._axis_header("R-Stick"), 0, 3, 1, 2)
        for col, axis in enumerate("AB", 3):
            lbl = self._axis_label(axis, _AXIS_STYLE)
            gl.addWidget(lbl, 1, col)
            self.lbl_axes[axis] = lbl

        # C (Aux)
        gl.addWidget(self._axis_header("Aux"), 0, 5)
        lbl_c = self._axis_label("C", _AXIS_STYLE)
        gl.addWidget(lbl_c, 1, 5)
        self.lbl_axes["C"] = lbl_c

        root.addWidget(grp_pos)

        # ── Increment: Shot + INC + 증분 버튼 ──
        grp_info = QGroupBox("Increment")
        il = QHBoxLayout(grp_info)

        self.lbl_shot = QLabel("SHOT: 0")
        self.lbl_shot.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        self.lbl_shot.setStyleSheet("color:#ff9800;")
        self.lbl_shot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(self.lbl_shot)

        il.addSpacing(16)

        self.lbl_inc = QLabel("INC: ---")
        self.lbl_inc.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        self.lbl_inc.setStyleSheet("color:#4CAF50; background:#1a1a1a;"
                                   " border:1px solid #444; border-radius:4px; padding:4px 10px;")
        self.lbl_inc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(self.lbl_inc)

        il.addSpacing(16)

        self.inc_btns = []
        for v in _INC_LIST:
            btn = QPushButton(f"{v}")
            btn.setCheckable(True)
            btn.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            btn.setMinimumWidth(52)
            btn.setStyleSheet(_BTN)
            btn.clicked.connect(lambda _, val=v: self._on_inc_clicked(val))
            il.addWidget(btn)
            self.inc_btns.append((v, btn))
        root.addWidget(grp_info)

        # ── Raw Trace ──
        grp_raw = QGroupBox("Raw Trace")
        rl = QVBoxLayout(grp_raw)
        self.txt_trace = QPlainTextEdit()
        self.txt_trace.setReadOnly(True)
        self.txt_trace.setFont(QFont("Consolas", 9))
        self.txt_trace.setStyleSheet(
            "color:#ff0; background:#111; border:none;")
        self.txt_trace.setMaximumBlockCount(200)
        rl.addWidget(self.txt_trace)
        btn_clear = QPushButton("Clear")
        btn_clear.setFont(QFont("Arial", 9))
        btn_clear.setStyleSheet(
            "QPushButton { background:#333; color:#aaa; border:1px solid #555;"
            " border-radius:3px; padding:3px 10px; }"
            "QPushButton:hover { background:#444; }")
        btn_clear.clicked.connect(self.txt_trace.clear)
        rl.addWidget(btn_clear, alignment=Qt.AlignmentFlag.AlignRight)
        root.addWidget(grp_raw, stretch=1)

    # ── UI 헬퍼 ──

    def _axis_header(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 9))
        lbl.setStyleSheet("color:#666;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lbl

    def _axis_label(self, axis, style):
        lbl = QLabel(f"{axis}\n+0.00")
        lbl.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setMinimumWidth(80)
        lbl.setStyleSheet(style)
        return lbl

    def _set_conn(self, connected):
        if connected:
            self.lbl_conn.setText("CONNECTED")
            self.lbl_conn.setStyleSheet(
                "background:#2E7D32; color:white; padding:6px; border-radius:4px;")
        else:
            self.lbl_conn.setText("DISCONNECTED")
            self.lbl_conn.setStyleSheet(
                "background:#C62828; color:white; padding:6px; border-radius:4px;")

    def _restart_app(self):
        QProcess.startDetached(sys.executable, sys.argv, os.getcwd())
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def _update_inc(self, val):
        for v, btn in self.inc_btns:
            btn.setChecked(v == val)

    def _on_inc_clicked(self, val):
        self.signal.jog.set.inc.emit(val)

    # ── signal 수신 ──

    @ui_thread
    def on_jog_connect(self, signal):
        self._set_conn(signal.data)

    @ui_thread
    def on_jog_pos(self, signal):
        d = signal.data
        for axis in "xyzabc":
            if axis in d:
                lbl = self.lbl_axes[axis.upper()]
                lbl.setText(f"{axis.upper()}\n{d[axis]:+.2f}")

    @ui_thread
    def on_jog_shot(self, signal):
        self.lbl_shot.setText(f"SHOT: {signal.data}")

    @ui_thread
    def on_jog_inc(self, signal):
        self._inc = signal.data
        self.lbl_inc.setText(f"INC: {self._inc}")
        self._update_inc(self._inc)

    @ui_thread
    def on_jog_raw(self, signal):
        self.txt_trace.appendPlainText(signal.data)

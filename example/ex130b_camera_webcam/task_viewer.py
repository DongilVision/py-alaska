# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
WebcamView Widget
=================
QWidget 기반 웹캠 뷰어 (Signal 수신 → UI 업데이트)
- ex130_camera의 ImiCameraView를 웹캠용으로 단순화
"""

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from py_alaska import task
from py_alaska import ui_thread
import numpy as np
import time

from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QGroupBox,
    QDialog, QToolButton, QTabWidget
)
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property, QRectF, QTimer, Signal as QtSignal


class ToggleSwitch(QCheckBox):
    """iOS 스타일 슬라이드 토글 스위치 (80% 크기)"""

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
        if state:
            self._animation.setStartValue(self._handle_position)
            self._animation.setEndValue(22)
        else:
            self._animation.setStartValue(self._handle_position)
            self._animation.setEndValue(2)
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor("#0078d4") if self.isChecked() else QColor("#555555")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, 40, 21), 10, 10)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QRectF(self._handle_position, 2.5, 16, 16))

    def hitButton(self, pos):
        return self.rect().contains(pos)


DARK_STYLE = """
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
}
QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    background-color: #0e639c;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #1177bb;
}
QPushButton:disabled {
    background-color: #3c3c3c;
    color: #6c6c6c;
}
QCheckBox {
    spacing: 8px;
}
QLabel {
    color: #d4d4d4;
}
"""


@task()
class WebcamView(QWidget):
    """웹캠 뷰어 위젯 (@task + QWidget)"""

    _frame_ready = QtSignal(object, int, float)  # (image, total_count, fps)

    def __init__(self):
        super().__init__()
        self.smblock = None
        self.target = None

        # FPS 계산
        self.frame_count = 0
        self.total_frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0.0

        # 오버레이 표시 옵션
        self.show_fps_overlay = True
        self.show_time_overlay = False

        # 확대/축소 및 패닝
        self._scale = 1.0
        self._pan_offset = [0, 0]
        self._panning = False
        self._pan_start = None
        self._current_pixmap = None
        self.enable_zoom_pan = True

        # 프레임 드롭 제어 (4K 등 대용량 프레임용)
        self._ui_busy = False

        # 연결 상태
        self._is_connected = False
        self._disconnect_time = None
        self._is_iconified = False

        self._init_ui()

    @property
    def camera_client(self):
        return self.target

    def run(self):
        """서비스 개시"""
        if self.target:
            self._sync_camera_state()
            print(f"[WebcamView] Service started with target: {self.target}")

    def _sync_camera_state(self):
        if not self.target:
            return
        try:
            is_opened = bool(self.target.is_opened)
            self._is_connected = is_opened
            self._update_settings_icon_color(is_opened)
            if is_opened:
                self._disconnect_time = None
        except Exception:
            pass

    def _update_settings_icon_color(self, connected: bool):
        color = QColor("#00ff00") if connected else QColor("#ff4444")
        self.settings_btn.setIcon(self._create_settings_icon(color))

    def _init_ui(self):
        self.setStyleSheet(DARK_STYLE)
        layout = QVBoxLayout(self)

        # 이미지 컨테이너
        self.image_container = QWidget()
        self.image_container.setMinimumSize(640, 480)
        layout.addWidget(self.image_container)

        # 이미지 표시 레이블
        self.image_label = QLabel(self.image_container)
        self.image_label.setGeometry(0, 0, 640, 480)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background-color: #1a1a1a;")

        # FPS 오버레이
        self.stats_label = QLabel("000 (0.0)", self.image_container)
        self.stats_label.setStyleSheet(
            "color: #00ff00; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )
        self.stats_label.move(10, 10)

        # 현재시간 오버레이
        self.time_label = QLabel("", self.image_container)
        self.time_label.setStyleSheet(
            "color: #ffffff; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )
        self.time_label.hide()

        # 설정 버튼
        self.settings_btn = QToolButton(self.image_container)
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setIcon(self._create_settings_icon())
        self.settings_btn.setIconSize(QSize(24, 24))
        self.settings_btn.setStyleSheet(
            "QToolButton { background-color: rgba(0, 0, 0, 150); border-radius: 18px; border: none; }"
            "QToolButton:hover { background-color: rgba(50, 50, 50, 200); }"
            "QToolButton:pressed { background-color: rgba(80, 80, 80, 200); }"
        )
        self.settings_btn.clicked.connect(self._show_settings_dialog)
        self.settings_btn.raise_()

        # Qt Signal → UI 스레드 연결
        self._frame_ready.connect(self._on_frame_ready_ui)

        # 시간 업데이트 타이머
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time_display)
        self._time_timer.start(1000)

    def _create_settings_icon(self, color: QColor = None) -> QIcon:
        from PySide6.QtGui import QPixmap
        import math
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        icon_color = color if color else QColor(255, 255, 255)
        pen = QPen(icon_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawEllipse(4, 4, 16, 16)
        painter.drawEllipse(8, 8, 8, 8)
        cx, cy, r1, r2 = 12, 12, 10, 14
        for i in range(8):
            angle = i * math.pi / 4
            x1 = cx + r1 * math.cos(angle)
            y1 = cy + r1 * math.sin(angle)
            x2 = cx + r2 * math.cos(angle)
            y2 = cy + r2 * math.sin(angle)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        painter.end()
        return QIcon(pixmap)

    def _show_settings_dialog(self):
        """설정 대화창 (디바이스 탭만 - 오버레이 옵션)"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Webcam Settings")
        dialog.setFixedSize(400, 300)
        dialog.setStyleSheet("""
            QDialog { background-color: #2d2d2d; color: white; }
            QTabWidget::pane { border: 1px solid #555; border-radius: 4px; }
            QTabBar::tab { background-color: #3d3d3d; padding: 8px 16px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: #0078d4; }
            QTabBar::tab:hover:!selected { background-color: #4d4d4d; }
        """)

        layout = QVBoxLayout(dialog)
        groupbox_style = (
            "QGroupBox { border: 1px solid #555; border-radius: 4px; margin-top: 10px; padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )

        # 오버레이 표시 옵션
        overlay_group = QGroupBox("오버레이 표시")
        overlay_group.setStyleSheet(groupbox_style)
        overlay_layout = QVBoxLayout(overlay_group)

        # FPS 표시
        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS 표시:"))
        self.show_fps_toggle = ToggleSwitch()
        self.show_fps_toggle.setChecked(self.show_fps_overlay)
        self.show_fps_toggle.toggled.connect(self._on_show_fps_changed)
        fps_row.addWidget(self.show_fps_toggle)
        fps_row.addStretch()
        overlay_layout.addLayout(fps_row)

        # 현재시간 표시
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("현재시간:"))
        self.show_time_toggle = ToggleSwitch()
        self.show_time_toggle.setChecked(self.show_time_overlay)
        self.show_time_toggle.toggled.connect(self._on_show_time_changed)
        time_row.addWidget(self.show_time_toggle)
        time_row.addStretch()
        overlay_layout.addLayout(time_row)

        # 확대/축소
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("확대/축소:"))
        self.zoom_pan_toggle = ToggleSwitch()
        self.zoom_pan_toggle.setChecked(self.enable_zoom_pan)
        self.zoom_pan_toggle.toggled.connect(self._on_zoom_pan_changed)
        zoom_row.addWidget(self.zoom_pan_toggle)
        zoom_row.addStretch()
        overlay_layout.addLayout(zoom_row)

        layout.addWidget(overlay_group)
        layout.addStretch()

        # 닫기 버튼
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "QPushButton { background-color: #0078d4; border: none; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1084d8; }"
        )
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec()

    def _on_show_fps_changed(self, checked: bool):
        self.show_fps_overlay = checked
        self.stats_label.setVisible(checked)

    def _on_show_time_changed(self, checked: bool):
        self.show_time_overlay = checked
        self.time_label.setVisible(checked)

    def _on_zoom_pan_changed(self, checked: bool):
        self.enable_zoom_pan = checked
        if not checked:
            self._scale = 1.0
            self._pan_offset = [0, 0]
            if self._current_pixmap:
                self.image_label.setPixmap(self._current_pixmap)

    # ═══════════════════════════════════════════════════════════════════════════
    # Signal Handlers
    # ═══════════════════════════════════════════════════════════════════════════

    def on_camera_received(self, signal):
        """Signal: 프레임 수신 (dispatcher 스레드) → 즉시 mfree → UI가 준비된 경우만 전달"""
        if not self.smblock:
            return

        data = signal.data
        sm_index = data["sm_index"]
        try:
            # FPS 카운트
            self.frame_count += 1
            self.total_frame_count += 1
            now = time.time()
            elapsed = now - self.last_fps_time
            if elapsed >= 1.0:
                self.fps = self.frame_count / elapsed
                self.frame_count = 0
                self.last_fps_time = now

            # 최소화 또는 UI 렌더링 중이면 복사 스킵 (프레임 드롭)
            if self._is_iconified or self._ui_busy:
                return

            # dispatcher 스레드에서 즉시 복사 (SmBlock 점유 최소화)
            image = self.smblock.get_buffer(sm_index).copy()
        finally:
            self.smblock.mfree(sm_index)

        # UI busy 플래그 → Qt Signal 큐에 1프레임만 존재하도록 제한
        self._ui_busy = True
        self._frame_ready.emit(image, self.total_frame_count, self.fps)

    def _on_frame_ready_ui(self, image, total_count, fps):
        """UI 스레드: 프레임 표시"""
        pixmap = self._numpy_to_pixmap(image)
        self._current_pixmap = pixmap

        if self.enable_zoom_pan and self._scale != 1.0:
            self._apply_zoom_pan()
        else:
            self.image_label.setPixmap(pixmap)

        if self.show_fps_overlay:
            self.stats_label.setText(f"{total_count:03d} ({fps:.1f})")
            self.stats_label.adjustSize()
            self.stats_label.raise_()

        # UI 렌더링 완료 → 다음 프레임 수신 허용
        self._ui_busy = False

    @ui_thread
    def on_camera_connected(self, signal):
        self._is_connected = True
        self._disconnect_time = None
        self._update_settings_icon_color(True)
        self.stats_label.setStyleSheet(
            "color: #00ff00; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )

    @ui_thread
    def on_camera_disconnected(self, signal):
        self._is_connected = False
        self._disconnect_time = time.time()
        self._update_settings_icon_color(False)
        self.stats_label.setStyleSheet(
            "color: #ff4444; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # UI Updates
    # ═══════════════════════════════════════════════════════════════════════════

    def _update_time_display(self):
        if self.show_time_overlay:
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.time_label.setText(current_time)
            self.time_label.adjustSize()
            self._update_time_label_position()
            self.time_label.raise_()

        if not self._is_connected and self._disconnect_time is not None:
            elapsed = int(time.time() - self._disconnect_time)
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                disconnect_text = f"DC {hours:02d}:{mins:02d}:{secs:02d}"
            else:
                disconnect_text = f"DC {mins:02d}:{secs:02d}"
            self.stats_label.setText(disconnect_text)
            self.stats_label.adjustSize()
            self.stats_label.raise_()

    def hideEvent(self, event):
        self._is_iconified = True
        super().hideEvent(event)

    def showEvent(self, event):
        self._is_iconified = False
        super().showEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.image_label.setGeometry(0, 0, self.image_container.width(), self.image_container.height())
        self._update_settings_btn_position()
        self._update_time_label_position()

    # ═══════════════════════════════════════════════════════════════════════════
    # Zoom / Pan
    # ═══════════════════════════════════════════════════════════════════════════

    def wheelEvent(self, event):
        if not self.enable_zoom_pan:
            return super().wheelEvent(event)
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        self._scale = max(0.1, min(10.0, self._scale * zoom_factor))
        self._apply_zoom_pan()

    def mousePressEvent(self, event):
        if not self.enable_zoom_pan:
            return super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if not self.enable_zoom_pan or not self._panning:
            return super().mouseMoveEvent(event)
        delta = event.pos() - self._pan_start
        self._pan_offset[0] += delta.x()
        self._pan_offset[1] += delta.y()
        self._pan_start = event.pos()
        self._apply_zoom_pan()

    def mouseReleaseEvent(self, event):
        if not self.enable_zoom_pan:
            return super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event):
        if not self.enable_zoom_pan:
            return super().mouseDoubleClickEvent(event)
        self._scale = 1.0
        self._pan_offset = [0, 0]
        self._apply_zoom_pan()

    def _apply_zoom_pan(self):
        if self._current_pixmap is None:
            return
        scaled_w = int(self._current_pixmap.width() * self._scale)
        scaled_h = int(self._current_pixmap.height() * self._scale)
        scaled_pixmap = self._current_pixmap.scaled(
            scaled_w, scaled_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        container_w = self.image_container.width()
        container_h = self.image_container.height()
        result = QPixmap(container_w, container_h)
        result.fill(QColor("#1a1a1a"))
        x = (container_w - scaled_w) // 2 + self._pan_offset[0]
        y = (container_h - scaled_h) // 2 + self._pan_offset[1]
        painter = QPainter(result)
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end()
        self.image_label.setPixmap(result)

    def _update_settings_btn_position(self):
        x = self.image_container.width() - self.settings_btn.width() - 10
        self.settings_btn.move(max(0, x), 10)
        self.settings_btn.raise_()

    def _update_time_label_position(self):
        x = (self.image_container.width() - self.time_label.width()) // 2
        self.time_label.move(max(0, x), 10)

    @staticmethod
    def _numpy_to_pixmap(image: np.ndarray) -> QPixmap:
        if image.ndim == 2:
            h, w = image.shape
            return QPixmap.fromImage(QImage(image.data, w, h, w, QImage.Format_Grayscale8))
        h, w, c = image.shape
        if c == 3:
            img = image[:, :, ::-1].copy()
            return QPixmap.fromImage(QImage(img.data, w, h, 3 * w, QImage.Format_RGB888))
        elif c == 4:
            return QPixmap.fromImage(QImage(image.data, w, h, 4 * w, QImage.Format_RGBA8888))
        raise ValueError(f"Unsupported channels: {c}")

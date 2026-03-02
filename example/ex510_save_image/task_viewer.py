# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-02
"""
ImiCameraView Widget (DeviceProperty 버전)
==========================================
QWidget 기반 이미지 뷰어 (RMI 수신 → UI 업데이트)

ex130 대비 변경점:
  - camera_client.is_opened → camera_client.is_connect (DeviceProperty)
  - trigger_mode_state/exposure_value 로컬 프로퍼티 제거 → DeviceProperty 직접 사용
  - snapshot() 활용으로 카메라 상태 일괄 조회 가능
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
    QDialog, QSlider, QToolButton, QComboBox, QTabWidget
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

        if self.isChecked():
            bg_color = QColor("#0078d4")
        else:
            bg_color = QColor("#555555")

        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(QRectF(0, 0, 40, 21), 10, 10)

        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(QRectF(self._handle_position, 2.5, 16, 16))

    def hitButton(self, pos):
        return self.rect().contains(pos)


# 블랙 테마 스타일
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
QSpinBox, QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
}
QCheckBox {
    spacing: 8px;
}
QLabel {
    color: #d4d4d4;
}
"""


@task( )
class ImiCameraView(QWidget):
    """이미지 뷰어 위젯 (@task + QWidget)"""
    _frame_ready = QtSignal(object, int, float)  # image, total_count, fps

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
        self.enable_zoom_pan = False

        # 화면 갱신 주기 제한
        self._last_display_time = 0.0
        self._display_interval = 1.0 / 60  # 최대 60 FPS 표시

        # 연결 상태 추적
        self._is_connected = False
        self._disconnect_time = None

        # 로컬 캐시 (설정 다이얼로그용)
        self._trigger_mode = False
        self._exposure_value = 15000

        self._init_ui()
        self._frame_ready.connect(self._on_frame_ready_ui)

    @property
    def camera_client(self):
        return self.target

    def run(self):
        if self.target:
            self._sync_camera_state()
            print(f"[ImiCameraView] Service started with target: {self.target}")

    def _sync_camera_state(self):
        """카메라 DeviceProperty 상태를 로컬에 동기화"""
        if not self.target:
            return
        try:
            # DeviceProperty: is_connect (기존 is_opened 대체)
            is_connected = bool(self.target.is_connect)
            self._is_connected = is_connected
            self._update_settings_icon_color(is_connected)
            if is_connected:
                self._disconnect_time = None

            # snapshot()으로 전체 속성 일괄 조회
            try:
                snap = self.target.snapshot()
                self._trigger_mode = snap.get("trigger_mode", False)
                self._exposure_value = snap.get("exposure", 15000)
            except Exception:
                pass
        except Exception:
            pass

    def _update_settings_icon_color(self, connected: bool):
        color = QColor("#00ff00") if connected else QColor("#ff4444")
        self.settings_btn.setIcon(self._create_settings_icon(color))

    def _init_ui(self):
        self.setStyleSheet(DARK_STYLE)
        layout = QVBoxLayout(self)

        self.image_container = QWidget()
        self.image_container.setMinimumSize(640, 480)
        layout.addWidget(self.image_container)

        self.image_label = QLabel(self.image_container)
        self.image_label.setGeometry(0, 0, 640, 480)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background-color: #1a1a1a;")

        self.stats_label = QLabel("000 (0.0)", self.image_container)
        self.stats_label.setStyleSheet(
            "color: #00ff00; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )
        self.stats_label.move(10, 10)

        self.time_label = QLabel("", self.image_container)
        self.time_label.setStyleSheet(
            "color: #ffffff; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )
        self.time_label.hide()

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

        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time_display)
        self._time_timer.start(1000)

    def _on_trigger_mode_changed(self, checked: bool):
        """트리거 모드 → DeviceProperty 직접 설정"""
        self._trigger_mode = checked
        if self.camera_client:
            try:
                self.camera_client.trigger_mode = checked
            except Exception:
                pass

    def _on_exposure_changed(self, value: int):
        """노출값 → DeviceProperty 직접 설정"""
        self._exposure_value = value
        if self.camera_client:
            try:
                self.camera_client.exposure = value
            except Exception:
                pass

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
        """설정 대화창 표시"""
        # 열기 전 최신 상태 동기화
        self._sync_camera_state()

        dialog = QDialog(self)
        dialog.setWindowTitle("Camera Settings (DeviceProperty)")
        dialog.setFixedSize(500, 400)
        dialog.setStyleSheet("""
            QDialog { background-color: #2d2d2d; color: white; }
            QTabWidget::pane { border: 1px solid #555; border-radius: 4px; }
            QTabBar::tab { background-color: #3d3d3d; padding: 8px 16px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: #0078d4; }
            QTabBar::tab:hover:!selected { background-color: #4d4d4d; }
        """)

        layout = QVBoxLayout(dialog)

        slider_style = (
            "QSlider::groove:horizontal { background: #555; height: 8px; border-radius: 4px; }"
            "QSlider::handle:horizontal { background: #0078d4; width: 18px; margin: -5px 0; border-radius: 9px; }"
            "QSlider::sub-page:horizontal { background: #0078d4; border-radius: 4px; }"
        )
        combo_style = (
            "QComboBox { background-color: #3d3d3d; border: 1px solid #555; padding: 4px; border-radius: 4px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #3d3d3d; selection-background-color: #0078d4; }"
        )
        groupbox_style = (
            "QGroupBox { border: 1px solid #555; border-radius: 4px; margin-top: 10px; padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )

        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # ===== 카메라 탭 =====
        camera_tab = QWidget()
        camera_layout = QVBoxLayout(camera_tab)

        # 카메라 상태 그룹
        status_group = QGroupBox("Camera Status")
        status_group.setStyleSheet(groupbox_style)
        status_layout = QHBoxLayout(status_group)

        # DeviceProperty: is_connect 사용
        is_connected = self._is_connected
        status_text = "CONNECTED" if is_connected else "DISCONNECTED"
        status_color = "#00ff00" if is_connected else "#ff4444"
        self.is_opened_label = QLabel(
            f"is_connect: <span style='color:{status_color}; font-weight:bold;'>{status_text}</span>")
        status_layout.addWidget(self.is_opened_label)
        status_layout.addStretch()
        camera_layout.addWidget(status_group)

        # 트리거 설정 그룹
        trigger_group = QGroupBox("Trigger")
        trigger_group.setStyleSheet(groupbox_style)
        trigger_layout = QHBoxLayout(trigger_group)

        trigger_layout.addWidget(QLabel("Source:"))
        self.trigger_source_combo = QComboBox()
        self.trigger_source_combo.addItems(["software", "hardware"])
        self.trigger_source_combo.setStyleSheet(combo_style)
        self.trigger_source_combo.currentTextChanged.connect(self._on_trigger_source_changed)
        trigger_layout.addWidget(self.trigger_source_combo)

        trigger_layout.addWidget(QLabel("Mode:"))
        self.trigger_mode_toggle = ToggleSwitch()
        self.trigger_mode_toggle.setChecked(self._trigger_mode)
        self.trigger_mode_toggle.toggled.connect(self._on_trigger_mode_changed)
        trigger_layout.addWidget(self.trigger_mode_toggle)
        trigger_layout.addStretch()
        camera_layout.addWidget(trigger_group)

        # 노출값 슬라이더
        exposure_layout = QHBoxLayout()
        exposure_layout.addWidget(QLabel("Exposure:"))
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(100, 100000)
        self.exposure_slider.setValue(self._exposure_value)
        self.exposure_slider.setStyleSheet(slider_style)
        exposure_layout.addWidget(self.exposure_slider)

        exposure_ms = self._exposure_value / 1000.0
        self.exposure_value_label = QLabel(f"{exposure_ms:.2f} ms")
        self.exposure_value_label.setFixedWidth(80)
        self.exposure_value_label.setStyleSheet("font-weight: bold;")
        exposure_layout.addWidget(self.exposure_value_label)
        camera_layout.addLayout(exposure_layout)

        max_fps = 1000000.0 / self._exposure_value if self._exposure_value > 0 else 0
        self.calc_fps_label = QLabel(f"Max FPS: {max_fps:.1f}")
        self.calc_fps_label.setStyleSheet("color: #ff4444; font-size: 11px; margin-left: 70px;")
        camera_layout.addWidget(self.calc_fps_label)

        self.exposure_slider.valueChanged.connect(self._on_exposure_slider_changed)

        camera_layout.addStretch()
        tab_widget.addTab(camera_tab, "카메라")

        # ===== 디바이스 탭 =====
        device_tab = QWidget()
        device_layout = QVBoxLayout(device_tab)

        overlay_group = QGroupBox("오버레이 표시")
        overlay_group.setStyleSheet(groupbox_style)
        overlay_layout = QVBoxLayout(overlay_group)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel("FPS 표시:"))
        self.show_fps_toggle = ToggleSwitch()
        self.show_fps_toggle.setChecked(self.show_fps_overlay)
        self.show_fps_toggle.toggled.connect(self._on_show_fps_changed)
        fps_row.addWidget(self.show_fps_toggle)
        fps_row.addStretch()
        overlay_layout.addLayout(fps_row)

        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("현재시간:"))
        self.show_time_toggle = ToggleSwitch()
        self.show_time_toggle.setChecked(self.show_time_overlay)
        self.show_time_toggle.toggled.connect(self._on_show_time_changed)
        time_row.addWidget(self.show_time_toggle)
        time_row.addStretch()
        overlay_layout.addLayout(time_row)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("확대/축소:"))
        self.zoom_pan_toggle = ToggleSwitch()
        self.zoom_pan_toggle.setChecked(self.enable_zoom_pan)
        self.zoom_pan_toggle.toggled.connect(self._on_zoom_pan_changed)
        zoom_row.addWidget(self.zoom_pan_toggle)
        zoom_row.addStretch()
        overlay_layout.addLayout(zoom_row)

        device_layout.addWidget(overlay_group)
        device_layout.addStretch()
        tab_widget.addTab(device_tab, "디바이스")

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "QPushButton { background-color: #0078d4; border: none; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1084d8; }"
        )
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec()

    def _on_exposure_slider_changed(self, value: int):
        exposure_ms = value / 1000.0
        max_fps = 1000000.0 / value if value > 0 else 0
        self.exposure_value_label.setText(f"{exposure_ms:.2f} ms")
        self.calc_fps_label.setText(f"Max FPS: {max_fps:.1f}")
        self._on_exposure_changed(value)

    def _on_trigger_source_changed(self, source: str):
        if self.camera_client:
            try:
                self.camera_client.trigger_source = source
            except Exception:
                pass

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

    def on_camera_received(self, signal):
        """Signal: 프레임 수신 — InvokeDispenser 스레드에서 직접 실행

        - 모든 프레임: FPS 카운트 (프레임 손실 없음)
        - 60 FPS분만: 버퍼 복사 → _frame_ready Signal → UI 스레드 표시
        - mfree는 save_image 태스크가 담당 (copy만 수행)
        """
        if not self.smblock:
            return

        data = signal.data
        sm_index = data["sm_index"]
        now = time.time()

        # FPS 카운터: 수신된 모든 프레임 계산
        self.frame_count += 1
        self.total_frame_count += 1
        elapsed = now - self.last_fps_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.last_fps_time = now

        # 표시 주기 외 프레임: 스킵 (버퍼 복사/변환 없음)
        if now - self._last_display_time < self._display_interval:
            return

        self._last_display_time = now
        image = self.smblock.get_buffer(sm_index).copy()
        # Qt Signal로 UI 스레드에 전달 (자동 queued connection)
        self._frame_ready.emit(image, self.total_frame_count, self.fps)

    def _on_frame_ready_ui(self, image, total_count, current_fps):
        """UI 스레드: 프레임 표시 (_frame_ready Signal 수신)"""
        pixmap = self._numpy_to_pixmap(image)
        self._current_pixmap = pixmap

        if self.enable_zoom_pan and self._scale != 1.0:
            self._apply_zoom_pan()
        else:
            self.image_label.setPixmap(pixmap)

        if self.show_fps_overlay:
            self.stats_label.setText(f"{total_count:03d} ({current_fps:.1f})")
            self.stats_label.adjustSize()
            self.stats_label.raise_()

    @ui_thread
    def on_camera_connected(self, signal):
        """Signal: 카메라 연결"""
        self._is_connected = True
        self._disconnect_time = None
        self._update_settings_icon_color(True)
        self.stats_label.setStyleSheet(
            "color: #00ff00; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )

    @ui_thread
    def on_camera_disconnected(self, signal):
        """Signal: 카메라 연결 해제"""
        self._is_connected = False
        self._disconnect_time = time.time()
        self._update_settings_icon_color(False)
        self.stats_label.setStyleSheet(
            "color: #ff4444; font-size: 14px; font-weight: bold; "
            "background-color: rgba(0, 0, 0, 150); padding: 5px;"
        )

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.image_label.setGeometry(0, 0, self.image_container.width(), self.image_container.height())
        self._update_settings_btn_position()
        self._update_time_label_position()

    def wheelEvent(self, event):
        if not self.enable_zoom_pan:
            return super().wheelEvent(event)

        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        new_scale = self._scale * zoom_factor
        new_scale = max(0.1, min(10.0, new_scale))
        self._scale = new_scale
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
            scaled_w, scaled_h,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
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

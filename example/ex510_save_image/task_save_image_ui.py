# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-02
"""
SaveImageUI — 이미지 저장 UI 패널
=================================
Save/Stop 버튼, 세션 테이블, 미리보기, 이미지 뷰어를 제공하는 UI 패널.

Classes:
    ImageViewerDialog   QDialog  — 이미지 뷰어 (네비게이션 + 확대/패닝 + 삭제)
    SaveImageUI         @task    — 저장 UI 패널 (테이블 + 미리보기)

주요 함수:
    _numpy_to_pixmap    — numpy BGR/Gray/RGBA → QPixmap 변환

ImageViewerDialog 조작:
    마우스 휠       — 확대/축소
    좌클릭 드래그   — 패닝 (확대 시)
    더블클릭        — fit ↔ 100% 토글
    ←/→ 키          — 이전/다음 이미지
    +/-/0 키        — 확대/축소/맞춤
    Delete 키       — 현재 이미지 삭제
    ESC             — 닫기

SaveImageUI 버튼:
    [Save/Stop]         — saver RMI (start_saving/stop_saving)
    [Scan]              — 세션 디렉토리 재스캔 (기존 갱신 + 새 세션 추가)

SaveImageUI 테이블 context 메뉴 (우클릭):
    Open                — ImageViewerDialog 열기
    Delete Session      — 세션 디렉토리 전체 삭제 (confirm)

SaveImageUI 시그널 수신 (@ui_thread):
    on_saver_saved      — 테이블 갱신 + 미리보기
    on_saver_session    — 세션 행 추가/종료
"""

import shutil
from pathlib import Path

import cv2
import numpy as np

from py_alaska import task, ui_thread

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QSplitter,
    QHeaderView, QAbstractItemView, QDialog, QMessageBox,
    QScrollArea, QMenu,
)
from PySide6.QtGui import QImage, QPixmap, QColor
from PySide6.QtCore import Qt


# ═══════════════════════════════════════════════════════════════════════════
# 상수
# ═══════════════════════════════════════════════════════════════════════════
COLOR_ACTIVE = "#4fc3f7"   # 활성 세션: 하늘색
COLOR_CLOSED = "#666666"   # 종료 세션: 회색
COLOR_DROPPED = "#ff4444"  # Dropped > 0: 빨간색

# ═══════════════════════════════════════════════════════════════════════════
# 스타일
# ═══════════════════════════════════════════════════════════════════════════
DARK_STYLE = """
QWidget        { background-color: #1e1e1e; color: #d4d4d4; }
QPushButton    { background-color: #0e639c; color: white;
                 border: none; border-radius: 4px; padding: 6px 12px; }
QPushButton:hover    { background-color: #1177bb; }
QPushButton:disabled { background-color: #3c3c3c; color: #6c6c6c; }
QPushButton:checked       { background-color: #d32f2f; }
QPushButton:checked:hover { background-color: #e53935; }
QTableWidget          { background-color: #252526;
                        border: 1px solid #3c3c3c; gridline-color: #3c3c3c; }
QTableWidget::item    { padding: 4px; }
QTableWidget::item:selected { background-color: #0e639c; }
QHeaderView::section  { background-color: #2d2d2d; color: #d4d4d4;
                        border: 1px solid #3c3c3c; padding: 4px; font-weight: bold; }
QLabel         { color: #d4d4d4; }
QScrollArea    { background-color: #1a1a1a; border: none; }
"""

STYLE_NAV_LABEL = "font-size: 14px; font-weight: bold;"
STYLE_INFO_LABEL = "font-size: 11px; color: #888;"
STYLE_PREVIEW_BG = "background-color: #1a1a1a;"
STYLE_BTN_DELETE = "background-color: #c62828; color: white; border-radius: 4px; padding: 6px;"
STYLE_BTN_DELETE_ALL = "background-color: #b71c1c; color: white; border-radius: 4px; padding: 6px;"


# ═══════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════
def _numpy_to_pixmap(image: np.ndarray) -> QPixmap:
    """numpy BGR/Grayscale/RGBA 이미지 → QPixmap 변환."""
    if image.ndim == 2:
        h, w = image.shape
        return QPixmap.fromImage(QImage(image.data, w, h, w, QImage.Format_Grayscale8))
    h, w, c = image.shape
    if c == 3:
        rgb = image[:, :, ::-1].copy()
        return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888))
    if c == 4:
        return QPixmap.fromImage(QImage(image.data, w, h, 4 * w, QImage.Format_RGBA8888))
    raise ValueError(f"Unsupported channels: {c}")


# ═══════════════════════════════════════════════════════════════════════════
# ImageViewerDialog
# ═══════════════════════════════════════════════════════════════════════════
class ImageViewerDialog(QDialog):
    """이미지 뷰어 대화창 — 네비게이션 + 확대/축소/패닝 + 삭제."""

    # ── 초기화 ──────────────────────────────────────────────────────────
    def __init__(self, parent, dir_path, session_text=""):
        super().__init__(parent)
        title = (f"Image Viewer — {session_text} — {dir_path}"
                 if session_text else f"Image Viewer — {dir_path}")
        self.setWindowTitle(title)
        self.resize(900, 700)
        self.setStyleSheet(DARK_STYLE)

        self._dir_path = dir_path
        self._files = sorted(Path(dir_path).glob("img_*"))
        self._index = len(self._files) - 1 if self._files else -1
        self._pixmap = None      # 원본 QPixmap (캐시)
        self._zoom = 0.0         # 0 = fit-to-window, >0 = 고정 배율
        self._dragging = False   # 마우스 드래그 패닝 상태
        self._drag_pos = None    # 드래그 시작 위치 (global)

        self._init_ui()
        self._show_current()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 상단 네비게이션 ──
        nav = QHBoxLayout()

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setFixedWidth(80)
        self.prev_btn.clicked.connect(self._go_prev)
        nav.addWidget(self.prev_btn)

        self.nav_label = QLabel("0 / 0")
        self.nav_label.setAlignment(Qt.AlignCenter)
        self.nav_label.setStyleSheet(STYLE_NAV_LABEL)
        nav.addWidget(self.nav_label)

        self.zoom_label = QLabel("Fit")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setFixedWidth(60)
        self.zoom_label.setStyleSheet(STYLE_INFO_LABEL)
        nav.addWidget(self.zoom_label)

        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setFixedWidth(80)
        self.next_btn.clicked.connect(self._go_next)
        nav.addWidget(self.next_btn)

        layout.addLayout(nav)

        # ── 파일명 표시 ──
        self.filename_label = QLabel("")
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setStyleSheet(STYLE_INFO_LABEL)
        layout.addWidget(self.filename_label)

        # ── 이미지 (QScrollArea + QLabel) ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setMinimumSize(400, 400)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        # ── 하단 삭제 버튼 ──
        del_layout = QHBoxLayout()
        del_layout.addStretch()

        self.del_img_btn = QPushButton("Delete Image")
        self.del_img_btn.setFixedWidth(120)
        self.del_img_btn.setStyleSheet(STYLE_BTN_DELETE)
        self.del_img_btn.clicked.connect(self._on_delete_image)
        del_layout.addWidget(self.del_img_btn)

        self.del_all_btn = QPushButton("Delete All")
        self.del_all_btn.setFixedWidth(120)
        self.del_all_btn.setStyleSheet(STYLE_BTN_DELETE_ALL)
        self.del_all_btn.clicked.connect(self._on_delete_all)
        del_layout.addWidget(self.del_all_btn)

        del_layout.addStretch()
        layout.addLayout(del_layout)

    # ── 네비게이션 ──────────────────────────────────────────────────────
    def _go_prev(self):
        if self._index > 0:
            self._index -= 1
            self._show_current()

    def _go_next(self):
        if self._index < len(self._files) - 1:
            self._index += 1
            self._show_current()

    def _show_current(self):
        """현재 인덱스 이미지 로드 + 표시. 빈 목록 시 UI 비활성화."""
        total = len(self._files)
        if total == 0 or self._index < 0:
            self.nav_label.setText("0 / 0")
            self.filename_label.setText("")
            self.image_label.clear()
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.del_img_btn.setEnabled(False)
            self.del_all_btn.setEnabled(False)
            self._pixmap = None
            return

        self.nav_label.setText(f"{self._index + 1} / {total}")
        self.prev_btn.setEnabled(self._index > 0)
        self.next_btn.setEnabled(self._index < total - 1)
        self.del_img_btn.setEnabled(True)
        self.del_all_btn.setEnabled(True)

        filepath = self._files[self._index]
        self.filename_label.setText(filepath.name)

        try:
            img = cv2.imread(str(filepath))
            if img is None:
                self.image_label.setText("(읽기 실패)")
                self._pixmap = None
                return
            self._pixmap = _numpy_to_pixmap(img)
            self._zoom = 0.0
            self._apply_zoom()
        except Exception:
            self.image_label.setText("(오류)")
            self._pixmap = None

    # ── 확대/축소 ──────────────────────────────────────────────────────
    def _apply_zoom(self):
        """현재 _zoom 배율로 이미지 표시."""
        if self._pixmap is None:
            return
        if self._zoom <= 0:
            area_size = self.scroll_area.viewport().size()
            scaled = self._pixmap.scaled(
                area_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.zoom_label.setText("Fit")
        else:
            w = int(self._pixmap.width() * self._zoom)
            h = int(self._pixmap.height() * self._zoom)
            scaled = self._pixmap.scaled(
                w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.zoom_label.setText(f"{int(self._zoom * 100)}%")
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def _get_fit_ratio(self):
        """현재 뷰포트 대비 fit 배율 계산."""
        area = self.scroll_area.viewport().size()
        return min(
            area.width() / max(self._pixmap.width(), 1),
            area.height() / max(self._pixmap.height(), 1))

    def _zoom_in(self):
        if self._pixmap is None:
            return
        if self._zoom <= 0:
            self._zoom = self._get_fit_ratio()
        self._zoom = min(self._zoom * 1.25, 10.0)
        self._apply_zoom()

    def _zoom_out(self):
        if self._pixmap is None:
            return
        if self._zoom <= 0:
            self._zoom = self._get_fit_ratio()
        self._zoom = max(self._zoom / 1.25, 0.01)
        self._apply_zoom()

    def _zoom_fit(self):
        self._zoom = 0.0
        self._apply_zoom()

    # ── 삭제 ───────────────────────────────────────────────────────────
    def _on_delete_image(self):
        """현재 이미지 1장 삭제 (confirm)."""
        if self._index < 0 or self._index >= len(self._files):
            return
        filepath = self._files[self._index]
        reply = QMessageBox.question(
            self, "Delete Image",
            f"Delete '{filepath.name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            filepath.unlink()
        except OSError:
            return
        del self._files[self._index]
        if self._index >= len(self._files):
            self._index = len(self._files) - 1
        self._show_current()

    def _on_delete_all(self):
        """세션 디렉토리 전체 삭제 (confirm)."""
        reply = QMessageBox.question(
            self, "Delete All",
            f"Delete entire directory?\n{self._dir_path}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        try:
            shutil.rmtree(self._dir_path)
        except OSError:
            return
        self._files.clear()
        self._index = -1
        self._show_current()
        self.close()

    # ── Qt 이벤트 ──────────────────────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_zoom()

    def wheelEvent(self, event):
        """마우스 휠 → 확대/축소 (스크롤 위치 비율 유지)."""
        if event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        old_h = h_bar.value() / max(h_bar.maximum(), 1) if h_bar.maximum() > 0 else 0.5
        old_v = v_bar.value() / max(v_bar.maximum(), 1) if v_bar.maximum() > 0 else 0.5

        if event.angleDelta().y() > 0:
            self._zoom_in()
        else:
            self._zoom_out()

        h_bar.setValue(int(old_h * h_bar.maximum()))
        v_bar.setValue(int(old_v * v_bar.maximum()))
        event.accept()

    def mousePressEvent(self, event):
        """좌클릭 드래그 시작 → 패닝 (확대 상태에서만)."""
        if event.button() == Qt.LeftButton and self._zoom > 0:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """드래그 중 → 스크롤바 이동."""
        if self._dragging and self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._drag_pos = event.globalPosition().toPoint()
            self.scroll_area.horizontalScrollBar().setValue(
                self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """드래그 종료 → 커서 복원."""
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self._drag_pos = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """더블클릭 → fit ↔ 100% 토글."""
        if event.button() == Qt.LeftButton:
            if self._zoom > 0:
                self._zoom_fit()
            else:
                self._zoom = 1.0
                self._apply_zoom()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """키보드: ←→ 네비게이션, +/-/0 줌, Delete 삭제, ESC 닫기."""
        key = event.key()
        if key == Qt.Key_Left:
            self._go_prev()
        elif key == Qt.Key_Right:
            self._go_next()
        elif key == Qt.Key_Escape:
            self.close()
        elif key == Qt.Key_Delete:
            self._on_delete_image()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._zoom_in()
        elif key == Qt.Key_Minus:
            self._zoom_out()
        elif key == Qt.Key_0:
            self._zoom_fit()
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# SaveImageUI Task
# ═══════════════════════════════════════════════════════════════════════════
@task()
class SaveImageUI(QWidget):
    """이미지 저장 UI 패널 (@task + QWidget).

    config.json 주입:
        target  — inject("client:saver") — saver RMI 프록시
    """

    def __init__(self):
        super().__init__()
        self.target = None
        self._saving = False
        self._save_path = ""
        self._session_row = -1
        self._init_ui()

    def run(self):
        """초기화 (시작 시 saver 미기동 → RMI 호출 없음)."""
        pass

    # ═══════════════════════════════════════════════════════════════════
    # UI 초기화
    # ═══════════════════════════════════════════════════════════════════
    def _init_ui(self):
        self.setStyleSheet(DARK_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Save/Stop + Scan 버튼 ──
        ctrl_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.setCheckable(True)
        self.save_btn.setFixedHeight(32)
        self.save_btn.clicked.connect(self._on_save_toggle)
        ctrl_layout.addWidget(self.save_btn)

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.setFixedHeight(32)
        self.scan_btn.clicked.connect(self._on_scan_click)
        ctrl_layout.addWidget(self.scan_btn)
        layout.addLayout(ctrl_layout)

        # ── 스플리터: 테이블 + 미리보기 ──
        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Directory", "Session", "Saved", "Dropped"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents)
        self.table.setMaximumHeight(200)
        self.table.doubleClicked.connect(self._on_table_double_click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        splitter.addWidget(self.table)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setStyleSheet(STYLE_PREVIEW_BG)
        splitter.addWidget(self.preview_label)

        splitter.setSizes([150, 350])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    # ═══════════════════════════════════════════════════════════════════
    # 버튼 핸들러
    # ═══════════════════════════════════════════════════════════════════
    def _on_save_toggle(self, checked):
        """Save/Stop 토글 → saver RMI 호출."""
        if not self.target:
            self.save_btn.setChecked(False)
            return
        try:
            if checked:
                self.target.start_saving()
                self.save_btn.setText("Stop")
                self._saving = True
            else:
                self.target.stop_saving()
                self.save_btn.setText("Save")
                self._saving = False
        except Exception:
            self.save_btn.setChecked(False)

    def _on_scan_click(self):
        """Scan 버튼 → 세션 디렉토리 재스캔 (기존 행 갱신 + 새 세션 추가)."""
        base_dir = self._find_base_dir()
        if base_dir is None:
            return
        self._scan_sessions(base_dir)

    def _on_table_double_click(self, index):
        """테이블 행 더블클릭 → ImageViewerDialog → 닫힌 후 재스캔."""
        self._open_viewer(index.row())

    def _open_viewer(self, row):
        """지정 행의 세션 디렉토리를 ImageViewerDialog로 열기."""
        dir_item = self.table.item(row, 0)
        if not dir_item:
            return
        dir_path = dir_item.data(Qt.UserRole)
        if not dir_path or not Path(dir_path).exists():
            return
        session_item = self.table.item(row, 1)
        session_text = session_item.text() if session_item else ""
        dlg = ImageViewerDialog(self, dir_path, session_text)
        dlg.exec()
        self._rescan_row(row, dir_path)

    def _on_context_menu(self, pos):
        """테이블 우클릭 → context 메뉴 (Open / Delete Session)."""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        dir_item = self.table.item(row, 0)
        if not dir_item:
            return
        dir_path = dir_item.data(Qt.UserRole)
        if not dir_path:
            return

        menu = QMenu(self)
        open_action = menu.addAction("Open")
        menu.addSeparator()
        delete_action = menu.addAction("Delete Session")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == open_action:
            self._open_viewer(row)
        elif action == delete_action:
            self._delete_session(row, dir_path)

    # ═══════════════════════════════════════════════════════════════════
    # 시그널 수신 (saver → UI, @ui_thread 필수)
    # ═══════════════════════════════════════════════════════════════════
    @ui_thread
    def on_saver_saved(self, signal):
        """저장 완료 1건 → 테이블 갱신 + 미리보기."""
        data = signal.data
        seq = data.get("seq", 0)
        dropped = data.get("dropped", 0)
        filepath = data.get("path", "")

        if self._session_row < 0 and filepath:
            session_dir = str(Path(filepath).parent)
            self._save_path = session_dir
            self._add_session_row(session_dir, seq)

        self._update_session_row(saved=seq, dropped=dropped)

        if filepath:
            self._show_last_image(filepath)

    @ui_thread
    def on_saver_session(self, signal):
        """세션 상태 변경 (open/close)."""
        data = signal.data
        action = data.get("action", "")

        if action == "open":
            path = data.get("path", "")
            continued = data.get("continued", 0)
            self._save_path = path
            self._load_existing_sessions(path)
            self._add_session_row(path, continued)

        elif action == "close":
            saved = data.get("saved_count", 0)
            dropped = data.get("dropped_count", 0)
            self._close_session_row(saved, dropped)
            self._saving = False
            self.save_btn.setChecked(False)
            self.save_btn.setText("Save")

    # ═══════════════════════════════════════════════════════════════════
    # 테이블 관리
    # ═══════════════════════════════════════════════════════════════════
    def _find_base_dir(self):
        """테이블 행 또는 _save_path에서 base_dir(YYYY/MM/DD) 추출."""
        # 기존 행에서 추출
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                dp = item.data(Qt.UserRole)
                if dp:
                    p = Path(dp).parent
                    if p.exists():
                        return p
        # _save_path에서 추출
        if self._save_path:
            p = Path(self._save_path)
            base = p.parent if p.name.startswith("S") else p
            if base.exists():
                return base
        return None

    def _scan_sessions(self, base_dir):
        """base_dir 아래 세션 재스캔 — 기존 행 갱신/삭제 + 새 세션 추가."""
        # 기존 행 역순 재스캔 (삭제 시 인덱스 안정)
        for r in range(self.table.rowCount() - 1, -1, -1):
            item = self.table.item(r, 0)
            if not item:
                continue
            dp = item.data(Qt.UserRole)
            if not dp:
                continue
            p = Path(dp)
            if not p.exists():
                self._remove_row(r)
            elif r != self._session_row:
                cnt = len(list(p.glob("img_*")))
                saved_item = self.table.item(r, 2)
                if saved_item:
                    saved_item.setText(str(cnt))

        # 새 세션 검색 + 추가
        loaded = set()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                loaded.add(item.data(Qt.UserRole))

        try:
            dirs = sorted(base_dir.iterdir())
        except OSError:
            return

        for d in dirs:
            if not d.is_dir() or not d.name.startswith("S"):
                continue
            dir_path = str(d)
            if dir_path in loaded:
                continue

            img_count = len(list(d.glob("img_*")))
            row = self.table.rowCount()
            self.table.insertRow(row)

            dir_text = f"{d.parent.parent.name}/{d.parent.name}/{d.name}"
            dir_item = QTableWidgetItem(dir_text)
            dir_item.setData(Qt.UserRole, dir_path)
            self.table.setItem(row, 0, dir_item)

            self._set_centered_item(row, 1, d.name)
            self._set_centered_item(row, 2, img_count)
            self._set_centered_item(row, 3, "-")
            self._highlight_row(row, COLOR_CLOSED)

    def _load_existing_sessions(self, current_path):
        """기존 세션 디렉토리를 테이블에 로드 (회색, 종료 상태)."""
        p = Path(current_path)
        base_dir = p.parent  # save_path/YYYY/MM/DD
        if not base_dir.exists():
            return

        loaded = set()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                loaded.add(item.data(Qt.UserRole))

        try:
            dirs = sorted(base_dir.iterdir())
        except OSError:
            return

        for d in dirs:
            if not d.is_dir() or not d.name.startswith("S"):
                continue
            dir_path = str(d)
            if dir_path in loaded or dir_path == current_path:
                continue

            img_count = len(list(d.glob("img_*")))
            row = self.table.rowCount()
            self.table.insertRow(row)

            dir_text = f"{d.parent.parent.name}/{d.parent.name}/{d.name}"
            dir_item = QTableWidgetItem(dir_text)
            dir_item.setData(Qt.UserRole, dir_path)
            self.table.setItem(row, 0, dir_item)

            self._set_centered_item(row, 1, d.name)
            self._set_centered_item(row, 2, img_count)
            self._set_centered_item(row, 3, "-")
            self._highlight_row(row, COLOR_CLOSED)

    def _add_session_row(self, path, continued=0):
        """새 세션 행 추가 (활성: 하늘색)."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._session_row = row

        p = Path(path)
        dir_text = (f"{p.parent.parent.name}/{p.parent.name}/{p.name}"
                    if path else "-")
        dir_item = QTableWidgetItem(dir_text)
        dir_item.setData(Qt.UserRole, path)
        self.table.setItem(row, 0, dir_item)

        self._set_centered_item(row, 1, p.name if path else "-")
        self._set_centered_item(row, 2, continued)
        self._set_centered_item(row, 3, "0")

        self._highlight_row(row, COLOR_ACTIVE)
        self.table.scrollToBottom()

    def _update_session_row(self, saved=None, dropped=None):
        """현재 세션 행의 saved/dropped 갱신."""
        row = self._session_row
        if row < 0 or row >= self.table.rowCount():
            return

        if saved is not None:
            item = self.table.item(row, 2)
            if item:
                item.setText(str(saved))

        if dropped is not None:
            item = self.table.item(row, 3)
            if item:
                item.setText(str(dropped))
                if dropped > 0:
                    item.setForeground(QColor(COLOR_DROPPED))

    def _close_session_row(self, saved, dropped):
        """세션 종료 → 회색 처리."""
        row = self._session_row
        if row < 0 or row >= self.table.rowCount():
            return
        self._update_session_row(saved=saved, dropped=dropped)
        self._highlight_row(row, COLOR_CLOSED)
        self._session_row = -1

    def _delete_session(self, row, dir_path):
        """세션 디렉토리 삭제 (confirm) + 테이블 행 제거."""
        if not Path(dir_path).exists():
            self._remove_row(row)
            return

        if self._session_row == row and self._saving:
            QMessageBox.warning(
                self, "Delete Session",
                "Cannot delete active saving session.\nStop saving first.")
            return

        reply = QMessageBox.question(
            self, "Delete Session",
            f"Delete entire session directory?\n{dir_path}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        try:
            shutil.rmtree(dir_path)
        except OSError:
            return
        self._remove_row(row)

    def _rescan_row(self, row, dir_path):
        """대화창 닫힘 → 디렉토리 재스캔하여 행 갱신/제거."""
        if not Path(dir_path).exists():
            self._remove_row(row)
            return
        img_count = len(list(Path(dir_path).glob("img_*")))
        item = self.table.item(row, 2)
        if item:
            item.setText(str(img_count))

    def _remove_row(self, row):
        """테이블 행 제거 + _session_row 인덱스 보정."""
        self.table.removeRow(row)
        if self._session_row == row:
            self._session_row = -1
        elif self._session_row > row:
            self._session_row -= 1

    def _set_centered_item(self, row, col, text):
        """중앙 정렬 QTableWidgetItem 생성 + 배치."""
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)

    def _highlight_row(self, row, color):
        """행 전체 전경색 변경."""
        qcolor = QColor(color)
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setForeground(qcolor)

    # ═══════════════════════════════════════════════════════════════════
    # 미리보기 (마지막 저장 이미지)
    # ═══════════════════════════════════════════════════════════════════
    def _show_last_image(self, filepath):
        """마지막 저장된 이미지를 미리보기 라벨에 표시."""
        try:
            img = cv2.imread(filepath)
            if img is None:
                return
            pixmap = _numpy_to_pixmap(img)
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation)
            self.preview_label.setPixmap(scaled)
        except Exception:
            pass

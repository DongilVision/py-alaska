# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""GUI Task - IPC Performance Test (Dark Theme, 3-Column Layout)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import time
import json
import statistics
from datetime import datetime
from typing import List
from threading import Thread

from py_alaska import task

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QSpinBox,
    QProgressBar, QTabWidget, QCheckBox
)
from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtGui import QFont, QShortcut, QKeySequence

# ── Dark Theme Stylesheet ──────────────────────────────────────
DARK_STYLE = """
QWidget {
    background-color: #222222;
    color: #e0e0e0;
    font-family: "Segoe UI", Arial;
}
QFrame#card {
    background: #2b2b2b;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
}
QFrame#card:hover {
    border: 1px solid #4FC3F7;
}
QFrame#separator {
    background: #3a3a3a;
    max-height: 1px;
}
QSpinBox {
    background: #2b2b2b;
    border: 1px solid #444;
    border-radius: 3px;
    color: white;
    padding: 4px 8px;
    font-size: 13px;
}
QPushButton {
    background: #333;
    border: 1px solid #555;
    color: white;
    padding: 6px 14px;
    border-radius: 4px;
    font-size: 12px;
}
QPushButton:hover {
    background: #444;
    border-color: #4FC3F7;
}
QPushButton:pressed {
    background: #222;
}
QPushButton:disabled {
    background: #222;
    color: #555;
    border-color: #333;
}
QPushButton#startBtn {
    background: #2196F3;
    border: none;
    font-weight: bold;
    padding: 8px;
}
QPushButton#startBtn:hover {
    background: #42A5F5;
}
QPushButton#startBtn:disabled {
    background: #1a3a5c;
    color: #556;
}
QProgressBar {
    border: 1px solid #333;
    border-radius: 3px;
    background: #252525;
    text-align: center;
    color: #aaa;
    font-size: 11px;
}
QProgressBar::chunk {
    background: #4CAF50;
    border-radius: 2px;
}
QTabWidget::pane {
    border: 1px solid #333;
    background: #222222;
}
QTabBar::tab {
    background: #2b2b2b;
    color: #888;
    border: 1px solid #333;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #222222;
    color: #4FC3F7;
    border-bottom: none;
}
QTabBar::tab:hover {
    color: #e0e0e0;
}
QCheckBox {
    color: #e0e0e0;
    font-size: 20px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 1px solid #555;
    border-radius: 3px;
    background: #2b2b2b;
}
QCheckBox::indicator:checked {
    background: #FF9800;
    border-color: #FF9800;
}
QCheckBox::indicator:hover {
    border-color: #4FC3F7;
}
"""


@task(name="PerformanceGui")
class PerformanceGui(QWidget):
    """IPC Performance Test GUI — Dark Theme, 3-Column Layout"""

    sig_progress = QtSignal(int, int)
    sig_test_done = QtSignal(str)

    WARMUP_COUNT = 10

    def __init__(self):
        super().__init__()
        self.setStyleSheet(DARK_STYLE)

        self.p1 = None  # RMI client (injected)
        self.p2 = None  # RMI client for contention (injected)
        self.p3 = None  # RMI client for contention (injected)
        self._running = False
        self._results: List[float] = []
        self._iterations_requested = 0
        self._stat_labels = {}
        self._btn_starts: List[QPushButton] = []
        self._selected_test = "ipc"

        self._init_ui()
        self._connect_signals()
        self._setup_shortcuts()

    # ── UI Construction ─────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 8, 12, 8)

        # Title
        title = QLabel("IPC Performance Test")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #ffffff; padding: 4px;")
        root.addWidget(title)

        # ── 3-column main area ──
        columns = QHBoxLayout()
        columns.setSpacing(10)

        # LEFT: Stats panel
        columns.addWidget(self._build_stats_panel())

        # CENTER: Graph
        columns.addWidget(self._build_graph_panel(), stretch=1)

        # RIGHT: Scenario list
        columns.addWidget(self._build_scenario_panel())

        root.addLayout(columns, stretch=1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        root.addWidget(self.progress_bar)

    def _build_stats_panel(self) -> QWidget:
        """Left panel — iteration count + statistics grid"""
        panel = QWidget()
        panel.setFixedWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Iteration count
        lbl = QLabel("시험 횟수")
        lbl.setStyleSheet("color: #888; font-size: 22px;")
        layout.addWidget(lbl)

        self.spin_iter = QSpinBox()
        self.spin_iter.setRange(100, 1000000)
        self.spin_iter.setValue(1000)
        self.spin_iter.setSingleStep(100)
        self.spin_iter.setStyleSheet(
            "QSpinBox { background: #2b2b2b; border: 1px solid #444; "
            "border-radius: 3px; color: white; padding: 6px 10px; font-size: 24px; }"
        )
        layout.addWidget(self.spin_iter)

        # Contention option
        self.chk_contention = QCheckBox("Contention")
        self.chk_contention.setToolTip(
            "ON: 흐름제어 없이 전부 emit (큐 경합 테스트)\n"
            "OFF: 배치별 수신 확인 (안정 모드)"
        )
        layout.addWidget(self.chk_contention)

        # Separator
        layout.addWidget(self._separator())

        # Stats grid
        grid = QGridLayout()
        grid.setSpacing(8)
        stats = [
            ("Avg", "avg"), ("Std", "std"), ("Min", "min"),
            ("Max", "max"), ("P95", "p95"), ("P99", "p99"),
            ("TPS", "tps"), ("Loss", "loss"),
        ]
        for row, (label, key) in enumerate(stats):
            name = QLabel(label)
            name.setStyleSheet("color: #888; font-size: 24px;")
            value = QLabel("-")
            value.setAlignment(Qt.AlignRight)
            color = "#FF5252" if key == "max" else "#4FC3F7"
            value.setStyleSheet(f"color: {color}; font-size: 24px; font-family: Consolas;")
            grid.addWidget(name, row, 0)
            grid.addWidget(value, row, 1)
            self._stat_labels[key] = value

        layout.addLayout(grid)
        layout.addStretch()

        # Export button
        self.btn_export = QPushButton("결과 저장")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export_results)
        layout.addWidget(self.btn_export)

        return panel

    def _build_graph_panel(self) -> QWidget:
        """Center panel — tabbed graphs (scatter + histogram)"""
        self.tab_graph = QTabWidget()

        # Tab 1: Time per iteration (scatter)
        self.fig_scatter = Figure(dpi=100, facecolor='#222222')
        self.canvas_scatter = FigureCanvas(self.fig_scatter)
        self.tab_graph.addTab(self.canvas_scatter, "시도별 측정시간")

        # Tab 2: Histogram (100 bins)
        self.fig_hist = Figure(dpi=100, facecolor='#222222')
        self.canvas_hist = FigureCanvas(self.fig_hist)
        self.tab_graph.addTab(self.canvas_hist, "히스토그램")

        self._draw_empty_graphs()

        return self.tab_graph

    def _build_scenario_panel(self) -> QWidget:
        """Right panel — test scenario cards"""
        panel = QWidget()
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QLabel("시험 시나리오")
        header.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(header)

        scenarios = [
            ("1. IPC Test", "P1 → P2",
             "P1이 P2에게 직접 IPC 호출\nP2가 수신 소요시간 측정", "ipc"),
            ("2. 3-Hop Test", "P1 → P2 → P3 → P4",
             "3-hop 체인 IPC 호출\nP4에서 수신시간 측정", "hop"),
            ("3. Signal Test", "P1 → P2",
             "P1이 P2에게 시그널 발신\nP2가 수신 소요시간 측정", "sig"),
            ("4. Signal 3-Hop", "P1 → P2 → P3 → P4",
             "3-hop 시그널 체인\nP4에서 수신시간 측정", "sig3hop"),
        ]
        self._scenario_cards = []
        for name, route, desc, test_type in scenarios:
            card, btn = self._scenario_card(name, route, desc, test_type)
            layout.addWidget(card)
            self._btn_starts.append(btn)
            self._scenario_cards.append((card, test_type))

        layout.addStretch()
        return panel

    def _scenario_card(self, name: str, route: str, desc: str, test_type: str):
        """Create a styled scenario card with start button"""
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        title = QLabel(name)
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        layout.addWidget(title)

        route_lbl = QLabel(route)
        route_lbl.setStyleSheet("color: #4FC3F7; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(route_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #888; font-size: 10px; border: none; background: transparent;")
        layout.addWidget(desc_lbl)

        btn = QPushButton("시작  (F5)")
        btn.setObjectName("startBtn")
        btn.clicked.connect(lambda: self._select_and_start(test_type))
        layout.addWidget(btn)

        return card, btn

    def _select_and_start(self, test_type: str):
        """Select scenario and start test"""
        self._selected_test = test_type
        self._update_card_selection()
        self._start_test(test_type)

    def _update_card_selection(self):
        """Highlight the selected scenario card"""
        for card, t in self._scenario_cards:
            if t == self._selected_test:
                card.setStyleSheet(
                    "QFrame#card { background: #2b2b2b; border: 2px solid #4FC3F7; border-radius: 6px; }"
                )
            else:
                card.setStyleSheet("")

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        return sep

    def _draw_empty_graphs(self):
        """Draw placeholder axes on both tabs"""
        for fig, canvas, xlabel, ylabel in [
            (self.fig_scatter, self.canvas_scatter, 'Iteration', 'Elapsed (ms)'),
            (self.fig_hist, self.canvas_hist, 'Elapsed (ms)', 'Count'),
        ]:
            fig.clear()
            ax = fig.add_subplot(111)
            self._style_axes(ax)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title('Ready', fontsize=12, color='#888')
            fig.tight_layout()
            canvas.draw()

    def _style_axes(self, ax):
        """Apply dark theme to axes"""
        ax.set_facecolor('#252525')
        ax.tick_params(colors='#aaa', labelsize=9)
        ax.xaxis.label.set_color('#aaa')
        ax.yaxis.label.set_color('#aaa')
        for spine in ax.spines.values():
            spine.set_color('#444')
        ax.grid(True, alpha=0.15, color='#666')

    # ── Shortcuts ─────────────────────────────────────────────

    def _setup_shortcuts(self):
        """F5: start selected test, F11: toggle fullscreen"""
        QShortcut(QKeySequence(Qt.Key_F5), self).activated.connect(
            lambda: self._start_test(self._selected_test)
        )
        QShortcut(QKeySequence(Qt.Key_F11), self).activated.connect(
            self._toggle_fullscreen
        )

    def _toggle_fullscreen(self):
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
        else:
            win.showFullScreen()

    # ── Signal connections ──────────────────────────────────────

    def _connect_signals(self):
        self.sig_progress.connect(self._on_progress)
        self.sig_test_done.connect(self._on_test_done)

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_test_done(self, test_name: str):
        """Update graph + stats on main thread"""
        self._set_buttons_enabled(True)
        if not self._results:
            return

        results = self._results
        n = len(results)
        avg = statistics.mean(results)
        std = statistics.stdev(results) if n > 1 else 0
        mn, mx = min(results), max(results)
        sr = sorted(results)
        p95 = sr[int(n * 0.95)]
        p99 = sr[int(n * 0.99)]
        tps = 1000 / avg if avg > 0 else 0

        # Loss
        req = self._iterations_requested
        loss = req - n if req > 0 else 0
        loss_pct = (loss / req * 100) if req > 0 else 0

        # Update stat labels
        self._stat_labels["avg"].setText(f"{avg:.4f} ms")
        self._stat_labels["std"].setText(f"{std:.4f} ms")
        self._stat_labels["min"].setText(f"{mn:.4f} ms")
        self._stat_labels["max"].setText(f"{mx:.4f} ms")
        self._stat_labels["p95"].setText(f"{p95:.4f} ms")
        self._stat_labels["p99"].setText(f"{p99:.4f} ms")
        self._stat_labels["tps"].setText(f"{tps:,.0f}")
        self._stat_labels["loss"].setText(f"{loss} ({loss_pct:.1f}%)")

        # ── Tab 1: Scatter (time per iteration) ──
        self.fig_scatter.clear()
        ax1 = self.fig_scatter.add_subplot(111)
        self._style_axes(ax1)

        x = list(range(1, n + 1))
        ax1.scatter(x, results, s=2, alpha=0.5, color='#42A5F5', zorder=2)

        ax1.axhline(y=avg, color='#FF5252', linewidth=1.5,
                     label=f'Avg: {avg:.4f} ms', zorder=3)
        if std > 0:
            lo = max(0, avg - std)
            ax1.axhspan(lo, avg + std, alpha=0.12, color='#FF5252',
                         label=f'Std: \u00b1{std:.4f} ms', zorder=1)

        ax1.set_xlabel('Iteration')
        ax1.set_ylabel('Elapsed (ms)')
        ax1.set_title(test_name, fontsize=12, color='#e0e0e0', fontweight='bold')
        ax1.legend(loc='upper right', fontsize=9, facecolor='#2b2b2b',
                   edgecolor='#444', labelcolor='#ccc')
        self.fig_scatter.tight_layout()
        self.canvas_scatter.draw()

        # ── Tab 2: Histogram (100 bins) ──
        self.fig_hist.clear()
        ax2 = self.fig_hist.add_subplot(111)
        self._style_axes(ax2)

        ax2.hist(results, bins=100, color='#42A5F5', edgecolor='#1a1a1a',
                 alpha=0.85, zorder=2)

        ax2.axvline(x=avg, color='#FF5252', linewidth=1.5,
                     label=f'Avg: {avg:.4f} ms', zorder=3)
        if std > 0:
            lo = max(0, avg - std)
            ax2.axvspan(lo, avg + std, alpha=0.12, color='#FF5252',
                         label=f'Std: \u00b1{std:.4f} ms', zorder=1)

        ax2.set_xlabel('Elapsed (ms)')
        ax2.set_ylabel('Count')
        ax2.set_title(test_name, fontsize=12, color='#e0e0e0', fontweight='bold')
        ax2.legend(loc='upper right', fontsize=9, facecolor='#2b2b2b',
                   edgecolor='#444', labelcolor='#ccc')
        self.fig_hist.tight_layout()
        self.canvas_hist.draw()

        self.btn_export.setEnabled(True)

    # ── Button control ──────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._btn_starts:
            btn.setEnabled(enabled)
        self.spin_iter.setEnabled(enabled)
        self.chk_contention.setEnabled(enabled)

    def _start_test(self, test_type: str):
        if self._running:
            return
        if not self.p1:
            print("[ERROR] P1 client not available")
            return

        self._running = True
        self._set_buttons_enabled(False)
        self.btn_export.setEnabled(False)

        Thread(target=self._run_test, args=(test_type,), daemon=True).start()

    # ── Test execution (background thread) ──────────────────────

    def _run_test(self, test_type: str):
        try:
            iters = self.spin_iter.value()
            self._iterations_requested = iters
            if test_type == "ipc":
                self._run_ipc_test(iters)
            elif test_type == "hop":
                self._run_hop_test(iters)
            elif test_type == "sig":
                self._run_sig_test(iters)
            elif test_type == "sig3hop":
                self._run_sig_3hop_test(iters)
        finally:
            self._running = False

    def _ipc_load(self, client, iterations: int):
        """Background IPC load for contention testing"""
        for _ in range(iterations):
            try:
                client.ipc_call_next(time.perf_counter())
            except:
                pass

    def _start_contention_threads(self, iterations: int):
        """Start P2→P3, P3→P4 IPC load threads"""
        threads = []
        if self.p2:
            t = Thread(target=self._ipc_load, args=(self.p2, iterations), daemon=True)
            t.start()
            threads.append(t)
        if self.p3:
            t = Thread(target=self._ipc_load, args=(self.p3, iterations), daemon=True)
            t.start()
            threads.append(t)
        return threads

    def _run_ipc_test(self, iterations: int):
        contention = self.chk_contention.isChecked()
        mode = "contention" if contention else "single"
        name = f"IPC Test (P1\u2192P2) \u00d7{iterations} [{mode}]"
        print(f"=== {name} ===")
        self._results = []

        # Start contention load
        load_threads = []
        if contention:
            load_threads = self._start_contention_threads(iterations)
            print("Contention: P2\u2192P3, P3\u2192P4 load started")

        print(f"Warmup ({self.WARMUP_COUNT})...")
        for _ in range(self.WARMUP_COUNT):
            try:
                self.p1.ipc_call(time.perf_counter())
            except Exception as e:
                print(f"Warmup error: {e}")

        print(f"Running {iterations} iterations...")
        errors = 0
        for i in range(iterations):
            try:
                result = self.p1.ipc_call(time.perf_counter())
                self._results.append(result["elapsed_ms"])
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"Error: {e}")

            if (i + 1) % 50 == 0 or i == iterations - 1:
                self.sig_progress.emit(i + 1, iterations)

        # Wait for contention threads
        for t in load_threads:
            t.join(timeout=30)

        print(f"Done. {len(self._results)}/{iterations} ok, {errors} errors")
        self.sig_test_done.emit(name)

    def _run_hop_test(self, iterations: int):
        contention = self.chk_contention.isChecked()
        mode = "contention" if contention else "single"
        name = f"3-Hop (P1\u2192P2\u2192P3\u2192P4) \u00d7{iterations} [{mode}]"
        print(f"=== {name} ===")
        self._results = []

        # Start contention load
        load_threads = []
        if contention:
            load_threads = self._start_contention_threads(iterations)
            print("Contention: P2\u2192P3, P3\u2192P4 load started")

        print(f"Warmup ({self.WARMUP_COUNT})...")
        for _ in range(self.WARMUP_COUNT):
            try:
                self.p1.hop_call(time.perf_counter())
            except Exception as e:
                print(f"Warmup error: {e}")

        print(f"Running {iterations} iterations...")
        errors = 0
        for i in range(iterations):
            try:
                result = self.p1.hop_call(time.perf_counter())
                self._results.append(result["elapsed_ms"])
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"Error: {e}")

            if (i + 1) % 50 == 0 or i == iterations - 1:
                self.sig_progress.emit(i + 1, iterations)

        # Wait for contention threads
        for t in load_threads:
            t.join(timeout=30)

        print(f"Done. {len(self._results)}/{iterations} ok, {errors} errors")
        self.sig_test_done.emit(name)

    def _run_sig_test(self, iterations: int):
        """Test 3: Signal P1→P2 (batch emit + chunked collect)"""
        contention = self.chk_contention.isChecked()
        mode = "contention" if contention else "flow-ctrl"
        name = f"Signal (P1\u2192P2) \u00d7{iterations} [{mode}]"
        print(f"=== {name} ===")
        self._results = []
        CHUNK = 500

        self.sig_progress.emit(0, iterations)
        try:
            # Phase 1: Emit signals
            received = self.p1.sig_emit(iterations, contention)
            print(f"Signal emit done: {received}/{iterations} received")

            # Phase 2: Collect results in chunks (64KB buffer limit)
            for offset in range(0, received, CHUNK):
                chunk = self.p1.get_sig_chunk(offset, CHUNK)
                self._results.extend(chunk)
                self.sig_progress.emit(min(offset + CHUNK, received), iterations)

            print(f"Collected {len(self._results)} results")
        except Exception as e:
            print(f"Signal test error: {e}")

        self.sig_progress.emit(iterations, iterations)
        self.sig_test_done.emit(name)

    def _run_sig_3hop_test(self, iterations: int):
        """Test 4: Signal 3-hop P1→P2→P3→P4 (batch emit + chunked collect)"""
        contention = self.chk_contention.isChecked()
        mode = "contention" if contention else "flow-ctrl"
        name = f"Signal 3-Hop (P1\u2192P2\u2192P3\u2192P4) \u00d7{iterations} [{mode}]"
        print(f"=== {name} ===")
        self._results = []
        CHUNK = 500

        self.sig_progress.emit(0, iterations)
        try:
            # Phase 1: Emit signals
            received = self.p1.sig_3hop_emit(iterations, contention)
            print(f"Signal 3-hop emit done: {received}/{iterations} received")

            # Phase 2: Collect results in chunks
            for offset in range(0, received, CHUNK):
                chunk = self.p1.get_hop_chunk(offset, CHUNK)
                self._results.extend(chunk)
                self.sig_progress.emit(min(offset + CHUNK, received), iterations)

            print(f"Collected {len(self._results)} results")
        except Exception as e:
            print(f"Signal 3-hop test error: {e}")

        self.sig_progress.emit(iterations, iterations)
        self.sig_test_done.emit(name)

    # ── Export ──────────────────────────────────────────────────

    def _export_results(self):
        if not self._results:
            return

        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = results_dir / f"performance_{ts}.json"

        n = len(self._results)
        sr = sorted(self._results)
        avg = statistics.mean(self._results)

        data = {
            "timestamp": datetime.now().isoformat(),
            "iterations": n,
            "metrics": {
                "avg_ms": avg,
                "std_ms": statistics.stdev(self._results) if n > 1 else 0,
                "min_ms": min(self._results),
                "max_ms": max(self._results),
                "p50_ms": statistics.median(self._results),
                "p95_ms": sr[int(n * 0.95)],
                "p99_ms": sr[int(n * 0.99)],
                "tps": 1000 / avg if avg > 0 else 0,
            },
            "raw_elapsed_ms": self._results,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"Exported: {filepath.name}")

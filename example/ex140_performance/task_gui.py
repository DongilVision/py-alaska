# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""GUI Task - Performance Test Orchestrator & Result Viewer (Qt)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import time
import json
import statistics
from datetime import datetime
from typing import Dict, List, Any
from threading import Thread

from py_alaska import task, rmi_signal
from py_alaska.qt import ui_thread

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QSplitter, QFrame
)
from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtGui import QColor, QFont


@task(name="PerformanceGui")
class PerformanceGui(QWidget):
    """Performance Test GUI Widget"""

    # Qt Signals for thread-safe UI updates
    update_progress = QtSignal(int, int)  # current, total
    update_log = QtSignal(str)
    update_result = QtSignal(str, dict)  # test_name, metrics
    test_completed = QtSignal(str)  # test_name

    # Success criteria
    SIGNAL_TARGET_MS = 0.5
    IPC_TARGET_MS = 3.0
    TARGET_TPS = 300
    TARGET_FAILURE_RATE = 0.1

    def __init__(self):
        super().__init__()
        self.iterations = 100
        self.warmup_count = 10

        # RMI clients (injected)
        self.p1 = None
        self.t1 = None

        # Test state
        self._running = False
        self._signal_responses: Dict[str, Dict] = {}
        self._pending_signal_count = 0

        # Results storage
        self.signal_results: Dict[str, List[float]] = {}
        self.ipc_results: Dict[str, List[Dict]] = {}

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Title
        title = QLabel("Signal / RMI Performance Test")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Criteria display
        criteria_group = QGroupBox("Success Criteria")
        criteria_layout = QHBoxLayout(criteria_group)
        criteria_layout.addWidget(QLabel(f"Signal: < {self.SIGNAL_TARGET_MS}ms"))
        criteria_layout.addWidget(QLabel(f"IPC: < {self.IPC_TARGET_MS}ms"))
        criteria_layout.addWidget(QLabel(f"TPS: > {self.TARGET_TPS}"))
        criteria_layout.addWidget(QLabel(f"Fail Rate: < {self.TARGET_FAILURE_RATE}%"))
        layout.addWidget(criteria_group)

        # Test buttons
        btn_group = QGroupBox("Test Controls")
        btn_layout = QHBoxLayout(btn_group)

        self.btn_signal = QPushButton("1. Signal Test")
        self.btn_signal.clicked.connect(lambda: self._start_test("signal"))
        btn_layout.addWidget(self.btn_signal)

        self.btn_process = QPushButton("2. Process IPC")
        self.btn_process.clicked.connect(lambda: self._start_test("process"))
        btn_layout.addWidget(self.btn_process)

        self.btn_thread = QPushButton("3. Thread IPC")
        self.btn_thread.clicked.connect(lambda: self._start_test("thread"))
        btn_layout.addWidget(self.btn_thread)

        self.btn_all = QPushButton("Run All Tests")
        self.btn_all.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_all.clicked.connect(lambda: self._start_test("all"))
        btn_layout.addWidget(self.btn_all)

        layout.addWidget(btn_group)

        # Progress bar
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        layout.addWidget(progress_group)

        # Splitter for results and log
        splitter = QSplitter(Qt.Vertical)

        # Results table
        result_frame = QFrame()
        result_layout = QVBoxLayout(result_frame)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_label = QLabel("Results")
        result_label.setFont(QFont("Arial", 12, QFont.Bold))
        result_layout.addWidget(result_label)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels([
            "Test", "Avg(ms)", "Min(ms)", "Max(ms)", "P95(ms)", "P99(ms)", "TPS", "Status"
        ])
        self.result_table.horizontalHeader().setStretchLastSection(True)
        result_layout.addWidget(self.result_table)
        splitter.addWidget(result_frame)

        # Log area
        log_frame = QFrame()
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_label = QLabel("Log")
        log_label.setFont(QFont("Arial", 12, QFont.Bold))
        log_layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_frame)

        layout.addWidget(splitter)

    def _connect_signals(self):
        """Connect Qt signals to slots"""
        self.update_progress.connect(self._on_progress)
        self.update_log.connect(self._on_log)
        self.update_result.connect(self._on_result)
        self.test_completed.connect(self._on_test_completed)

    def _on_progress(self, current: int, total: int):
        """Update progress bar"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Progress: {current}/{total}")

    def _on_log(self, message: str):
        """Append log message"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{timestamp}] {message}")

    def _on_result(self, test_name: str, metrics: dict):
        """Update result table"""
        row = self.result_table.rowCount()
        self.result_table.insertRow(row)

        avg = metrics.get("avg_ms", 0)
        target = self.SIGNAL_TARGET_MS if "signal" in test_name.lower() else self.IPC_TARGET_MS
        passed = avg < target

        items = [
            test_name,
            f"{metrics.get('avg_ms', 0):.4f}",
            f"{metrics.get('min_ms', 0):.4f}",
            f"{metrics.get('max_ms', 0):.4f}",
            f"{metrics.get('p95_ms', 0):.4f}",
            f"{metrics.get('p99_ms', 0):.4f}",
            f"{metrics.get('tps', 0):.0f}",
            "PASS" if passed else "FAIL"
        ]

        for col, text in enumerate(items):
            item = QTableWidgetItem(str(text))
            item.setTextAlignment(Qt.AlignCenter)
            if col == 7:  # Status column
                if passed:
                    item.setBackground(QColor(76, 175, 80))  # Green
                    item.setForeground(QColor(255, 255, 255))
                else:
                    item.setBackground(QColor(244, 67, 54))  # Red
                    item.setForeground(QColor(255, 255, 255))
            self.result_table.setItem(row, col, item)

        self.result_table.resizeColumnsToContents()

    def _on_test_completed(self, test_name: str):
        """Handle test completion"""
        self._set_buttons_enabled(True)
        self.progress_label.setText(f"{test_name} completed")

    def _set_buttons_enabled(self, enabled: bool):
        """Enable/disable test buttons"""
        self.btn_signal.setEnabled(enabled)
        self.btn_process.setEnabled(enabled)
        self.btn_thread.setEnabled(enabled)
        self.btn_all.setEnabled(enabled)

    def _start_test(self, test_type: str):
        """Start test in background thread"""
        if self._running:
            return

        self._running = True
        self._set_buttons_enabled(False)

        thread = Thread(target=self._run_test, args=(test_type,), daemon=True)
        thread.start()

    def _run_test(self, test_type: str):
        """Run test (background thread)"""
        try:
            if test_type == "signal":
                self._run_signal_test()
            elif test_type == "process":
                self._run_process_ipc_test()
            elif test_type == "thread":
                self._run_thread_ipc_test()
            elif test_type == "all":
                self._run_signal_test()
                self._run_process_ipc_test()
                self._run_thread_ipc_test()
                self._export_results()
        finally:
            self._running = False
            self.test_completed.emit(test_type)

    def _run_signal_test(self):
        """Signal Broadcast Test"""
        self.update_log.emit("=== Signal Broadcast Test ===")
        self.signal_results = {"p1": [], "p2": [], "p3": [], "t1": [], "t2": [], "t3": []}

        # Warmup
        self.update_log.emit(f"Warmup ({self.warmup_count} iterations)...")
        for _ in range(self.warmup_count):
            self._signal_responses.clear()
            self._pending_signal_count = 6
            self.signal.wakeup.emit({"send_time": time.perf_counter()})
            time.sleep(0.01)

        # Actual test
        self.update_log.emit(f"Running ({self.iterations} iterations)...")
        for i in range(self.iterations):
            self._signal_responses.clear()
            self._pending_signal_count = 6
            send_time = time.perf_counter()
            self.signal.wakeup.emit({"send_time": send_time})

            # Wait for responses
            timeout = time.perf_counter() + 0.1
            while self._pending_signal_count > 0 and time.perf_counter() < timeout:
                time.sleep(0.0001)

            # Collect results
            for task_name, data in self._signal_responses.items():
                short_name = task_name.lower()
                if short_name in self.signal_results:
                    self.signal_results[short_name].append(data["elapsed_ms"])

            self.update_progress.emit(i + 1, self.iterations)

        # Report results
        all_times = []
        for task_name, times in self.signal_results.items():
            if times:
                all_times.extend(times)
                metrics = self._calc_metrics(times)
                self.update_result.emit(f"Signal/{task_name}", metrics)

        if all_times:
            avg_all = statistics.mean(all_times)
            self.update_log.emit(f"Signal Avg: {avg_all:.4f}ms ({'PASS' if avg_all < self.SIGNAL_TARGET_MS else 'FAIL'})")

    def _run_process_ipc_test(self):
        """Process IPC Chain Test"""
        self.update_log.emit("=== Process IPC Test (P1→P2→P3→GUI) ===")
        self.ipc_results["process"] = []

        if not self.p1:
            self.update_log.emit("[SKIP] P1 client not available")
            return

        # Warmup
        self.update_log.emit(f"Warmup ({self.warmup_count} iterations)...")
        for _ in range(self.warmup_count):
            try:
                self.p1.chain_call({"path": ["gui"], "timestamps": [time.perf_counter()]})
            except Exception as e:
                self.update_log.emit(f"Warmup error: {e}")

        # Actual test
        self.update_log.emit(f"Running ({self.iterations} iterations)...")
        for i in range(self.iterations):
            start = time.perf_counter()
            try:
                result = self.p1.chain_call({"path": ["gui"], "timestamps": [start]})
                end = time.perf_counter()
                self.ipc_results["process"].append({"total_ms": (end - start) * 1000})
            except Exception as e:
                self.ipc_results["process"].append({"error": str(e)})

            self.update_progress.emit(i + 1, self.iterations)

        # Report
        self._report_ipc_results("process")

    def _run_thread_ipc_test(self):
        """Thread IPC Chain Test"""
        self.update_log.emit("=== Thread IPC Test (T1→T2→T3→GUI) ===")
        self.ipc_results["thread"] = []

        if not self.t1:
            self.update_log.emit("[SKIP] T1 client not available")
            return

        # Warmup
        self.update_log.emit(f"Warmup ({self.warmup_count} iterations)...")
        for _ in range(self.warmup_count):
            try:
                self.t1.chain_call({"path": ["gui"], "timestamps": [time.perf_counter()]})
            except Exception as e:
                self.update_log.emit(f"Warmup error: {e}")

        # Actual test
        self.update_log.emit(f"Running ({self.iterations} iterations)...")
        for i in range(self.iterations):
            start = time.perf_counter()
            try:
                result = self.t1.chain_call({"path": ["gui"], "timestamps": [start]})
                end = time.perf_counter()
                self.ipc_results["thread"].append({"total_ms": (end - start) * 1000})
            except Exception as e:
                self.ipc_results["thread"].append({"error": str(e)})

            self.update_progress.emit(i + 1, self.iterations)

        # Report
        self._report_ipc_results("thread")

    def _report_ipc_results(self, test_type: str):
        """Report IPC test results"""
        results = self.ipc_results.get(test_type, [])
        times = [r["total_ms"] for r in results if "total_ms" in r]
        errors = [r for r in results if "error" in r]

        if not times:
            self.update_log.emit(f"{test_type} IPC: No successful results")
            return

        metrics = self._calc_metrics(times)
        metrics["error_count"] = len(errors)
        metrics["success_rate"] = (len(times) / len(results)) * 100

        self.update_result.emit(f"IPC/{test_type}", metrics)

        avg = metrics["avg_ms"]
        tps = metrics["tps"]
        self.update_log.emit(
            f"{test_type} IPC Avg: {avg:.4f}ms, TPS: {tps:.0f} "
            f"({'PASS' if avg < self.IPC_TARGET_MS else 'FAIL'})"
        )

    def _calc_metrics(self, times: List[float]) -> dict:
        """Calculate statistics from time list"""
        if not times:
            return {}

        sorted_times = sorted(times)
        n = len(sorted_times)

        return {
            "avg_ms": statistics.mean(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "std_ms": statistics.stdev(times) if n > 1 else 0,
            "p50_ms": statistics.median(times),
            "p95_ms": sorted_times[int(n * 0.95)] if n > 0 else 0,
            "p99_ms": sorted_times[int(n * 0.99)] if n > 0 else 0,
            "tps": 1000 / statistics.mean(times) if statistics.mean(times) > 0 else 0,
            "count": n
        }

    @rmi_signal("awake")
    def on_awake(self, signal):
        """Receive signal response"""
        data = signal.data
        task_name = data.get("task", "unknown")
        self._signal_responses[task_name] = data
        self._pending_signal_count -= 1

    def on_chain_result(self, data: dict) -> dict:
        """Receive IPC chain result"""
        data["path"].append("gui")
        data["timestamps"].append(time.perf_counter())
        return data

    def _export_results(self):
        """Export results to JSON"""
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = results_dir / f"performance_{timestamp}.json"

        export_data = {
            "timestamp": datetime.now().isoformat(),
            "iterations": self.iterations,
            "signal_results": {k: self._calc_metrics(v) for k, v in self.signal_results.items() if v},
            "ipc_results": {}
        }

        for test_type, results in self.ipc_results.items():
            times = [r["total_ms"] for r in results if "total_ms" in r]
            if times:
                export_data["ipc_results"][test_type] = self._calc_metrics(times)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

        self.update_log.emit(f"Results exported: {filepath}")

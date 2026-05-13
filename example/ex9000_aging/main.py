#!/usr/bin/env python3
"""
ALASKA v2.7 - SmInfra Aging Test (ex9000)
All sm_infra components continuous test with PySide6 real-time graphs.

Components (3x3 grid):
  SmRingBuffer | SmBlock          | SmValue
  SmQueue      | SmKernelEvent    | SmLockFreeEvent
  SmMutex      | SmSignalRegistry | SmSignalStats

Run:  python main.py
Stop: close the window or Ctrl+C in terminal
"""

import os
import sys
import time
import threading
import multiprocessing as mp
import statistics
from collections import deque

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.normpath(os.path.join(_HERE, "..", "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from py_alaska.sm_infra._base          import cleanup_existing_shm
from py_alaska.sm_infra.sm_ring_buffer import SmRingBuffer
from py_alaska.sm_infra.sm_block       import SmBlock
from py_alaska.sm_infra.sm_value       import SmValue
from py_alaska.sm_infra.sm_queue       import SmQueue
from py_alaska.sm_infra.sm_sync        import SmKernelEvent, SmLockFreeEvent, SmMutex
from py_alaska.sm_infra.sm_signal      import SmSignalRegistry, SmSignalStats

import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
MAX_PTS   = 300         # history length: 60 s x 5 Hz
SAMPLE_HZ = 5
UPDATE_MS  = 200        # UI refresh interval
PAYLOAD    = b"aging_test_payload_64bytes_" + b"x" * 36
IMG_SHAPE  = (8, 8, 3)
_PID       = os.getpid()

_NM = {k: f"age9_{k}_{_PID}" for k in
       ["rb", "block", "val", "queue", "lfev", "sigreg", "sigstat"]}

_stop = threading.Event()

# ── Colors (hex) ──────────────────────────────────────────────────────────────
_COLORS = [
    "#4FC3F7",   # SmRingBuffer
    "#81C784",   # SmBlock
    "#FFB74D",   # SmValue
    "#F06292",   # SmQueue
    "#CE93D8",   # SmKernelEvent
    "#80DEEA",   # SmLockFreeEvent
    "#FFCC02",   # SmMutex
    "#A5D6A7",   # SmSignalRegistry
    "#EF9A9A",   # SmSignalStats
]


# ── CompMetrics ───────────────────────────────────────────────────────────────
class CompMetrics:
    """Thread-safe per-component metrics collector."""

    def __init__(self, name: str):
        self.name       = name
        self._lock      = threading.Lock()
        self._lats: list = []
        self._errs: int  = 0
        self.lat_hist   = deque(maxlen=MAX_PTS)
        self.tps_hist   = deque(maxlen=MAX_PTS)
        self._ts        = time.monotonic()
        self.cur_lat    = 0.0
        self.cur_tps    = 0.0
        self.total_ops  = 0
        self.total_errs = 0

    def record(self, lat_us: float):
        with self._lock:
            self._lats.append(lat_us)

    def error(self):
        with self._lock:
            self._errs += 1

    def sample(self):
        now = time.monotonic()
        with self._lock:
            lats = self._lats[:]
            errs = self._errs
            self._lats.clear()
            self._errs = 0
        dt = max(now - self._ts, 1e-6)
        self._ts = now

        avg = statistics.mean(lats) if lats else self.cur_lat
        tps = len(lats) / dt

        self.lat_hist.append(avg)
        self.tps_hist.append(tps)
        self.cur_lat    = avg
        self.cur_tps    = tps
        self.total_ops  += len(lats)
        self.total_errs += errs


# ── Workers ───────────────────────────────────────────────────────────────────
def _w_ring_buffer(m: CompMetrics, stop: threading.Event):
    nm = _NM["rb"]
    cleanup_existing_shm(nm)
    rb = SmRingBuffer(nm, size=4096, create=True)
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            ok = rb.write(PAYLOAD)
            if ok:
                data = rb.read()
                m.record((time.perf_counter() - t0) * 1e6)
                if data is None:
                    m.error()
            else:
                m.error()
    except Exception:
        m.error()
    finally:
        rb.close()


def _w_block(m: CompMetrics, stop: threading.Event):
    nm  = _NM["block"]
    cleanup_existing_shm(nm)
    lk  = threading.Lock()
    img = np.zeros(IMG_SHAPE, dtype=np.uint8)
    blk = SmBlock(nm, IMG_SHAPE, maxsize=4, create=True, lock=lk)
    try:
        while not stop.is_set():
            t0  = time.perf_counter()
            idx = blk.malloc2(img)
            if idx >= 0:
                blk.mfree(idx)
                m.record((time.perf_counter() - t0) * 1e6)
            else:
                m.error()
                time.sleep(0.001)
    except Exception:
        m.error()
    finally:
        blk.close()


def _w_value(m: CompMetrics, stop: threading.Event):
    nm  = _NM["val"]
    cleanup_existing_shm(nm)
    val = SmValue(nm, "i", create=True)
    cnt = 0
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            val.set(cnt)
            _ = val.get()
            m.record((time.perf_counter() - t0) * 1e6)
            cnt += 1
    except Exception:
        m.error()
    finally:
        val.close()


def _w_queue(m: CompMetrics, stop: threading.Event):
    nm  = _NM["queue"]
    sem = mp.Semaphore(0)
    cleanup_existing_shm(nm)
    q = SmQueue(nm, size=65536, create=True, lock=None, sem=sem, spin=64)
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            q.put_nowait(42)
            q.get_nowait()
            m.record((time.perf_counter() - t0) * 1e6)
    except Exception:
        m.error()
    finally:
        q.close()


def _w_kernel_event(m: CompMetrics, stop: threading.Event):
    nm  = f"age9_kev_{_PID}"
    kev = SmKernelEvent(nm, create=True, initial=False, manual_reset=False)
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            kev.set()
            kev.wait(timeout=0.5)
            m.record((time.perf_counter() - t0) * 1e6)
    except Exception:
        m.error()
    finally:
        kev.close()


def _w_lockfree_event(m: CompMetrics, stop: threading.Event):
    nm = _NM["lfev"]
    cleanup_existing_shm(nm + "_evt")
    lfev = SmLockFreeEvent(nm, create=True, initial=False)
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            lfev.set()
            lfev.wait_drain(timeout=0.1, spin=1000)
            m.record((time.perf_counter() - t0) * 1e6)
    except Exception:
        m.error()
    finally:
        lfev.close()


def _w_mutex(m: CompMetrics, stop: threading.Event):
    nm  = f"age9_mtx_{_PID}"
    mtx = SmMutex(nm, create=True)
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            mtx.acquire(timeout_ms=1000)
            mtx.release()
            m.record((time.perf_counter() - t0) * 1e6)
    except Exception:
        m.error()
    finally:
        mtx.close()


def _w_sig_registry(m: CompMetrics, stop: threading.Event):
    nm  = _NM["sigreg"]
    cleanup_existing_shm(nm)
    lk  = threading.Lock()
    reg = SmSignalRegistry(nm, create=True, lock=lk)
    try:
        reg.register_task("aging_task")
        reg.subscribe("aging.test.signal", "aging_task")
    except Exception:
        pass
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            reg.get_subscribers("aging.test.signal")
            m.record((time.perf_counter() - t0) * 1e6)
    except Exception:
        m.error()
    finally:
        reg.close()


def _w_sig_stats(m: CompMetrics, stop: threading.Event):
    nm  = _NM["sigstat"]
    cleanup_existing_shm(nm)
    lk  = threading.Lock()
    sts = SmSignalStats(nm, max_slots=64, create=True, lock=lk)
    try:
        while not stop.is_set():
            t0 = time.perf_counter()
            sts.record("aging.signal", transit_ms=0.05, proc_ms=0.01, qlen=0)
            m.record((time.perf_counter() - t0) * 1e6)
    except Exception:
        m.error()
    finally:
        sts.close()


_COMPONENTS = [
    ("SmRingBuffer",     _w_ring_buffer),
    ("SmBlock",          _w_block),
    ("SmValue",          _w_value),
    ("SmQueue",          _w_queue),
    ("SmKernelEvent",    _w_kernel_event),
    ("SmLockFreeEvent",  _w_lockfree_event),
    ("SmMutex",          _w_mutex),
    ("SmSignalRegistry", _w_sig_registry),
    ("SmSignalStats",    _w_sig_stats),
]


# ── Sampler thread ────────────────────────────────────────────────────────────
def _sampler(metrics: list, stop: threading.Event):
    interval = 1.0 / SAMPLE_HZ
    while not stop.is_set():
        time.sleep(interval)
        for m in metrics:
            m.sample()


# ── PySide6 UI ────────────────────────────────────────────────────────────────
def _run_gui(metrics: list):
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget,
        QGridLayout, QVBoxLayout,
        QLabel, QFrame, QSizePolicy,
    )
    from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
    from PySide6.QtCore   import Qt, QTimer, QPointF, QMargins, QRect
    from PySide6.QtGui    import QColor, QPainter, QFont, QPen, QPalette

    BG     = "#0D0D1A"
    PANEL  = "#141428"
    FG     = "#C8C8E8"
    BORDER = "#2A2A4A"
    GRID   = "#222240"
    DIM    = "#666688"

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,        QColor(BG))
    pal.setColor(QPalette.ColorRole.WindowText,    QColor(FG))
    pal.setColor(QPalette.ColorRole.Base,          QColor(PANEL))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1A1A30"))
    pal.setColor(QPalette.ColorRole.Button,        QColor("#1E1E36"))
    pal.setColor(QPalette.ColorRole.ButtonText,    QColor(FG))
    pal.setColor(QPalette.ColorRole.Highlight,     QColor("#3A3A6A"))
    app.setPalette(pal)

    # ── Main window ───────────────────────────────────────────────────────────
    win = QMainWindow()
    win.setWindowTitle("ALASKA v2.7  SmInfra Aging Test")
    win.resize(1400, 860)

    central = QWidget()
    central.setStyleSheet(f"background:{BG};")
    win.setCentralWidget(central)

    root = QVBoxLayout(central)
    root.setContentsMargins(8, 6, 8, 6)
    root.setSpacing(6)

    title_lbl = QLabel("ALASKA v2.7  |  SmInfra Aging Test")
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_lbl.setStyleSheet(
        f"color:#8888CC; font-size:15px; font-weight:bold;"
        f" padding:4px; background:{BG};"
    )
    root.addWidget(title_lbl)

    # ── 3x3 latency charts ────────────────────────────────────────────────────
    grid = QGridLayout()
    grid.setSpacing(6)
    root.addLayout(grid, stretch=5)

    series_list  = []
    y_axes       = []
    title_labels = []

    for i, (m, col_hex) in enumerate(zip(metrics, _COLORS)):
        r, c = divmod(i, 3)

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{PANEL}; border:1px solid {BORDER};"
            f" border-radius:6px; }}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(6, 4, 6, 4)
        fl.setSpacing(2)

        info = QLabel(m.name)
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(
            f"color:{col_hex}; font-size:11px; font-weight:bold;"
            f" background:transparent; border:none;"
        )
        fl.addWidget(info)
        title_labels.append(info)

        series = QLineSeries()
        pen = QPen(QColor(col_hex))
        pen.setWidthF(1.5)
        series.setPen(pen)

        chart = QChart()
        chart.addSeries(series)
        chart.setBackgroundBrush(QColor(PANEL))
        chart.setPlotAreaBackgroundBrush(QColor(BG))
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setVisible(False)
        chart.setMargins(QMargins(2, 2, 2, 2))

        ax_x = QValueAxis()
        ax_x.setRange(0, MAX_PTS)
        ax_x.setLabelFormat("%d")
        ax_x.setLabelsColor(QColor(DIM))
        ax_x.setGridLineColor(QColor(GRID))
        ax_x.setLabelsFont(QFont("", 7))
        ax_x.setTickCount(5)

        ax_y = QValueAxis()
        ax_y.setRange(0, 10)
        ax_y.setLabelFormat("%.1f")
        ax_y.setLabelsColor(QColor(DIM))
        ax_y.setGridLineColor(QColor(GRID))
        ax_y.setLabelsFont(QFont("", 7))
        ax_y.setTitleText("us")
        ax_y.setTitleFont(QFont("", 7))
        ax_y.setTitleBrush(QColor(DIM))
        ax_y.setTickCount(4)

        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(ax_x)
        series.attachAxis(ax_y)

        view = QChartView(chart)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setStyleSheet("border:none; background:transparent;")
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        fl.addWidget(view, stretch=1)
        grid.addWidget(frame, r, c)
        series_list.append(series)
        y_axes.append(ax_y)

    # ── Bottom: custom QPainter TPS bar widget ────────────────────────────────
    cat_names = [
        m.name.replace("Sm", "").replace("Signal", "Sig").replace("Kernel", "Kern")
        for m in metrics
    ]

    class TpsWidget(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._vals = [0.0] * len(metrics)
            self._peak = 1.0
            self.setMinimumHeight(90)

        def set_values(self, vals: list):
            self._vals = vals
            self._peak = max(vals) if any(v > 0 for v in vals) else 1.0
            self.update()

        def paintEvent(self, _):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            W, H = self.width(), self.height()
            ML, MR, MT, MB = 8, 8, 6, 28  # margins: left right top bottom
            pw = W - ML - MR
            ph = H - MT - MB
            n  = len(self._vals)
            bw = pw / n
            gap = max(bw * 0.18, 3)

            p.fillRect(0, 0, W, H, QColor(BG))

            font_sm = QFont("", 7)
            font_val = QFont("", 7)
            font_val.setBold(True)
            p.setFont(font_sm)

            for i, (v, col_hex, lbl) in enumerate(
                zip(self._vals, _COLORS, cat_names)
            ):
                frac   = v / self._peak if self._peak > 0 else 0.0
                bar_h  = max(int(ph * frac), 1 if v > 0 else 0)
                x      = int(ML + i * bw + gap / 2)
                bwidth = max(int(bw - gap), 4)
                y      = MT + ph - bar_h

                col = QColor(col_hex)
                p.fillRect(x, y, bwidth, bar_h, col)

                # Label below bar
                p.setPen(QColor(FG))
                p.setFont(font_sm)
                p.drawText(
                    QRect(x, MT + ph + 2, bwidth, MB - 2),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    lbl,
                )

                # TPS value above bar
                if v > 0:
                    val_str = f"{v:,.0f}"
                    p.setFont(font_val)
                    col.setAlpha(220)
                    p.setPen(col)
                    p.drawText(
                        QRect(x, max(y - 18, MT), bwidth, 18),
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                        val_str,
                    )
            p.end()

    bottom_frame = QFrame()
    bottom_frame.setStyleSheet(
        f"QFrame {{ background:{PANEL}; border:1px solid {BORDER};"
        f" border-radius:6px; }}"
    )
    bl = QVBoxLayout(bottom_frame)
    bl.setContentsMargins(6, 4, 6, 4)
    bl.setSpacing(2)

    tps_header = QLabel("ops / sec  per Component")
    tps_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tps_header.setStyleSheet(
        f"color:{FG}; font-size:10px; font-weight:bold;"
        f" background:transparent; border:none;"
    )
    bl.addWidget(tps_header)

    tps_widget = TpsWidget()
    tps_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    bl.addWidget(tps_widget, stretch=1)
    root.addWidget(bottom_frame, stretch=2)

    # Status bar
    win.statusBar().setStyleSheet(f"color:#8888CC; background:{BG};")
    win.statusBar().showMessage(f"PID={_PID}  |  Running...")

    # ── Update timer ──────────────────────────────────────────────────────────
    _t_start = time.monotonic()

    def _update():
        for m, series, ax_y, lbl in zip(metrics, series_list, y_axes, title_labels):
            data = list(m.lat_hist)
            if not data:
                continue
            series.replace([QPointF(float(x), v) for x, v in enumerate(data)])
            ymax = max(data) * 1.3 if max(data) > 0 else 10.0
            ax_y.setRange(0, ymax)
            err_tag = f"  ERR={m.total_errs}" if m.total_errs else ""
            lbl.setText(
                f"{m.name}    {m.cur_lat:.1f} us    {m.cur_tps:,.0f} ops/s{err_tag}"
            )

        tps_widget.set_values([m.cur_tps for m in metrics])

        elapsed = time.monotonic() - _t_start
        h  = int(elapsed) // 3600
        m_ = (int(elapsed) % 3600) // 60
        s  = int(elapsed) % 60
        ts = f"{h:02d}:{m_:02d}:{s:02d}" if h else f"{m_:02d}:{s:02d}"
        total  = sum(m.total_ops   for m in metrics)
        errs   = sum(m.total_errs  for m in metrics)
        win.setWindowTitle(f"ALASKA v2.7  SmInfra Aging Test  |  {ts}")
        win.statusBar().showMessage(
            f"PID={_PID}  |  Elapsed: {ts}  |"
            f"  Total ops: {total:,}  |  Errors: {errs}"
        )

    timer = QTimer()
    timer.timeout.connect(_update)
    timer.start(UPDATE_MS)

    win.show()
    result = app.exec()
    _stop.set()
    return result


# ── Console fallback ──────────────────────────────────────────────────────────
def _run_console(metrics: list, stop: threading.Event):
    sep = "-" * 62
    hdr = f"  {'Component':<20} {'Lat(us)':>9} {'TPS':>10} {'TotalOps':>12} {'Errs':>6}"
    try:
        while not stop.is_set():
            time.sleep(2.0)
            print(sep)
            print(hdr)
            print(sep)
            for m in metrics:
                status = "OK" if m.total_errs == 0 else f"ERR={m.total_errs}"
                print(f"  {m.name:<20} {m.cur_lat:>9.2f} {m.cur_tps:>10,.0f} "
                      f"{m.total_ops:>12,} {status:>6}")
    except KeyboardInterrupt:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 62)
    print("  ALASKA v2.7 - SmInfra Aging Test")
    print(f"  PID={_PID}   Components={len(_COMPONENTS)}")
    print("=" * 62)

    metrics = [CompMetrics(name) for name, _ in _COMPONENTS]

    workers = []
    for (_, fn), m in zip(_COMPONENTS, metrics):
        t = threading.Thread(target=fn, args=(m, _stop), daemon=True, name=m.name)
        t.start()
        workers.append(t)

    smp = threading.Thread(
        target=_sampler, args=(metrics, _stop), daemon=True, name="sampler"
    )
    smp.start()

    time.sleep(0.3)

    try:
        _run_gui(metrics)
    except ImportError:
        print("[!] PySide6 not found -- console mode")
        _run_console(metrics, _stop)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping ...")
        _stop.set()
        for t in workers:
            t.join(timeout=2.0)
        smp.join(timeout=2.0)

    # Final summary
    print()
    print("=" * 62)
    print(f"  {'Component':<20} {'Lat(us)':>9} {'TPS':>10} {'TotalOps':>12} {'Errs':>6}")
    print("  " + "-" * 60)
    for m in metrics:
        status = "OK" if m.total_errs == 0 else f"ERR={m.total_errs}"
        print(f"  {m.name:<20} {m.cur_lat:>9.2f} {m.cur_tps:>10,.0f} "
              f"{m.total_ops:>12,} {status:>6}")
    print("=" * 62)


if __name__ == "__main__":
    main()

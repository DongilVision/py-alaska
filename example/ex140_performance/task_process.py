# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Process Tasks for IPC / Signal Performance Test (P1~P4)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import time
from py_alaska import task

_BATCH = 500          # signal emit batch size (signal queue ~64KB)
_CHUNK = 500          # result chunk size (RMI response ~64KB)
_BATCH_TIMEOUT = 30   # seconds to wait per batch


@task(name="Process1", mode="process", restart=True)
class Process1:
    """Process 1 — IPC / Signal entry point"""
    def __init__(self):
        self.next_task = None  # client:p2

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    # ── IPC Tests ──────────────────────────────────────────────

    def ipc_call(self, send_time: float) -> dict:
        """Test 1: P1 → P2 direct IPC"""
        return self.next_task.ipc_receive(send_time)

    def hop_call(self, send_time: float) -> dict:
        """Test 2: P1 → P2 → P3 → P4 (3-hop IPC)"""
        return self.next_task.hop_forward(send_time)

    # ── Signal Tests (flow-controlled batch) ──────────────────

    def sig_emit(self, iterations: int, contention: bool = False) -> int:
        """Test 3: Emit P1→P2 signals, return received count"""
        # Warmup
        for _ in range(10):
            self.signal.sig_ping.emit({"t": time.perf_counter()})
        time.sleep(0.1)
        self.next_task.clear_sig_results()
        time.sleep(0.01)

        if contention:
            # Contention mode: emit all without flow control
            for _ in range(iterations):
                self.signal.sig_ping.emit({"t": time.perf_counter()})
                time.sleep(0.00001)
        else:
            # Flow-controlled: emit in batches, wait for receiver
            sent = 0
            while sent < iterations:
                batch_end = min(sent + _BATCH, iterations)
                for _ in range(batch_end - sent):
                    self.signal.sig_ping.emit({"t": time.perf_counter()})
                    time.sleep(0.00001)
                sent = batch_end

                deadline = time.perf_counter() + _BATCH_TIMEOUT
                while time.perf_counter() < deadline:
                    if self.next_task.get_sig_count() >= sent:
                        break
                    time.sleep(0.01)

        # Wait for delivery
        deadline = time.perf_counter() + min(300, max(10, iterations * 0.001))
        while time.perf_counter() < deadline:
            if self.next_task.get_sig_count() >= iterations:
                break
            time.sleep(0.05)

        return self.next_task.get_sig_count()

    def get_sig_chunk(self, offset: int, count: int) -> list:
        """Proxy: collect chunk of signal results from P2"""
        return self.next_task.get_sig_results_chunk(offset, count)

    def sig_3hop_emit(self, iterations: int, contention: bool = False) -> int:
        """Test 4: Emit 3-hop signals, return received count"""
        # Warmup
        for _ in range(10):
            self.signal.sig_hop1.emit({"t": time.perf_counter()})
        time.sleep(0.2)
        self.next_task.clear_hop_chain()
        time.sleep(0.01)

        if contention:
            # Contention mode: emit all without flow control
            for _ in range(iterations):
                self.signal.sig_hop1.emit({"t": time.perf_counter()})
                time.sleep(0.00001)
        else:
            # Flow-controlled: emit in batches, wait for receiver
            sent = 0
            while sent < iterations:
                batch_end = min(sent + _BATCH, iterations)
                for _ in range(batch_end - sent):
                    self.signal.sig_hop1.emit({"t": time.perf_counter()})
                    time.sleep(0.00001)
                sent = batch_end

                deadline = time.perf_counter() + _BATCH_TIMEOUT
                while time.perf_counter() < deadline:
                    if self.next_task.get_hop_count() >= sent:
                        break
                    time.sleep(0.01)

        # Wait for delivery
        deadline = time.perf_counter() + min(300, max(10, iterations * 0.003))
        while time.perf_counter() < deadline:
            if self.next_task.get_hop_count() >= iterations:
                break
            time.sleep(0.05)

        return self.next_task.get_hop_count()

    def get_hop_chunk(self, offset: int, count: int) -> list:
        """Proxy: collect chunk of 3-hop results from P4 (via P2→P3)"""
        return self.next_task.collect_hop_chunk(offset, count)


@task(name="Process2", mode="process", restart=True,
      signal_subscribe=["sig_ping", "sig_hop1"])
class Process2:
    """Process 2"""
    def __init__(self):
        self.next_task = None  # client:p3
        self._sig_results = []

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    # ── IPC ──
    def ipc_receive(self, send_time: float) -> dict:
        recv_time = time.perf_counter()
        return {"elapsed_ms": (recv_time - send_time) * 1000}

    def hop_forward(self, send_time: float) -> dict:
        return self.next_task.hop_forward(send_time)

    def ipc_call_next(self, send_time: float) -> dict:
        """IPC to next task (P2→P3) for contention testing"""
        return self.next_task.ipc_receive(send_time)

    # ── Signal: direct test (P1→P2) ──
    def on_sig_ping(self, signal):
        recv_time = time.perf_counter()
        self._sig_results.append((recv_time - signal.data["t"]) * 1000)

    def clear_sig_results(self):
        self._sig_results.clear()

    def get_sig_count(self) -> int:
        return len(self._sig_results)

    def get_sig_results_chunk(self, offset: int, count: int) -> list:
        """Return a chunk of results (fits in 64KB RMI buffer)"""
        return self._sig_results[offset:offset + count]

    # ── Signal: 3-hop forward (P1→P2→P3) ──
    def on_sig_hop1(self, signal):
        self.signal.sig_hop2.emit(signal.data)

    def clear_hop_chain(self):
        self.next_task.clear_hop_chain()

    def get_hop_count(self) -> int:
        return self.next_task.get_hop_count()

    def collect_hop_chunk(self, offset: int, count: int) -> list:
        """Proxy chunk collection to P3→P4"""
        return self.next_task.collect_hop_chunk(offset, count)


@task(name="Process3", mode="process", restart=True,
      signal_subscribe=["sig_hop2"])
class Process3:
    """Process 3"""
    def __init__(self):
        self.next_task = None  # client:p4

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    # ── IPC ──
    def hop_forward(self, send_time: float) -> dict:
        return self.next_task.ipc_receive(send_time)

    def ipc_call_next(self, send_time: float) -> dict:
        """IPC to next task (P3→P4) for contention testing"""
        return self.next_task.ipc_receive(send_time)

    # ── Signal: 3-hop forward (P2→P3→P4) ──
    def on_sig_hop2(self, signal):
        self.signal.sig_hop3.emit(signal.data)

    def clear_hop_chain(self):
        self.next_task.clear_sig_results()

    def get_hop_count(self) -> int:
        return self.next_task.get_sig_count()

    def collect_hop_chunk(self, offset: int, count: int) -> list:
        """Proxy chunk collection to P4"""
        return self.next_task.get_sig_results_chunk(offset, count)


@task(name="Process4", mode="process", restart=True,
      signal_subscribe=["sig_hop3"])
class Process4:
    """Process 4 — 3-hop endpoint"""
    def __init__(self):
        self._sig_results = []

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    # ── IPC ──
    def ipc_receive(self, send_time: float) -> dict:
        recv_time = time.perf_counter()
        return {"elapsed_ms": (recv_time - send_time) * 1000}

    # ── Signal: 3-hop endpoint ──
    def on_sig_hop3(self, signal):
        recv_time = time.perf_counter()
        self._sig_results.append((recv_time - signal.data["t"]) * 1000)

    def clear_sig_results(self):
        self._sig_results.clear()

    def get_sig_count(self) -> int:
        return len(self._sig_results)

    def get_sig_results_chunk(self, offset: int, count: int) -> list:
        """Return a chunk of results (fits in 64KB RMI buffer)"""
        return self._sig_results[offset:offset + count]

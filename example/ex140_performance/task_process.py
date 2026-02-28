# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Process Tasks for IPC Performance Test (P1, P2, P3)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import time
from py_alaska import task, rmi_signal


@task(name="Process1", mode="process", restart=True)
class Process1:
    """Process 1 - IPC Chain Start"""
    def __init__(self):
        self.next_task = None

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    def chain_call(self, data: dict) -> dict:
        """IPC chain call: P1 → P2"""
        data["path"].append(self.task_name)
        data["timestamps"].append(time.perf_counter())
        if self.next_task:
            return self.next_task.chain_call(data)
        return data

    @rmi_signal("wakeup")
    def on_wakeup(self, signal):
        """Signal broadcast response"""
        recv_time = time.perf_counter()
        send_time = signal.data.get("send_time", 0)
        elapsed_ms = (recv_time - send_time) * 1000
        # Respond back to GUI
        self.signal.awake.emit({
            "task": self.task_name,
            "send_time": send_time,
            "recv_time": recv_time,
            "elapsed_ms": elapsed_ms
        })


@task(name="Process2", mode="process", restart=True)
class Process2:
    """Process 2 - IPC Chain Middle"""
    def __init__(self):
        self.next_task = None

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    def chain_call(self, data: dict) -> dict:
        """IPC chain call: P2 → P3"""
        data["path"].append(self.task_name)
        data["timestamps"].append(time.perf_counter())
        if self.next_task:
            return self.next_task.chain_call(data)
        return data

    @rmi_signal("wakeup")
    def on_wakeup(self, signal):
        """Signal broadcast response"""
        recv_time = time.perf_counter()
        send_time = signal.data.get("send_time", 0)
        elapsed_ms = (recv_time - send_time) * 1000
        self.signal.awake.emit({
            "task": self.task_name,
            "send_time": send_time,
            "recv_time": recv_time,
            "elapsed_ms": elapsed_ms
        })


@task(name="Process3", mode="process", restart=True)
class Process3:
    """Process 3 - IPC Chain End"""
    def __init__(self):
        self.next_task = None

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    def chain_call(self, data: dict) -> dict:
        """IPC chain call: P3 → GUI (final)"""
        data["path"].append(self.task_name)
        data["timestamps"].append(time.perf_counter())
        if self.next_task:
            return self.next_task.on_chain_result(data)
        return data

    @rmi_signal("wakeup")
    def on_wakeup(self, signal):
        """Signal broadcast response"""
        recv_time = time.perf_counter()
        send_time = signal.data.get("send_time", 0)
        elapsed_ms = (recv_time - send_time) * 1000
        self.signal.awake.emit({
            "task": self.task_name,
            "send_time": send_time,
            "recv_time": recv_time,
            "elapsed_ms": elapsed_ms
        })

# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Thread Tasks for IPC Performance Test (T1, T2, T3)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import time
from py_alaska import task


@task(name="Thread1", mode="thread", restart=True, signal_subscribe=["wakeup"])
class Thread1:
    """Thread 1 - IPC Chain Start"""
    def __init__(self):
        self.next_task = None

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    def chain_call(self, data: dict) -> dict:
        """IPC chain call: T1 → T2"""
        data["path"].append(self.task_name)
        data["timestamps"].append(time.perf_counter())
        if self.next_task:
            return self.next_task.chain_call(data)
        return data

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


@task(name="Thread2", mode="thread", restart=True, signal_subscribe=["wakeup"])
class Thread2:
    """Thread 2 - IPC Chain Middle"""
    def __init__(self):
        self.next_task = None

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    def chain_call(self, data: dict) -> dict:
        """IPC chain call: T2 → T3"""
        data["path"].append(self.task_name)
        data["timestamps"].append(time.perf_counter())
        if self.next_task:
            return self.next_task.chain_call(data)
        return data

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


@task(name="Thread3", mode="thread", restart=True, signal_subscribe=["wakeup"])
class Thread3:
    """Thread 3 - IPC Chain End"""
    def __init__(self):
        self.next_task = None

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            time.sleep(0.1)

    def chain_call(self, data: dict) -> dict:
        """IPC chain call: T3 → GUI (final)"""
        data["path"].append(self.task_name)
        data["timestamps"].append(time.perf_counter())
        if self.next_task:
            return self.next_task.on_chain_result(data)
        return data

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

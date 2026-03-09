# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""동적 Task 생성/삭제 예제 - Task 정의
=============================================
- ManagerTask : 정적 Task (항상 실행). 시스템 상태 모니터 역할.
- WorkerTask  : 동적 생성 대상 Task. RMI와 Signal을 지원한다.
"""
import time
from py_alaska import task
from py_alaska.core.task_signal_decl import TSignal, on


@task(name="ManagerTask", mode="thread", restart=False)
class ManagerTask:
    """정적 Task - 시스템 상태 모니터 역할"""
    notify = TSignal(name="notify")

    def __init__(self):
        self.runtime = None

    def ping(self) -> str:
        return "manager_pong"

    def send_notify(self, data):
        self.notify.emit(data)

    def run(self):
        while self.runtime.running:
            time.sleep(0.1)


@task(name="WorkerTask", mode="thread", restart=False)
class WorkerTask:
    """동적 생성 대상 Task"""

    def __init__(self):
        self.runtime = None
        self.signal = None
        self.counter = 0

    def ping(self) -> str:
        return f"pong from {self.runtime.name}"

    def increment(self) -> int:
        self.counter += 1
        return self.counter

    def get_counter(self) -> int:
        return self.counter

    @on(ManagerTask.notify)
    def on_notify(self, sig):
        print(f"[{self.runtime.name}] signal received: {sig.data}")

    def run(self):
        while self.runtime.running:
            time.sleep(0.05)

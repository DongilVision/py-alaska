# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Restart - 자동 복구 예제"""
import random
import time
from py_alaska import task


@task(name="UnstableTask", mode="process", restart=True)
class UnstableTask:
    """5~10초 간격으로 랜덤 예외 발생 → 자동 재시작"""

    def __init__(self):
        self.run_count = 0

    def run(self):
        self.run_count += 1
        print(f"[UnstableTask] Started (run #{self.run_count})")

        while self.running:
            # 랜덤 시점에 예외 발생
            if random.random() < 0.1:
                raise RuntimeError(f"Simulated crash at run #{self.run_count}")
            time.sleep(0.5)


@task(name="WatcherTask", mode="process")
class WatcherTask:
    """UnstableTask의 상태를 관찰"""

    def __init__(self):
        self.unstable = None  # config에서 RmiClient 주입

    def run(self):
        while self.running:
            try:
                count = self.unstable.run_count
                print(f"[Watcher] UnstableTask run_count = {count}")
            except Exception as e:
                print(f"[Watcher] UnstableTask unavailable: {e}")
            time.sleep(3.0)

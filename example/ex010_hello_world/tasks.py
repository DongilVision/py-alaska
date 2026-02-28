# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Hello World - 최소 Task 예제"""
import time
from py_alaska import task


@task(mode="process")
class HelloTask:
    """1초마다 인사하는 최소 Task"""

    def __init__(self):
        self.count = 0

    def run(self):
        while self.running:
            self.count += 1
            print(f"[HelloTask] Hello #{self.count}")
            time.sleep(1.0)

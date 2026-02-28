# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from src import task


@task(name="aaa", mode="process")
class process_job:
    def __init__(self):
        self.counter = 0
        self.runtime = None
        self.nextTask = None
        self.delay = 0.1

    def ping(self):
        return f"pong from {self.runtime.name}"

    def add(self, a, b):
        self.counter += 1
        return a + b

    def get_count(self):
        self.counter += 1
        return self.counter

    def rmi_loop(self, runtime):
        print(f"[{runtime.name}] rmi_loop started")
        while not runtime.should_stop():
            print(f"[{runtime.name}] loop #{self.nextTask.get_count():8d}, {self.delay}")
            time.sleep(self.delay)

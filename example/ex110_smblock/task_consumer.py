# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""SmBlock Consumer"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src import task
import time
import queue


@task(mode="process", restart=True)
class Consumer:
    def __init__(self):
        self.smblock = None
        self.delay = 0.001
        self.count = 0

    def get_count(self):
        return self.count

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            try:
                index = self._input_queue.get_nowait()
                self.smblock.get(index)
                self.smblock.mfree(index)
                self.count += 1
            except queue.Empty:
                pass
            time.sleep(self.delay)

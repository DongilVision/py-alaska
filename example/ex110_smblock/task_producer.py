# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""SmBlock Producer"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src import task
import numpy as np
import time


@task(mode="process", restart=True)
class Producer:
    def __init__(self):
        self.smblock = None
        self.consumer = None
        self.delay = 0.1
        self.count = 0

    def get_count(self):
        return self.count

    def run(self):
        print(f"[{self.task_name}] Started")
        while self.running:
            image = np.random.randint(0, 255, self.smblock.shape, dtype=np.uint8)
            index = self.smblock.malloc(image)
            if index >= 0:
                self.count += 1
                try:
                    self.consumer.on_input(index)
                except Exception as e:
                    self.smblock.mfree(index)
            time.sleep(self.delay)

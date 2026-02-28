# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""SumProcess - 1초마다 누적 합산 후 signal 발행"""
import random
import time
from py_alaska import task


@task(debug="rmi, signal")
class SumProcess:
    """1초 간격으로 랜덤 점수를 누적하고 score.update signal 발행"""

    def __init__(self):
        self.total = 0
        self.count = 0

    def run(self):
        while self.running:
            score = random.randint(1, 100)
            self.total += score
            self.count += 1
            self.signal.score.update.emit({
                "score": score,
                "total": self.total,
                "count": self.count,
            })
            print("sent...")
            time.sleep(0.1)

# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Debug Option - 디버그 출력 예제"""
import time
from py_alaska import task


@task(name="ProducerTask", mode="process", debug="signal")
class ProducerTask:
    """debug="signal": emit 시 시그널 이름/데이터 출력"""

    def __init__(self):
        self.count = 0

    def run(self):
        while self.running:
            self.count += 1
            self.signal.data.ready.emit({"count": self.count})
            time.sleep(1.0)


@task(name="ConsumerTask", mode="process", debug="signal,method")
class ConsumerTask:
    """debug="signal,method": 시그널 수신 + RMI 호출 모두 출력"""

    def __init__(self):
        self.producer = None  # config에서 RmiClient 주입
        self.received = 0

    def run(self):
        while self.running:
            time.sleep(3.0)
            # RMI 호출 (debug="method"로 호출 로그 출력)
            count = self.producer.count
            print(f"[Consumer] producer.count = {count}, received = {self.received}")

    def on_data_ready(self, signal):
        """자동 구독: data.ready (debug="signal"로 수신 로그 출력)"""
        self.received += 1

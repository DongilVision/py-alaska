# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Dynamic Signal - 런타임 구독/해제 예제"""
import random
import time
from py_alaska import task


@task(name="SensorTask", mode="process")
class SensorTask:
    """0.3초마다 온도/습도 시그널 발행"""

    def run(self):
        while self.running:
            self.signal.sensor.temp.emit(round(random.uniform(20, 40), 1))
            self.signal.sensor.humidity.emit(round(random.uniform(30, 80), 1))
            time.sleep(0.3)


@task(name="MonitorTask", mode="process")
class MonitorTask:
    """5초 주기로 temp 구독/해제를 토글하는 Monitor
    - humidity는 on_ 자동 구독 (항상 수신)
    - temp는 동적 on/off (5초마다 토글)
    """

    def __init__(self):
        self.subscribed = False

    def run(self):
        while self.running:
            if self.subscribed:
                self.signal.sensor.temp.off(self._on_temp)
                self.subscribed = False
                print("[Monitor] temp 구독 해제")
            else:
                self.signal.sensor.temp.on(self._on_temp)
                self.subscribed = True
                print("[Monitor] temp 구독 시작")
            time.sleep(5.0)

    def _on_temp(self, signal):
        print(f"  [Monitor] temp = {signal.data}")

    def on_sensor_humidity(self, signal):
        """자동 구독: sensor.humidity (항상 수신)"""
        print(f"  [Monitor] humidity = {signal.data}")

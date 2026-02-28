# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Signal + RMI Combo - 이벤트 수신 후 상태 조회 패턴"""
import random
import time
from py_alaska import task


@task(name="SensorTask", mode="process")
class SensorTask:
    """센서 데이터 생성, 임계값 초과 시 alert 발행"""

    def __init__(self):
        self.value = 25.0
        self.threshold = 35.0

    def run(self):
        while self.running:
            self.value = round(random.uniform(20, 45), 1)
            if self.value > self.threshold:
                self.signal.sensor.alert.emit({
                    "value": self.value,
                    "threshold": self.threshold,
                })
            time.sleep(0.5)

    def get_status(self):
        """RMI: 현재 센서 상세 상태 반환"""
        return {
            "value": self.value,
            "threshold": self.threshold,
            "is_alert": self.value > self.threshold,
        }


@task(name="DashboardTask", mode="process")
class DashboardTask:
    """Signal로 alert 수신 → RMI로 상세 상태 조회"""

    def __init__(self):
        self.sensor = None  # config에서 RmiClient 주입
        self.alert_count = 0

    def run(self):
        while self.running:
            time.sleep(0.1)

    def on_sensor_alert(self, signal):
        """자동 구독: sensor.alert"""
        self.alert_count += 1
        # Signal로 알림 수신 후, RMI로 상세 정보 조회
        detail = self.sensor.get_status()
        print(f"[Dashboard] Alert #{self.alert_count}: "
              f"value={signal.data['value']}, detail={detail}")

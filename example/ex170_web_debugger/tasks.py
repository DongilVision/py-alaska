from py_alaska import task, Signal, QoS
from py_alaska.core.task_signal_decl import TSignal, on
import time
import random

@task(mode="process")
class SensorTask:
    raw_sensor_1 = TSignal(float, name="raw.sensor.1")
    raw_sensor_5 = TSignal(float, name="raw.sensor.5")
    sensor_urgent = TSignal(str, name="sensor.urgent")

    def __init__(self, sensor_count=5):
        self.sensor_count = sensor_count

    def run(self):
        print(f"[Sensor] Publishing data with QoS profiles...")
        while self.running:
            # 1. 고우선순위 실시간 데이터 (20ms 데드라인)
            self.raw_sensor_1.emit(random.random()*100, qos=QoS.REALTIME)

            # 2. 일반 데이터 (기본 QoS)
            self.raw_sensor_5.emit(random.random()*100)

            # 3. 의도적인 데드라인 위반 시나리오 (5ms 데드라인)
            self.sensor_urgent.emit("CRITICAL_DATA", qos={"priority": 1, "deadline": 0.005})

            time.sleep(0.5)

@task(mode="process")
class AnalyticsTask:
    @on(SensorTask.raw_sensor_1)
    def on_raw_sensor_1(self, sig: Signal):
        # 실시간 데이터 처리
        pass

    @on(SensorTask.sensor_urgent)
    def on_sensor_urgent(self, sig: Signal):
        # 데드라인이 1ms이므로, 큐 대기 시간에 따라 이 로그가 안 찍힐 수 있음
        print(f"[Analytics] Received URGENT signal! (This should be rare if deadline works)")

    def run(self):
        print("[Analytics] Analyzer node active.")
        while self.running: time.sleep(1)

@task(mode="thread")
class ControllerTask:
    system_heartbeat = TSignal(float, name="system.heartbeat")

    def __init__(self, sensor_proxy=None):
        self.sensor_proxy = sensor_proxy

    def run(self):
        print("[Controller] QoS Monitoring active.")
        while self.running:
            # 4. 백그라운드 시그널 (최저 우선순위)
            self.system_heartbeat.emit(time.time(), qos=QoS.BACKGROUND)
            time.sleep(2)

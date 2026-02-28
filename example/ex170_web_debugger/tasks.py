from py_alaska import task, Signal, QoS
import time
import random

@task(mode="process")
class SensorTask:
    def __init__(self, sensor_count=5):
        self.sensor_count = sensor_count

    def run(self):
        print(f"[Sensor] Publishing data with QoS profiles...")
        while self.running:
            # 1. 고우선순위 실시간 데이터 (20ms 데드라인)
            self.signal.emit("raw.sensor.1", random.random()*100, qos=QoS.REALTIME)
            
            # 2. 일반 데이터 (기본 QoS)
            self.signal.emit("raw.sensor.5", random.random()*100)
            
            # 3. 의도적인 데드라인 위반 시나리오 (5ms 데드라인)
            # 처리가 5ms를 넘기면 수신측에서 폐기해야 함
            self.signal.emit("sensor.urgent", "CRITICAL_DATA", qos={"priority": 1, "deadline": 0.005})
            
            time.sleep(0.5)

@task(mode="process")
class AnalyticsTask:
    def on_raw_sensor_1(self, sig: Signal):
        # 실시간 데이터 처리
        pass

    def on_sensor_urgent(self, sig: Signal):
        # 데드라인이 1ms이므로, 큐 대기 시간에 따라 이 로그가 안 찍힐 수 있음
        print(f"[Analytics] Received URGENT signal! (This should be rare if deadline works)")

    def run(self):
        print("[Analytics] Analyzer node active.")
        while self.running: time.sleep(1)

@task(mode="thread")
class ControllerTask:
    def __init__(self, sensor_proxy=None):
        self.sensor_proxy = sensor_proxy

    def run(self):
        print("[Controller] QoS Monitoring active.")
        while self.running:
            # 4. 백그라운드 시그널 (최저 우선순위)
            self.signal.emit("system.heartbeat", time.time(), qos=QoS.BACKGROUND)
            time.sleep(2)

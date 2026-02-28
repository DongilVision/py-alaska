# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
ALASKA v2.0 - Qt Signal 예제
============================
main_thread=True, @rmi_signal, signal_bridge, self.signal 체인 문법 데모

주요 기능:
1. main_thread=True: 메인 스레드에서 Task 인스턴스 생성 (QObject 지원, 자동 감지)
2. @rmi_signal: RMI Signal 핸들러 데코레이터 (수동 emit)
3. signal_bridge: @task 파라미터로 RMI Signal → Qt Signal 자동 매핑
4. self.signal.xxx.emit(): 체인 문법으로 Signal 발신
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import time
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PySide6.QtCore import Signal, QObject
from src import TaskManager, gconfig, task, rmi_run, rmi_signal


# ═══════════════════════════════════════════════════════════════════════════════
#  방법 1: main_thread=True + @rmi_signal (수동 emit)
# ═══════════════════════════════════════════════════════════════════════════════

@task(name="sensor_ui", mode="thread", main_thread=True)
class SensorUI(QObject):
    """센서 UI Task - main_thread=True로 QObject 직접 사용

    main_thread=True 옵션으로 인스턴스가 메인 스레드에서 생성되어
    QObject를 상속하고 Qt Signal을 직접 emit할 수 있습니다.
    """

    # Qt Signals
    temperature_changed = Signal(float)
    humidity_changed = Signal(float)
    alert_triggered = Signal(str)

    def __init__(self):
        super().__init__()
        self.temperature = 25.0
        self.humidity = 50.0

    # @rmi_signal: RMI Signal 수신 시 Qt Signal로 변환
    @rmi_signal("sensor.temperature")
    def _on_temperature(self, signal):
        """RMI Signal 수신 → Qt Signal emit"""
        self.temperature = signal.data
        self.temperature_changed.emit(signal.data)

    @rmi_signal("sensor.humidity")
    def _on_humidity(self, signal):
        self.humidity = signal.data
        self.humidity_changed.emit(signal.data)

    @rmi_signal("sensor.alert")
    def _on_alert(self, signal):
        self.alert_triggered.emit(signal.data)

    @rmi_run
    def run(self):
        """run()은 워커 스레드에서 실행됩니다."""
        print(f"[{self.runtime.name}] SensorUI started (main_thread instance)")
        while not self.runtime.should_stop():
            time.sleep(0.1)


# ═══════════════════════════════════════════════════════════════════════════════
#  방법 2: signal_bridge 데코레이터 파라미터 (자동 매핑)
# ═══════════════════════════════════════════════════════════════════════════════

@task(name="device_ui", mode="thread", signal_bridge={
    "device.connected": "device_connected",
    "device.disconnected": "device_disconnected",
    "device.error": "device_error",
    "device.status": "status_updated",
})
class DeviceUI(QObject):
    """디바이스 UI Task - signal_bridge 파라미터로 자동 매핑

    @task의 signal_bridge 파라미터로 RMI Signal → Qt Signal을 선언적으로 매핑합니다.
    @rmi_signal 데코레이터 없이 자동으로 연결됩니다.
    (QObject 상속 시 main_thread=True 자동 설정)
    """

    # Qt Signals
    device_connected = Signal(object)  # object: 임의 데이터 타입
    device_disconnected = Signal(object)
    device_error = Signal(str)
    status_updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self.device_name = "Unknown"
        self.is_connected = False

    @rmi_run
    def run(self):
        print(f"[{self.runtime.name}] DeviceUI started (main_thread instance)")
        print(f"[{self.runtime.name}] signal_bridge: {self._rmi_signal_bridge}")
        while not self.runtime.should_stop():
            time.sleep(0.1)


# ═══════════════════════════════════════════════════════════════════════════════
#  Signal 발신 Task (process 모드)
# ═══════════════════════════════════════════════════════════════════════════════

@task(name="sensor_worker", mode="thread")
class SensorWorker:
    """센서 데이터 생성 워커 - Signal 발신"""

    def __init__(self):
        self.interval = 1.0

    @rmi_run
    def run(self):
        import random
        print(f"[{self.runtime.name}] SensorWorker started")

        count = 0
        while not self.runtime.should_stop():
            # 센서 데이터 생성
            temp = 20.0 + random.random() * 15.0  # 20~35
            humidity = 40.0 + random.random() * 30.0  # 40~70

            # RMI Signal 발신 (SensorUI가 수신) - 체인 문법 사용
            self.signal.sensor.temperature.emit(temp)
            self.signal.sensor.humidity.emit(humidity)

            # 경고 조건
            if temp > 32.0:
                self.signal.sensor.alert.emit(f"High temperature: {temp:.1f}°C")

            count += 1
            if count % 5 == 0:
                print(f"[{self.runtime.name}] Emitted {count} signals (temp={temp:.1f}, hum={humidity:.1f})")

            time.sleep(self.interval)


@task(name="device_worker", mode="thread")
class DeviceWorker:
    """디바이스 상태 생성 워커 - Signal 발신"""

    def __init__(self):
        self.interval = 2.0

    @rmi_run
    def run(self):
        import random
        print(f"[{self.runtime.name}] DeviceWorker started")

        # 디바이스 연결 시뮬레이션
        time.sleep(1.0)
        self.signal.device.connected.emit({"name": "Camera-01", "ip": "192.168.1.100"})

        count = 0
        while not self.runtime.should_stop():
            # 상태 업데이트 (signal_bridge가 자동 처리)
            status = {
                "fps": 25 + random.randint(-5, 5),
                "frames": count * 30,
                "errors": random.randint(0, 2),
            }
            self.signal.device.status.emit(status)

            # 오류 시뮬레이션
            if random.random() < 0.1:
                self.signal.device.error.emit("Frame drop detected")

            count += 1
            time.sleep(self.interval)


# ═══════════════════════════════════════════════════════════════════════════════
#  UI Window
# ═══════════════════════════════════════════════════════════════════════════════

class DemoWindow(QMainWindow):
    """데모 메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALASKA Qt Signal Demo")
        self.resize(500, 400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 센서 UI 영역
        layout.addWidget(QLabel("=== Sensor (@rmi_signal) ==="))
        self.temp_label = QLabel("Temperature: --")
        self.humidity_label = QLabel("Humidity: --")
        self.alert_label = QLabel("Alert: None")
        self.alert_label.setStyleSheet("color: red;")
        layout.addWidget(self.temp_label)
        layout.addWidget(self.humidity_label)
        layout.addWidget(self.alert_label)

        layout.addSpacing(20)

        # 디바이스 UI 영역
        layout.addWidget(QLabel("=== Device (signal_bridge) ==="))
        self.device_status_label = QLabel("Device: Disconnected")
        self.device_info_label = QLabel("Status: --")
        self.device_error_label = QLabel("Last Error: None")
        self.device_error_label.setStyleSheet("color: orange;")
        layout.addWidget(self.device_status_label)
        layout.addWidget(self.device_info_label)
        layout.addWidget(self.device_error_label)

        layout.addStretch()

    # === Sensor UI Slots ===
    def on_temperature_changed(self, value: float):
        self.temp_label.setText(f"Temperature: {value:.1f}°C")

    def on_humidity_changed(self, value: float):
        self.humidity_label.setText(f"Humidity: {value:.1f}%")

    def on_alert_triggered(self, message: str):
        self.alert_label.setText(f"Alert: {message}")

    # === Device UI Slots ===
    def on_device_connected(self, data):
        name = data.get("name", "Unknown")
        ip = data.get("ip", "")
        self.device_status_label.setText(f"Device: {name} ({ip})")
        self.device_status_label.setStyleSheet("color: green;")

    def on_device_disconnected(self, data):
        self.device_status_label.setText("Device: Disconnected")
        self.device_status_label.setStyleSheet("color: red;")

    def on_device_error(self, message: str):
        self.device_error_label.setText(f"Last Error: {message}")

    def on_status_updated(self, status: dict):
        fps = status.get("fps", 0)
        frames = status.get("frames", 0)
        errors = status.get("errors", 0)
        self.device_info_label.setText(f"Status: FPS={fps}, Frames={frames}, Errors={errors}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)

    # 윈도우 생성
    window = DemoWindow()
    window.show()

    # TaskManager 초기화
    config_path = Path(__file__).parent / "config_qt_signal.json"
    gconfig.load(config_path)
    manager = TaskManager(gconfig)

    # Task 시작 (main_thread=True Task들은 메인 스레드에서 인스턴스 생성)
    manager.start_all()

    # Qt Signal 연결 (main_thread=True이므로 get_task()로 인스턴스 접근 가능)
    sensor_ui = manager.get_task("sensor_ui")
    if sensor_ui:
        sensor_ui.temperature_changed.connect(window.on_temperature_changed)
        sensor_ui.humidity_changed.connect(window.on_humidity_changed)
        sensor_ui.alert_triggered.connect(window.on_alert_triggered)
        print("[Main] Connected SensorUI Qt Signals")

    device_ui = manager.get_task("device_ui")
    if device_ui:
        device_ui.device_connected.connect(window.on_device_connected)
        device_ui.device_disconnected.connect(window.on_device_disconnected)
        device_ui.device_error.connect(window.on_device_error)
        device_ui.status_updated.connect(window.on_status_updated)
        print("[Main] Connected DeviceUI Qt Signals")

    # 종료 처리
    app.aboutToQuit.connect(manager.stop_all)

    print("\n" + "=" * 60)
    print("  ALASKA Qt Signal Demo")
    print("  - SensorUI: @rmi_signal → Qt Signal (수동 emit)")
    print("  - DeviceUI: signal_bridge 파라미터 (자동 매핑)")
    print("  - Monitor: http://localhost:7100")
    print("=" * 60 + "\n")

    sys.exit(app.exec())


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()

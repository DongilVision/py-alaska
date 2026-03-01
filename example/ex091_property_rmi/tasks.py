# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""@property RMI 프록시 테스트 - Task 정의"""
import time
from py_alaska import task


class _DeviceBase:
    """디바이스 공통 로직 (property + method)"""

    def __init__(self):
        self._connected = False
        self._temperature = 25.0
        self._dev_mode = "idle"
        self.plain_var = 42

    def run(self):
        while self.running:
            time.sleep(0.5)

    @property
    def connected(self):
        return self._connected

    @connected.setter
    def connected(self, value):
        self._connected = bool(value)

    @property
    def temperature(self):
        return self._temperature

    @temperature.setter
    def temperature(self, value):
        self._temperature = float(value)

    @property
    def status(self):
        conn = "ON" if self._connected else "OFF"
        return f"{conn}/{self._dev_mode}/{self._temperature}C"

    def is_connected(self):
        return self._connected

    def get_temperature(self):
        return self._temperature


@task(name="DeviceProc", mode="process")
class DeviceProc(_DeviceBase):
    """Process 모드 디바이스 → RmiClient / _RmiProxy"""


@task(name="DeviceThrd", mode="thread")
class DeviceThrd(_DeviceBase):
    """Thread 모드 디바이스 → DirectClient / _DirectProxy"""

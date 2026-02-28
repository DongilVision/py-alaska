# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Signal + RMI Combo 예제
==========================
목적: Signal 이벤트 수신 후 RMI로 상세 상태 조회하는 패턴
     - SensorTask: 임계값 초과 시 signal.sensor.alert 발행
     - DashboardTask: alert 수신 → sensor.get_status() RMI 호출
실행: python main.py
"""
import sys
import multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import TaskManager, gconfig

if __name__ == "__main__":
    multiprocessing.freeze_support()
    gconfig.load(Path(__file__).parent / "config.json")

    with TaskManager(gconfig):
        input("Enter to stop...\n")

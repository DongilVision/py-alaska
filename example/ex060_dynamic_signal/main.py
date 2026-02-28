# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Dynamic Signal - 런타임 on/off 예제
========================================
목적: self.signal.xxx.on()/off() 동적 구독/해제 시연
     - humidity: on_ 자동 구독 (항상 수신)
     - temp: 5초마다 구독/해제 토글
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

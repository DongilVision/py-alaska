# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Restart - 자동 복구 예제
============================
목적: restart=True 설정 시 예외 발생 후 자동 재시작 동작 시연
     - UnstableTask: 랜덤 시점에 예외 발생 (restart=True)
     - WatcherTask: RMI로 run_count 조회하여 재시작 확인
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

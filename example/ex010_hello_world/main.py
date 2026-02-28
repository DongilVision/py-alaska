# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Hello World - ALASK 최소 예제
=================================
목적: @task + config.json + TaskManager 의 최소 구성
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

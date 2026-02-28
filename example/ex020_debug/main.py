# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Debug Option 예제
=====================
목적: @task(debug=...) 옵션별 디버그 출력 시연
     - ProducerTask: debug="signal" → emit 로그
     - ConsumerTask: debug="signal,method" → 수신 + RMI 호출 로그
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

# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""ex180 JoyStick - BT 게임패드 → CNC jog 제어 예제 (PySide6 UI)"""
import sys
import multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from py_alaska import AlaskaApp

    AlaskaApp.run(Path(__file__).parent / "config.json", main_task="ui")

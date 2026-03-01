# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""카메라 예제 (AlaskaApp + DeviceProperty)"""
import sys, multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import AlaskaApp

if __name__ == "__main__":
    multiprocessing.freeze_support()
    AlaskaApp.run(
        Path(__file__).parent / "config.json",
        main_task="viewer",
        title="Camera Viewer (DeviceProperty)"
    )

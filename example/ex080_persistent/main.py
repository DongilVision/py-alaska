# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Persistent Example - Main"""
import sys
import multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from py_alaska import AlaskaApp
    from example.ex080_persistent.viewer import MainWindow

    AlaskaApp.run(Path(__file__).parent / "config.json", MainWindow)

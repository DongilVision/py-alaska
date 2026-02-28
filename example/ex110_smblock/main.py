# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""SmBlock Producer-Consumer Example"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src import TaskManager, gconfig

if __name__ == "__main__":
    gconfig.load(Path(__file__).parent / "config.json")
    with TaskManager(gconfig):
        input("Enter to stop...\n")

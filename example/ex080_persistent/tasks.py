# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Persistent Example - Source Task"""
import time
from py_alaska import task, gconfig
from py_alaska.core.task_signal_decl import TSignal


@task(name="SourceTask", mode="process")
class SourceTask:
    """interval마다 count 증가 및 signal 발행"""

    count_sig = TSignal(int, name="count")

    def __init__(self):
        self.count = 0

    def run(self):
        while self.running:
            self.count += 1
            self.count_sig.emit(self.count)
            interval = gconfig.data_get("user_config.interval", 1.0)
            time.sleep(interval)

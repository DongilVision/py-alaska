# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Selective Signal Example - Source & Worker Tasks"""
import random
import time
from py_alaska import task
from py_alaska.core.task_signal_decl import TSignal, on


@task(name="SourceTask", mode="process", debug=True)
class SourceTask:
    """랜덤 job 타입(a,b,c,d) 생성 및 signal 발행"""

    job = TSignal(dict, name="job")

    def __init__(self):
        self.interval = 0.1
        self.job_count = 0

    def run(self):
        self.interval = 0.001
        while self.running:
            job_type = random.choice("abcd")
            self.job_count += 1
            self.job.emit({
                "id": self.job_count,
                "type": job_type
            })
            time.sleep(self.interval)


@task(name="WorkerTask", mode="process")
class WorkerTask:
    """job 시그널 처리 Worker (job_type에 따라 해당 시그널 동적 구독)"""

    result = TSignal(dict, name="result")

    def run(self):
        while self.running:
            time.sleep(0.1)

    @on("job")
    def on_job(self, signal):
        """job_type 필터링 후 처리"""
        job_type = getattr(self, 'job_type', 'a')
        if signal.data["type"] != job_type:
            return
        result = "ok" if random.random() < 0.8 else "ng"
        self.result.emit({
            "job_id": signal.data["id"],
            "job_type": job_type,
            "result": result
        })

# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Selective Signal Example - Source & Worker Tasks"""
import random
import time
from py_alaska import task


@task(name="SourceTask", mode="process", debug=True)
class SourceTask:
    """랜덤 job 타입(a,b,c,d) 생성 및 signal 발행"""

    def __init__(self):
        self.interval = 0.5
        self.job_count = 0

    def run(self):
        while self.running:
            job_type = random.choice("abcd")
            self.job_count += 1
            getattr(self.signal.job, job_type).emit({
                "id": self.job_count,
                "type": job_type
            })
            time.sleep(self.interval)


@task(name="WorkerTask", mode="process")
class WorkerTask:
    """job 시그널 처리 Worker (job_type에 따라 해당 시그널 동적 구독)"""

    def run(self):
        job_type = getattr(self, 'job_type', 'a')
        self.runtime.signal.on(f"job.{job_type}", self.on_job)
        while self.running:
            time.sleep(0.1)

    def on_job(self, signal):
        """동적 구독 핸들러: job_type에 해당하는 시그널만 수신"""
        result = "ok" if random.random() < 0.8 else "ng"
        self.signal.result.emit({
            "job_id": signal.data["id"],
            "job_type": getattr(self, 'job_type', 'a'),
            "result": result
        })

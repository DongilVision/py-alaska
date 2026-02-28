# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
RelayTask - 통합 중계 Task (공용화)
=====================================
- nextTask가 주입되면: 다음 Task로 토큰 전달 (RMI call)
- nextTask가 없으면: 최종 Task로서 signal 발신

config 예시:
  "mid1/RelayTask": {"nextTask": "client:mid2"}  # 중계 역할
  "dest/RelayTask": {}                            # 최종 Task (signal 발신)
"""

import time
from py_alaska import task


@task(name="RelayTask", mode="thread")
class RelayTask:
    """통합 Relay Task - nextTask 주입 여부로 동작 결정"""

    def __init__(self):
        self.nextTask = None  # RmiClient (config에서 주입, 없으면 최종 Task)
        self.relay_count: int = 0

    def run(self):
        role = "relay" if self.nextTask else "endpoint"
        print(f"[Relay] Started as {role}")

        while self.running:
            time.sleep(1.0)

        print(f"[Relay] Finished. Total processed: {self.relay_count}")

    def relay_token(self, token: dict) -> str:
        """토큰 처리 - nextTask 유무에 따라 중계 또는 signal 발신"""
        self.relay_count += 1

        if self.nextTask:
            # 중계: 다음 Task로 전달
            return self.nextTask.relay_token(token)
        else:
            # 최종: signal 발신
            self.signal.token.returned.emit(token)
            return "ok"

    def get_relay_count(self) -> int:
        """처리 횟수 반환"""
        return self.relay_count


@task(name="ProcessRelay", mode="process")
class ProcessRelayTask:
    """Process 모드 Relay Task - Cross-mode 테스트용"""

    def __init__(self):
        self.nextTask = None
        self.relay_count: int = 0

    def run(self):
        role = "relay" if self.nextTask else "endpoint"
        print(f"[ProcessRelay] Started as {role}")
        while self.running:
            time.sleep(1.0)
        print(f"[ProcessRelay] Finished. Total processed: {self.relay_count}")

    def relay_token(self, token: dict) -> str:
        self.relay_count += 1
        if self.nextTask:
            return self.nextTask.relay_token(token)
        else:
            self.signal.token.returned.emit(token)
            return "ok"

    def get_relay_count(self) -> int:
        return self.relay_count

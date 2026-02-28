# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
SourceTask - Token holder and round-trip measurement
=====================================================
- 초기 토큰 10개 보유
- mid Task에 RMI call로 토큰 전달 (전달 시 토큰 제거)
- dest의 signal을 받아 토큰 다시 채움
- 라운드 시간 측정 (전달 → signal 수신)

Flow:
  source --[RMI call]--> mid --[RMI call]--> dest
    ^                                          |
    |______[signal: token.returned]____________|
"""

import time
from py_alaska import task


@task(name="SourceTask", mode="thread")
class SourceTask:
    """Source Task - 토큰 순환 및 라운드 시간 측정"""

    def __init__(self):
        self.tokens: list = []
        self.initial_tokens: int = 10
        self.mid = None  # RmiClient (config에서 주입)
        self.round_count: int = 0
        self.total_rounds: int = 1000  # 총 라운드 수
        self.round_times: list = []  # 라운드 시간 기록

    def run(self):
        # 초기 토큰 생성 (id만 보관)
        self.tokens = [f"TOKEN-{i:02d}" for i in range(self.initial_tokens)]
        print(f"[Source] Initialized with {len(self.tokens)} tokens")

        # 라운드 반복
        while self.running and self.round_count < self.total_rounds:
            if not self.tokens:
                time.sleep(0.001)  # 토큰 대기 (1ms)
                continue

            # 토큰 하나 꺼내서 전달 (출발시간 포함)
            token_id = self.tokens.pop(0)
            token = {
                "id": token_id,
                "send_time": time.time()  # 출발시간 기록
            }

            try:
                # RMI call: source -> mid -> dest
                self.mid.relay_token(token)
            except Exception as e:
                self.tokens.append(token_id)  # 실패 시 복구

        # 결과 출력
        self._print_stats()

    def on_token_returned(self, signal):
        """dest에서 토큰 반환 signal 수신 (이벤트) - on_ 패턴 자동 구독"""
        token = signal.data  # {"id": "TOKEN-00", "send_time": ...}
        recv_time = time.time()

        token_id = token.get("id", "unknown")
        send_time = token.get("send_time")

        # 라운드 시간 계산
        if send_time:
            round_time = (recv_time - send_time) * 1000  # ms
            self.round_times.append(round_time)

        # 토큰 다시 채움
        self.tokens.append(token_id)
        self.round_count += 1

    def _print_stats(self):
        """라운드 시간 통계 출력"""
        if not self.round_times:
            print("[Source] No round times recorded")
            return

        avg_time = sum(self.round_times) / len(self.round_times)
        min_time = min(self.round_times)
        max_time = max(self.round_times)

        print(f"\n{'='*50}")
        print(f"[Source] Round-trip Statistics:")
        print(f"  Rounds: {len(self.round_times)}")
        print(f"  Avg: {avg_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
        print(f"{'='*50}\n")

    def get_status(self) -> dict:
        """현재 상태 반환 (RMI로 호출 가능)"""
        return {
            "tokens": len(self.tokens),
            "round_count": self.round_count,
            "total_rounds": self.total_rounds,
            "min_round_time": min(self.round_times) if self.round_times else 0,
            "avg_round_time": sum(self.round_times) / len(self.round_times) if self.round_times else 0,
            "max_round_time": max(self.round_times) if self.round_times else 0
        }

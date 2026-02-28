# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
Chain Call Example - RMI Call & Signal Event Demo
=================================================

토큰을 source -> mid1 -> mid2 -> dest 체인으로 전달하고,
dest에서 signal을 발생시켜 source로 토큰을 반환하는 예제.

RelayTask: nextTask 주입으로 중계/종단 역할 결정
- nextTask 있음: 다음 Task로 RMI call
- nextTask 없음: signal 발신 (종단)

사용법:
    python -m example.chain_call.main
"""

from .task_source import SourceTask
from .task_relay import RelayTask

__all__ = ["SourceTask", "RelayTask"]

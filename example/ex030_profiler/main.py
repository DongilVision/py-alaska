# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""Profiler 예제
=================
목적: task_profiler context manager 사용법 시연
     - 기본 프로파일링 (with 문)
     - 중첩 프로파일링 (outer/inner)
     - lap() 중간 지점 기록
     - JSON export
실행: python main.py
"""
import sys
import time
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import task_profiler


def compute_primes(n):
    """소수 계산 (CPU 부하용)"""
    primes = []
    for num in range(2, n):
        if all(num % i != 0 for i in range(2, int(math.sqrt(num)) + 1)):
            primes.append(num)
    return primes


def main():
    print("=" * 60)
    print("  task_profiler 예제")
    print("=" * 60)

    # 1. 기본 사용법
    print("\n--- 1. 기본 프로파일링 ---")
    with task_profiler("basic") as p:
        compute_primes(5000)

    # 2. 중첩 프로파일링
    print("\n--- 2. 중첩 프로파일링 ---")
    with task_profiler("outer"):
        with task_profiler("step_1"):
            compute_primes(3000)
        with task_profiler("step_2"):
            compute_primes(5000)
        with task_profiler("step_3"):
            compute_primes(7000)

    # 3. lap() 중간 지점 기록
    print("\n--- 3. lap() 기록 ---")
    with task_profiler("lap_demo") as p:
        compute_primes(2000)
        p.lap("after_2000")
        compute_primes(5000)
        p.lap("after_5000")
        compute_primes(10000)
        p.lap("after_10000")

    # 4. JSON export
    print("\n--- 4. JSON export ---")
    with task_profiler("export_demo", export_json=True) as p:
        compute_primes(3000)
        p.lap("checkpoint")
        compute_primes(3000)

    print("\n" + "=" * 60)
    print("  완료")
    print("=" * 60)


if __name__ == "__main__":
    main()

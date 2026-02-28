# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
ALASK 스트레스 테스트 예제
Thread/Process TASK 간 랜덤 상호 통신 데모

실행 방법:
    python example_stress.py

기능:
    - Thread/Process TASK 혼합 실행
    - Thread TASK가 랜덤하게 다른 Thread/Process TASK 메서드 호출
    - Thread→Thread, Thread→Process RMI 지원
    - Event/Signal Pub/Sub 통신 테스트
    - 실시간 통계 출력
    - JobMonitor로 웹 모니터링 (http://localhost:8080)

참고:
    - Thread→Process RMI 지원 (Manager Queue 사용)
    - Process→Process 또는 Process→Thread RMI는 미지원
    - Event는 Thread TASK만 지원
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import random
import threading
from collections import defaultdict
from src import TaskManager, reset_rmi_stats

# === 전역 통계 ===
stats = {
    "total_calls": 0,
    "success_calls": 0,
    "fail_calls": 0,
    "task_stats": defaultdict(lambda: {"sent": 0, "received": 0, "success": 0, "fail": 0}),
    # 이벤트 통계
    "total_events": 0,
    "events_emitted": 0,
    "events_received": 0,
    "event_stats": defaultdict(lambda: {"emitted": 0, "received": 0})
}
stats_lock = threading.Lock()

# === 설정 ===
THREAD_COUNT = 2     # Thread TASK 수
PROCESS_COUNT = 2      # Process TASK 수
TEST_DURATION = 3600     # 테스트 시간 (초)
CALL_INTERVAL = 0.01     # 호출 간격 (초)
EVENT_INTERVAL = 0.05    # 이벤트 발행 간격 (초)
MONITOR_PORT = 8080      # 모니터 포트

# 이벤트 이름 목록
EVENT_NAMES = ["data_ready", "status_update", "heartbeat", "notification"]


def get_total_task_count():
    """전체 TASK 수 반환"""
    return THREAD_COUNT + PROCESS_COUNT


def get_all_task_names():
    """모든 TASK 이름 목록 반환"""
    names = []
    for i in range(THREAD_COUNT):
        names.append(f"thread_{i}")
    for i in range(PROCESS_COUNT):
        names.append(f"process_{i}")
    return names


def get_thread_task_names():
    """Thread TASK 이름 목록만 반환 (Thread→Thread RMI용)"""
    return [f"thread_{i}" for i in range(THREAD_COUNT)]


def get_process_task_names():
    """Process TASK 이름 목록만 반환 (Process→Process RMI용)"""
    return [f"process_{i}" for i in range(PROCESS_COUNT)]


def stress_job_thread(task):
    """
    Thread용 스트레스 테스트 Job 함수
    랜덤하게 다른 TASK의 메서드를 호출하고 이벤트를 발행/구독
    """
    # RMI로 호출 가능한 메서드 등록
    task.call_count = 0

    def ping():
        """간단한 ping 응답"""
        task.call_count += 1
        with stats_lock:
            stats["task_stats"][task.name]["received"] += 1
        return "pong"

    def get_info():
        """TASK 정보 반환"""
        task.call_count += 1
        with stats_lock:
            stats["task_stats"][task.name]["received"] += 1
        return {
            "name": task.name,
            "call_count": task.call_count
        }

    def compute(x):
        """간단한 계산"""
        task.call_count += 1
        with stats_lock:
            stats["task_stats"][task.name]["received"] += 1
        return x * 2

    task.ping = ping
    task.get_info = get_info
    task.compute = compute

    # === 이벤트 핸들러 등록 ===
    def on_event(event):
        """이벤트 수신 핸들러"""
        with stats_lock:
            stats["events_received"] += 1
            stats["event_stats"][task.name]["received"] += 1

    # 모든 이벤트 구독
    for event_name in EVENT_NAMES:
        task.on(event_name, on_event)

    # Thread TASK와 Process TASK 모두 호출 대상
    # Thread→Thread, Thread→Process RMI 모두 지원
    # 자신 제외
    all_tasks = get_all_task_names()
    other_tasks = [t for t in all_tasks if t != task.name]

    # 모든 TASK 시작 대기
    time.sleep(1.0)

    # 메인 루프 - 랜덤 RMI 호출 + 이벤트 발행
    start_time = time.time()
    last_event_time = time.time()

    while task.is_running():
        current_time = time.time()

        # 테스트 시간 초과 시 호출 중지 (응답 대기만)
        if current_time - start_time > TEST_DURATION:
            time.sleep(0.1)
            continue

        # === 이벤트 발행 ===
        if current_time - last_event_time >= EVENT_INTERVAL:
            event_name = random.choice(EVENT_NAMES)
            event_data = {
                "sender": task.name,
                "value": random.randint(1, 1000),
                "timestamp": current_time
            }
            task.emit(event_name, event_data)

            with stats_lock:
                stats["total_events"] += 1
                stats["events_emitted"] += 1
                stats["event_stats"][task.name]["emitted"] += 1

            last_event_time = current_time

        # === RMI 호출 (모든 다른 TASK에 호출) ===
        if not other_tasks:
            time.sleep(0.1)
            continue

        # 모든 다른 TASK에 순차적으로 RMI 호출
        for target in other_tasks:
            # 랜덤 메서드 선택
            method = random.choice(["ping", "get_info", "compute"])

            try:
                with stats_lock:
                    stats["total_calls"] += 1
                    stats["task_stats"][task.name]["sent"] += 1

                # RMI 호출
                proxy = getattr(task, target)

                if method == "ping":
                    result = proxy.ping()
                elif method == "get_info":
                    result = proxy.get_info()
                else:  # compute
                    result = proxy.compute(random.randint(1, 100))

                with stats_lock:
                    stats["success_calls"] += 1
                    stats["task_stats"][task.name]["success"] += 1

            except Exception as e:
                with stats_lock:
                    stats["fail_calls"] += 1
                    stats["task_stats"][task.name]["fail"] += 1

        # 호출 간격 (모든 TASK 호출 후)
        time.sleep(CALL_INTERVAL)


def stress_job_process(task):
    """
    Process용 스트레스 테스트 Job 함수

    Note: ProcessTaskContext는 outgoing RMI를 지원하지 않음
    - Process TASK는 RMI 요청을 받기만 함 (rx_count 증가)
    - Thread→Process RMI는 정상 작동
    - Process→Process 또는 Process→Thread RMI는 미지원
    """
    # RMI로 호출 가능한 메서드 등록
    call_count = 0
    sent_count = 0
    success_count = 0
    fail_count = 0

    def ping():
        nonlocal call_count
        call_count += 1
        return "pong"

    def get_info():
        nonlocal call_count
        call_count += 1
        return {"name": task.name, "call_count": call_count}

    def compute(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    def get_stats():
        """프로세스 내부 통계 반환"""
        return {
            "received": call_count,
            "sent": sent_count,
            "success": success_count,
            "fail": fail_count
        }

    task.ping = ping
    task.get_info = get_info
    task.compute = compute
    task.get_stats = get_stats

    # Process TASK는 RMI 요청을 받기만 함
    # outgoing RMI는 지원하지 않음 (ProcessTaskContext 제한)

    # 메인 루프 - RMI 요청 대기
    while task.is_running():
        time.sleep(0.1)

    # 프로세스 종료 시 통계 출력
    print(f"[{task.name}] 받은 RMI 요청: {call_count:,}")


def reset_stats():
    """통계 초기화"""
    global stats
    with stats_lock:
        stats["total_calls"] = 0
        stats["success_calls"] = 0
        stats["fail_calls"] = 0
        stats["task_stats"].clear()
        # 이벤트 통계 초기화
        stats["total_events"] = 0
        stats["events_emitted"] = 0
        stats["events_received"] = 0
        stats["event_stats"].clear()
    reset_rmi_stats()


def print_stats(process_stats=None):
    """통계 출력"""
    with stats_lock:
        total = stats["total_calls"]
        success = stats["success_calls"]
        fail = stats["fail_calls"]
        success_rate = (success / total * 100) if total > 0 else 0

        # 이벤트 통계
        total_events = stats["total_events"]
        events_emitted = stats["events_emitted"]
        events_received = stats["events_received"]

        print("\n" + "=" * 60)
        print("스트레스 테스트 결과")
        print("=" * 60)
        print(f"Thread TASK:    {THREAD_COUNT}개")
        print(f"Process TASK:   {PROCESS_COUNT}개")
        print(f"총 TASK:        {get_total_task_count()}개")
        print("-" * 60)
        print("[RMI 통신 - Thread TASK]")
        print(f"총 호출 횟수:    {total:,}")
        print(f"성공:           {success:,}")
        print(f"실패:           {fail:,}")
        print(f"성공률:         {success_rate:.1f}%")
        print("-" * 60)
        print("[이벤트/시그널]")
        print(f"총 이벤트:       {total_events:,}")
        print(f"발행(emit):      {events_emitted:,}")
        print(f"수신(received):  {events_received:,}")
        print("-" * 60)

        # 상위 5개 Thread TASK RMI 통계
        task_list = [(name, data) for name, data in stats["task_stats"].items()]
        task_list.sort(key=lambda x: x[1]["sent"], reverse=True)

        print("Thread TASK별 RMI 통계 (상위 5개):")
        print(f"{'TASK':<15} {'보낸호출':>10} {'받은호출':>10} {'성공':>10} {'실패':>8}")
        print("-" * 60)
        for name, data in task_list[:5]:
            print(f"{name:<15} {data['sent']:>10,} {data['received']:>10,} {data['success']:>10,} {data['fail']:>8,}")

        # Process TASK RMI 통계 (API 사용)
        if process_stats and PROCESS_COUNT > 0:
            print("-" * 60)
            print("[RMI 통신 - Process TASK]")
            print(f"{'TASK':<15} {'받음(rx)':>12} {'성공':>12} {'에러':>10}")
            print("-" * 60)
            total_rx = 0
            total_rx_success = 0
            total_rx_error = 0
            for name, pstats in sorted(process_stats.items()):
                rx = pstats.get("rx_count", 0)
                rx_success = pstats.get("rx_success", 0)
                rx_error = pstats.get("rx_error", 0)
                total_rx += rx
                total_rx_success += rx_success
                total_rx_error += rx_error
                print(f"{name:<15} {rx:>12,} {rx_success:>12,} {rx_error:>10,}")
            print("-" * 60)
            print(f"{'합계':<15} {total_rx:>12,} {total_rx_success:>12,} {total_rx_error:>10,}")

        # 상위 5개 TASK 이벤트 통계
        event_list = [(name, data) for name, data in stats["event_stats"].items()]
        event_list.sort(key=lambda x: x[1]["emitted"], reverse=True)

        if event_list:
            print("-" * 60)
            print("TASK별 이벤트 통계 (상위 5개):")
            print(f"{'TASK':<15} {'발행(emit)':>15} {'수신(received)':>15}")
            print("-" * 60)
            for name, data in event_list[:5]:
                print(f"{name:<15} {data['emitted']:>15,} {data['received']:>15,}")

        print("=" * 60)


def create_task_map():
    """설정에 따른 task_map 생성"""
    task_map = {}

    # Thread TASK 생성
    for i in range(THREAD_COUNT):
        task_map[f"thread_{i}"] = {
            "mode": "thread",
            "job": stress_job_thread
        }

    # Process TASK 생성
    for i in range(PROCESS_COUNT):
        task_map[f"process_{i}"] = {
            "mode": "process",
            "job": stress_job_process
        }

    return task_map


def main():
    """스트레스 테스트 메인 함수"""
    reset_stats()

    print("=" * 60)
    print("ALASK 스트레스 테스트")
    print("=" * 60)
    print(f"Thread TASK: {THREAD_COUNT}개")
    print(f"Process TASK: {PROCESS_COUNT}개")
    print(f"총 TASK: {get_total_task_count()}개")
    print(f"테스트 시간: {TEST_DURATION}초")
    print(f"RMI 호출 간격: {CALL_INTERVAL * 1000}ms")
    print(f"이벤트 발행 간격: {EVENT_INTERVAL * 1000}ms")
    print(f"모니터: http://localhost:{MONITOR_PORT}")
    print("=" * 60)

    # task_map 생성
    task_map = create_task_map()

    # TaskManager 생성
    manager = TaskManager(task_map)

    print(f"\n[Main] {get_total_task_count()}개 TASK 시작 중...")
    start_time = time.time()

    # Monitor와 함께 시작
    monitor = manager.start_with_monitor(port=MONITOR_PORT)

    creation_time = time.time() - start_time
    print(f"[Main] 시작 완료 ({creation_time:.2f}초)")
    print(f"[Main] 모니터: {monitor.url}")

    # 진행 상황 출력
    print(f"\n[Main] 테스트 실행 중... ({TEST_DURATION}초)")

    for i in range(TEST_DURATION):
        time.sleep(1)
        with stats_lock:
            current = stats["total_calls"]
            success = stats["success_calls"]
            rate = (success / current * 100) if current > 0 else 0
            events = stats["total_events"]
            evt_recv = stats["events_received"]
        print(f"  [{i+1}/{TEST_DURATION}초] RMI: {current:,} (성공:{rate:.1f}%), 이벤트: {events:,} (수신:{evt_recv:,})")

    # 잔여 호출 완료 대기
    print("\n[Main] 잔여 호출 완료 대기 중...")
    time.sleep(2)

    # 프로세스 통계 수집 (종료 전)
    process_stats = manager.get_process_stats() if PROCESS_COUNT > 0 else {}

    # 종료
    print("[Main] TASK 종료 중...")
    manager.stop_all()
    monitor.stop()

    # 결과 출력
    print_stats(process_stats=process_stats)


def main_simple():
    """모니터 없이 간단한 스트레스 테스트"""
    reset_stats()

    print("=" * 60)
    print("ALASK 스트레스 테스트 (간단 버전)")
    print("=" * 60)
    print(f"Thread: {THREAD_COUNT}개, Process: {PROCESS_COUNT}개")

    task_map = create_task_map()

    manager = TaskManager(task_map)
    manager.start_all()

    print(f"[Main] {get_total_task_count()}개 TASK 실행 중...")

    for i in range(TEST_DURATION):
        time.sleep(1)
        with stats_lock:
            rmi = stats['total_calls']
            events = stats['total_events']
            print(f"  [{i+1}초] RMI: {rmi:,}, 이벤트: {events:,}")

    time.sleep(1)

    # 프로세스 통계 수집 (종료 전)
    process_stats = manager.get_process_stats() if PROCESS_COUNT > 0 else {}

    manager.stop_all()

    print_stats(process_stats=process_stats)


def main_mixed():
    """Thread + Process 혼합 테스트"""
    global THREAD_COUNT, PROCESS_COUNT
    THREAD_COUNT = 8
    PROCESS_COUNT = 2

    reset_stats()

    print("=" * 60)
    print("ALASK 혼합 모드 테스트")
    print("=" * 60)
    print(f"Thread: {THREAD_COUNT}개, Process: {PROCESS_COUNT}개")

    task_map = create_task_map()

    # Monitor와 함께 시작
    manager = TaskManager(task_map)
    monitor = manager.start_with_monitor(port=MONITOR_PORT)

    print(f"[Main] 모니터: {monitor.url}")
    print(f"[Main] 테스트 실행 중... ({TEST_DURATION}초)")

    for i in range(TEST_DURATION):
        time.sleep(1)
        with stats_lock:
            current = stats["total_calls"]
            success = stats["success_calls"]
            rate = (success / current * 100) if current > 0 else 0
            events = stats["total_events"]
        print(f"  [{i+1}/{TEST_DURATION}초] RMI: {current:,} (성공:{rate:.1f}%), 이벤트: {events:,}")

    time.sleep(2)

    # 프로세스 통계 수집 (종료 전)
    process_stats = manager.get_process_stats() if PROCESS_COUNT > 0 else {}

    manager.stop_all()
    monitor.stop()

    print_stats(process_stats=process_stats)


def main_scalability():
    """확장성 테스트 - TASK 수 증가"""
    global THREAD_COUNT, PROCESS_COUNT

    print("=" * 60)
    print("ALASK 확장성 테스트")
    print("=" * 60)

    test_configs = [
        (10, 0),   # 10 threads
        (20, 0),   # 20 threads
        (30, 0),   # 30 threads
        (8, 2),    # 8 threads + 2 processes
        (15, 5),   # 15 threads + 5 processes
    ]
    results = []

    for thread_cnt, process_cnt in test_configs:
        THREAD_COUNT = thread_cnt
        PROCESS_COUNT = process_cnt

        reset_stats()

        print(f"\n[테스트] Thread: {thread_cnt}, Process: {process_cnt}...")

        task_map = create_task_map()

        start = time.time()

        with TaskManager(task_map) as manager:
            time.sleep(5)  # 5초간 실행

        elapsed = time.time() - start

        with stats_lock:
            total = stats["total_calls"]
            success = stats["success_calls"]
            rate = (success / total * 100) if total > 0 else 0
            throughput = total / 5  # 초당 호출 수
            events = stats["total_events"]
            evt_recv = stats["events_received"]

        results.append({
            "thread": thread_cnt,
            "process": process_cnt,
            "total": total,
            "success_rate": rate,
            "throughput": throughput,
            "events": events,
            "evt_recv": evt_recv
        })

        print(f"  - RMI: {total:,} (성공률:{rate:.1f}%), 이벤트: {events:,} (수신:{evt_recv:,})")

    # 결과 요약
    print("\n" + "=" * 80)
    print("확장성 테스트 결과 요약")
    print("=" * 80)
    print(f"{'Thread':>8} {'Process':>8} {'RMI호출':>12} {'성공률':>10} {'처리량(/초)':>12} {'이벤트':>12}")
    print("-" * 80)
    for r in results:
        print(f"{r['thread']:>8} {r['process']:>8} {r['total']:>12,} {r['success_rate']:>9.1f}% {r['throughput']:>12,.0f} {r['events']:>12,}")


if __name__ == "__main__":
    # main()           # 기본 스트레스 테스트 (모니터 포함)
    # main_simple()    # 간단한 버전 (모니터 없음)
    # main_mixed()     # Thread + Process 혼합 테스트
    # main_scalability()  # 확장성 테스트

    main()  # 기본 실행

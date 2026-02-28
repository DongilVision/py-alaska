# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
ALASK 사용 예제
멀티프로세스 관리 시스템 데모
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from src import TaskManager, RecursiveCallError


# === Job 함수 정의 ===

def first_job(task):
    """
    첫 번째 TASK의 작업 함수
    injection으로 전달받은 값을 사용하고, 다른 TASK를 RMI로 호출
    """
    aa = task.get_injection("aa", 0)
    print(f"[{task.name}] Started with injection aa={aa}")

    # 잠시 대기 후 second task 호출
    time.sleep(1)

    try:
        # === 편리한 RMI 호출 방식 ===
        # task.second.add(10, 20) 형태로 호출 가능!
        result = task.second.add(10, 20)
        print(f"[{task.name}] task.second.add(10, 20) = {result}")

        result = task.second.multiply(5, 3)
        print(f"[{task.name}] task.second.multiply(5, 3) = {result}")

        # 기존 방식도 여전히 사용 가능
        # result = task.rmi.call("second", "add", 10, 20)

    except Exception as e:
        print(f"[{task.name}] RMI error: {e}")

    # 주기적으로 작업 수행
    for i in range(3):
        time.sleep(1)
        print(f"[{task.name}] Working... count={i + 1}, aa={aa}")


def second_job(task):
    """
    두 번째 TASK의 작업 함수
    RMI 요청을 처리하는 메서드들을 가짐
    """
    print(f"[{task.name}] Started")

    # RMI로 호출 가능한 메서드 추가
    def add(a, b):
        return a + b

    def multiply(a, b):
        return a * b

    def get_status():
        return {"status": "running", "task": task.name}

    # 메서드를 task에 동적으로 추가
    task.add = add
    task.multiply = multiply
    task.get_status = get_status

    # 메인 루프
    count = 0
    while task.is_running() and count < 10:
        time.sleep(1)
        count += 1
        print(f"[{task.name}] Heartbeat {count}")


def third_job(task):
    """
    세 번째 TASK (프로세스 모드)
    별도 프로세스에서 실행
    """
    print(f"[{task.name}] Started in separate process")
    value = task.get_injection("initial_value", 100)

    for i in range(5):
        time.sleep(1)
        value += 10
        print(f"[{task.name}] Process value={value}")

    print(f"[{task.name}] Process finished")


# === 상호 호출 예제용 Job 함수 ===

def ping_job(task):
    """
    Ping TASK - Pong을 호출하고 응답 받음
    """
    print(f"[{task.name}] Started")

    # RMI로 호출될 메서드 등록
    def get_ping_count():
        return task._ping_count

    task.get_ping_count = get_ping_count
    task._ping_count = 0

    time.sleep(0.5)  # pong이 준비될 때까지 대기

    for i in range(5):
        try:
            task._ping_count += 1
            print(f"[{task.name}] Ping #{task._ping_count} -> pong")

            # 편리한 호출 방식: task.pong.receive_ping()
            response = task.pong.receive_ping(task._ping_count)
            print(f"[{task.name}] Got response: {response}")

            time.sleep(0.5)
        except Exception as e:
            print(f"[{task.name}] Error: {e}")
            break

    print(f"[{task.name}] Finished")


def pong_job(task):
    """
    Pong TASK - Ping의 호출을 받고 다시 Ping을 호출
    """
    print(f"[{task.name}] Started")

    task._pong_count = 0

    # RMI로 호출될 메서드 등록
    def receive_ping(ping_num):
        task._pong_count += 1
        print(f"[{task.name}] Received ping #{ping_num}, sending pong #{task._pong_count}")

        # 편리한 호출 방식: task.ping.get_ping_count()
        try:
            ping_count = task.ping.get_ping_count()
            return f"Pong #{task._pong_count} (ping has sent {ping_count} pings)"
        except Exception as e:
            return f"Pong #{task._pong_count} (couldn't reach ping: {e})"

    def get_pong_count():
        return task._pong_count

    task.receive_ping = receive_ping
    task.get_pong_count = get_pong_count

    # 대기 루프
    while task.is_running():
        time.sleep(0.1)


# === task_map 정의 (spec.txt 형식) ===

task_map = {
    "first": {
        "mode": "thread",
        "job": first_job,
        "injection": {
            "aa": 3
        }
    },
    "second": {
        "mode": "thread",
        "job": second_job
    },
    "third": {
        "mode": "process",
        "job": third_job,
        "injection": {
            "initial_value": 50
        }
    }
}


# === 메인 실행 ===

def main():
    print("=" * 50)
    print("ALASK 멀티프로세스 관리 시스템 예제")
    print("=" * 50)

    # TaskManager 생성 및 task_map 설정
    manager = TaskManager(task_map)

    print("\n[Main] Starting all tasks...")
    manager.start_all()

    # 상태 확인
    print(f"\n[Main] Task status: {manager.get_all_status()}")
    print(f"[Main] Registered tasks: {manager.get_task_names()}")

    # 일정 시간 실행
    print("\n[Main] Running for 8 seconds...")
    time.sleep(8)

    # 종료
    print("\n[Main] Stopping all tasks...")
    manager.stop_all()

    print("\n[Main] Final status:", manager.get_all_status())
    print("=" * 50)
    print("Example completed!")


def main_with_context_manager():
    """컨텍스트 매니저를 사용한 예제"""
    print("=" * 50)
    print("Context Manager 예제")
    print("=" * 50)

    with TaskManager(task_map) as manager:
        print(f"Tasks running: {manager.get_task_names()}")
        time.sleep(5)

    print("All tasks stopped automatically")


def main_mutual_call():
    """상호 호출 예제 - Ping-Pong"""
    print("=" * 50)
    print("상호 호출 예제 (Ping-Pong)")
    print("=" * 50)

    # Ping-Pong task_map
    ping_pong_map = {
        "ping": {
            "mode": "thread",
            "job": ping_job
        },
        "pong": {
            "mode": "thread",
            "job": pong_job
        }
    }

    manager = TaskManager(ping_pong_map)

    print("\n[Main] Starting ping-pong tasks...")
    manager.start_all()

    # 실행
    time.sleep(5)

    # 종료
    print("\n[Main] Stopping tasks...")
    manager.stop_all()

    print("\n" + "=" * 50)
    print("Ping-Pong example completed!")


# === 신규 기능 테스트용 Job 함수 ===

def task_a_job(task):
    """Task A - 변수 참조, 타임아웃, 중첩호출 테스트"""
    print(f"[{task.name}] Started")

    # 외부에서 참조 가능한 변수 설정
    task.counter = 100
    task.message = "Hello from A"
    task.data = {"x": 1, "y": 2}

    def get_counter():
        return task.counter

    def increment():
        task.counter += 1
        return task.counter

    def call_b_which_calls_a():
        """B를 호출하고 B가 다시 A를 호출하면 중첩호출 발생"""
        return task.task_b.call_back_to_a()

    task.get_counter = get_counter
    task.increment = increment
    task.call_b_which_calls_a = call_b_which_calls_a

    time.sleep(0.5)

    # 1. 변수 참조 테스트
    print(f"\n[{task.name}] === 변수 참조 테스트 ===")
    try:
        b_value = task.task_b.shared_value
        print(f"[{task.name}] task.task_b.shared_value = {b_value}")

        # 산술 연산
        result = task.task_b.shared_value + 50
        print(f"[{task.name}] task.task_b.shared_value + 50 = {result}")
    except Exception as e:
        print(f"[{task.name}] Variable access error: {e}")

    # 2. 타임아웃 테스트
    print(f"\n[{task.name}] === 타임아웃 테스트 ===")
    try:
        # 짧은 타임아웃 설정 (100ms)
        result = task.task_b.__rmi_timeout(100).fast_method()
        print(f"[{task.name}] Fast method with 100ms timeout: {result}")
    except TimeoutError as e:
        print(f"[{task.name}] Timeout (expected for slow): {e}")
    except Exception as e:
        print(f"[{task.name}] Error: {e}")

    # 3. 중첩 호출 테스트 (A -> B -> A)
    print(f"\n[{task.name}] === 중첩 호출 테스트 ===")
    try:
        result = task.call_b_which_calls_a()
        print(f"[{task.name}] Recursive call result: {result}")
    except RecursiveCallError as e:
        print(f"[{task.name}] RecursiveCallError caught: {e}")
    except Exception as e:
        print(f"[{task.name}] Error: {e}")

    print(f"\n[{task.name}] Tests completed!")

    while task.is_running():
        time.sleep(0.5)


def task_b_job(task):
    """Task B - A에서 호출되는 태스크"""
    print(f"[{task.name}] Started")

    # 외부에서 참조 가능한 변수
    task.shared_value = 42
    task.name_str = "TaskB"

    def fast_method():
        return "fast response"

    def slow_method():
        time.sleep(2)  # 느린 작업
        return "slow response"

    def call_back_to_a():
        """A를 다시 호출 - 중첩 호출 발생"""
        print(f"[{task.name}] Trying to call back to task_a...")
        return task.task_a.get_counter()  # 이 호출은 RecursiveCallError 발생

    task.fast_method = fast_method
    task.slow_method = slow_method
    task.call_back_to_a = call_back_to_a

    while task.is_running():
        time.sleep(0.5)


def main_new_features():
    """신규 기능 테스트 - 변수참조, 타임아웃, 중첩호출"""
    print("=" * 50)
    print("신규 기능 테스트")
    print("- 변수 참조: task.other.variable")
    print("- 타임아웃: task.other.__rmi_timeout(ms)")
    print("- 중첩 호출 감지: RecursiveCallError")
    print("=" * 50)

    test_map = {
        "task_a": {
            "mode": "thread",
            "job": task_a_job
        },
        "task_b": {
            "mode": "thread",
            "job": task_b_job
        }
    }

    manager = TaskManager(test_map)

    print("\n[Main] Starting tasks...")
    manager.start_all()

    time.sleep(3)

    print("\n[Main] Stopping tasks...")
    manager.stop_all()

    print("\n" + "=" * 50)
    print("New features test completed!")


def main_with_monitor():
    """Job Monitor와 함께 실행하는 예제"""
    print("=" * 50)
    print("Job Monitor 예제")
    print("http://localhost:8080 에서 상태 확인 가능")
    print("=" * 50)

    # 간단한 worker job
    def worker_job(task):
        count = 0
        while task.is_running():
            count += 1
            time.sleep(1)

    # task_map 정의
    monitor_task_map = {
        "worker1": {"mode": "thread", "job": worker_job},
        "worker2": {"mode": "thread", "job": worker_job},
        "worker3": {"mode": "thread", "job": worker_job},
    }

    manager = TaskManager(monitor_task_map)

    # Monitor와 함께 시작
    monitor = manager.start_with_monitor(port=8080)

    print(f"\n[Main] Monitor running at {monitor.url}")
    print("[Main] Press Ctrl+C to stop...\n")

    try:
        # 30초간 실행 (실제로는 Ctrl+C로 중지)
        time.sleep(30)
    except KeyboardInterrupt:
        print("\n[Main] Interrupted by user")

    # 종료
    monitor.stop()
    manager.stop_all()

    print("\n" + "=" * 50)
    print("Monitor example completed!")


if __name__ == "__main__":
    # main()
    # main_mutual_call()
    # main_with_context_manager()
    # main_new_features()
    main_with_monitor()

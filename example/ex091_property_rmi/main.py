# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""@property RMI 프록시 테스트
=================================
목적: @property getter/setter가 process/thread 모드 프록시에서 올바르게 동작하는지 검증
  - process 모드 → RmiClient / _RmiProxy
  - thread  모드 → DirectClient / _DirectProxy
"""
import sys
import time
import multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import TaskManager, gconfig


def run_tests(label, target):
    results = []
    proxy_type = type(target).__name__

    # Test 1: 메서드 호출
    try:
        val = target.is_connected()
        results.append(("method call", "PASS", f"is_connected()={val}"))
    except Exception as e:
        results.append(("method call", "FAIL", str(e)[:60]))

    # Test 2: 일반 변수 읽기
    try:
        val = target.plain_var
        int_result = int(val)
        type_name = type(val).__name__
        if int_result == 42:
            results.append(("plain var", "PASS", f"int({type_name})={int_result}"))
        else:
            results.append(("plain var", "FAIL", f"int({type_name})={int_result}, expected 42"))
    except Exception as e:
        results.append(("plain var", "FAIL", str(e)[:60]))

    # Test 3: property setter
    try:
        target.connected = True
        results.append(("prop setter", "PASS", "connected = True"))
    except Exception as e:
        results.append(("prop setter", "FAIL", str(e)[:60]))

    # Test 4: property getter → bool(True)
    try:
        val = target.connected
        bool_result = bool(val)
        type_name = type(val).__name__
        if bool_result is True:
            results.append(("prop True", "PASS", f"bool({type_name})={bool_result}"))
        else:
            results.append(("prop True", "FAIL", f"bool({type_name})={bool_result}, expected True"))
    except Exception as e:
        results.append(("prop True", "FAIL", str(e)[:60]))

    # Test 5: property setter→False, getter→bool(False)
    try:
        target.connected = False
        val = target.connected
        bool_result = bool(val)
        type_name = type(val).__name__
        if bool_result is False:
            results.append(("prop False", "PASS", f"bool({type_name})={bool_result}"))
        else:
            results.append(("prop False", "FAIL", f"bool({type_name})={bool_result}, expected False"))
    except Exception as e:
        results.append(("prop False", "FAIL", str(e)[:60]))

    # Test 6: property getter → 산술
    try:
        target.temperature = 36.5
        val = target.temperature
        result = val + 10
        type_name = type(val).__name__
        if abs(result - 46.5) < 0.01:
            results.append(("prop arith", "PASS", f"{type_name}+10={result}"))
        else:
            results.append(("prop arith", "FAIL", f"{type_name}+10={result}, expected 46.5"))
    except Exception as e:
        results.append(("prop arith", "FAIL", str(e)[:60]))

    # Test 7: property getter → str
    try:
        target.connected = True
        val = target.status
        s = str(val)
        if "ON" in s and "36.5" in s:
            results.append(("prop str", "PASS", f"str={s}"))
        else:
            results.append(("prop str", "FAIL", f"str={s}, expected ON/36.5"))
    except Exception as e:
        results.append(("prop str", "FAIL", str(e)[:60]))

    # 결과 출력
    pass_cnt = sum(1 for _, s, _ in results if s == "PASS")
    fail_cnt = sum(1 for _, s, _ in results if s == "FAIL")
    print(f"\n{'='*60}")
    print(f"  @property Test [{label}] proxy={proxy_type}")
    print(f"{'='*60}")
    for test_name, status, detail in results:
        mark = "OK" if status == "PASS" else "NG"
        print(f"  [{mark}] {label:7s} {test_name:14s} : {detail}")
    print(f"  --- {label}: {pass_cnt} PASS / {fail_cnt} FAIL ---")
    return fail_cnt


if __name__ == "__main__":
    multiprocessing.freeze_support()
    gconfig.load(Path(__file__).parent / "config.json")

    manager = TaskManager(gconfig)
    manager.start_all()
    time.sleep(2.0)

    total_fail = 0

    # 1. Process 모드 (RmiClient → _RmiProxy)
    total_fail += run_tests("PROCESS", manager.get_client("device_p"))

    # 2. Thread 모드 (DirectClient → _DirectProxy)
    total_fail += run_tests("THREAD", manager.get_client("device_t"))

    print(f"\n{'='*60}")
    if total_fail == 0:
        print("  ALL PASSED")
    else:
        print(f"  {total_fail} FAILED")
    print(f"{'='*60}\n")

    manager.stop_all()

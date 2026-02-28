
================================================================================
task_profiler 사용법
================================================================================

1. 기본 사용법 (context manager)
--------------------------------------------------------------------------------
from py_alaska import task_profiler

with task_profiler("my_operation") as profiler:
    # 프로파일링할 코드 블록
    result = some_heavy_computation()

# 자동으로 소요 시간 기록 및 출력


2. 중첩 프로파일링
--------------------------------------------------------------------------------
with task_profiler("outer") as outer:
    with task_profiler("inner_1") as inner1:
        step1()

    with task_profiler("inner_2") as inner2:
        step2()

# 결과:
#   [inner_1] Elapsed: 0.123s
#   [inner_2] Elapsed: 0.456s
#   [outer] Elapsed: 0.579s


3. 수동 타이밍 제어
--------------------------------------------------------------------------------
with task_profiler("manual") as profiler:
    profiler.lap("start")      # 중간 지점 기록
    do_something()
    profiler.lap("checkpoint") # 체크포인트
    do_another()
    profiler.lap("end")

# lap() 간 간격도 기록됨


4. TaskManager와 통합 사용
--------------------------------------------------------------------------------
from py_alaska import TaskManager, PerformanceCollector

with TaskManager() as tm:
    # RMI 성능은 자동으로 PerformanceCollector에 기록됨
    collector = tm.get_performance_collector()

    # 시스템 전체 성능 조회
    sys_perf = collector.get_system_performance()
    print(f"Total RMI calls: {sys_perf.total_calls}")
    print(f"Avg IPC time: {sys_perf.avg_ipc_time}ms")


5. 성능 데이터 export
--------------------------------------------------------------------------------
with task_profiler("export_test", export_json=True) as profiler:
    run_benchmark()

# 종료 시 자동으로 JSON 파일 생성: profiler_export_test_20260210_123456.json

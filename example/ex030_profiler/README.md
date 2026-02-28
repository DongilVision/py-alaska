# ex030_profiler - 성능 프로파일러

## 개요
코드 블록의 실행 시간 측정 유틸리티. 중첩 프로파일링, 랩(lap) 체크포인트, JSON 내보내기를 지원한다.

## 태스크 구성

태스크 없음 — 독립 실행 유틸리티 예제.

## 시퀀스 다이어그램

```
┌──────────┐
│   main   │
└────┬─────┘
     │
     │  with task_profiler("outer") as p:
     │  ┌─────────────────────────────────┐
     │  │  with task_profiler("step_1"):  │
     │  │    work_1()                     │
     │  │  with task_profiler("step_2"):  │
     │  │    work_2()                     │
     │  │  with task_profiler("step_3"):  │
     │  │    p.lap("checkpoint_a")        │
     │  │    work_3a()                    │
     │  │    p.lap("checkpoint_b")        │
     │  │    work_3b()                    │
     │  └─────────────────────────────────┘
     │
     │  결과 출력:
     │  outer: 3.02s
     │    step_1: 1.00s
     │    step_2: 1.01s
     │    step_3: 1.01s
     │      lap checkpoint_a: 0.50s
     │      lap checkpoint_b: 0.51s
```

## 사용된 API

| API | 설명 |
|-----|------|
| `task_profiler(name)` | 컨텍스트 매니저 — 코드 블록 실행 시간 측정 |
| `p.lap(label)` | 랩 체크포인트 — 중간 구간 시간 기록 |
| `export_json=True` | JSON 파일로 프로파일 결과 내보내기 |

## 실행 방법
```bash
python main.py
```

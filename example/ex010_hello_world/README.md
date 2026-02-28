# ex010_hello_world - 기본 태스크 실행

## 개요
ALASKA 프레임워크의 최소 구성 예제. `@task` 데코레이터, `config.json`, `TaskManager`를 사용한 단일 프로세스 태스크 실행을 보여준다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `HelloTask` | process | 1초 간격으로 "Hello #count" 출력 |

## 시퀀스 다이어그램

```
┌────────────┐     ┌───────────┐
│ TaskManager│     │ HelloTask │
└─────┬──────┘     └─────┬─────┘
      │  start()         │
      │─────────────────>│
      │                  │  ┌──────────────────┐
      │                  │──│ print("Hello #1") │
      │                  │  └──────────────────┘
      │                  │  sleep(1.0)
      │                  │  ┌──────────────────┐
      │                  │──│ print("Hello #2") │
      │                  │  └──────────────────┘
      │                  │  ...반복...
      │  stop()          │
      │─────────────────>│
      │                  │  running = False
      │                  │  종료
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process")` | 프로세스 모드 태스크 데코레이터 |
| `self.running` | 프레임워크 제공 실행 플래그 (stop 시 False) |
| `TaskManager` | 컨텍스트 매니저로 태스크 라이프사이클 관리 |
| `gconfig.load()` | config.json 로드 |

## 실행 방법
```bash
python main.py
```

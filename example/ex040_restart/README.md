# ex040_restart - 태스크 자동 재시작

## 개요
예외 발생 시 태스크가 자동으로 재시작되는 `restart=True` 옵션을 시연한다. 장애 복구(fault-tolerance)에 활용된다.

## 태스크 구성

| 태스크 | 모드 | restart | 설명 |
|--------|------|---------|------|
| `UnstableTask` | process | True | 10% 확률로 RuntimeError 발생 |
| `WatcherTask` | process | False | RMI로 재시작 횟수 모니터링 |

## 시퀀스 다이어그램

```
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│  Framework   │        │ UnstableTask │        │ WatcherTask  │
└──────┬───────┘        └──────┬───────┘        └──────┬───────┘
       │  start                │                       │
       │──────────────────────>│  run_count=1          │
       │                       │  동작 중...            │
       │                       │                       │
       │                       │  RuntimeError!        │
       │  감지 & 재시작         │  ╳                    │
       │──────────────────────>│  run_count=2          │
       │                       │  동작 중...            │
       │                       │                       │──┐
       │                       │<──────────────────────│  │ RMI: run_count
       │                       │  return 2             │  │
       │                       │──────────────────────>│──┘
       │                       │                       │  "재시작 2회"
       │                       │                       │
       │                       │  RuntimeError!        │
       │  감지 & 재시작         │  ╳                    │
       │──────────────────────>│  run_count=3          │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process", restart=True)` | 예외 시 자동 재시작 활성화 |
| `self.running` | 실행 상태 플래그 |
| `self.unstable.run_count` | RMI 프로퍼티 접근 (`"client:unstable"` 주입) |
| `raise RuntimeError()` | 의도적 예외로 재시작 트리거 |

## 설정 (config.json)
```json
"watcher/WatcherTask": {
  "@import": "example.ex040_restart.tasks",
  "unstable": "client:unstable"   // RmiClient 주입
}
```

## 실행 방법
```bash
python main.py
```

# ex150_dynamic_task - 런타임 태스크 동적 생성/삭제

## 개요
실행 중 `TaskManager` API로 태스크를 동적으로 추가하고 제거하는 방법을 시연한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `ManagerTask` | thread | 정적 태스크 — 시스템 모니터 역할 |
| `WorkerTask` | thread | 동적 생성 대상 — 카운터 + ping + notify |

## 시퀀스 다이어그램

```
┌──────────┐        ┌──────────────┐        ┌──────────────┐
│   CLI    │        │ TaskManager  │        │ WorkerTask   │
│  (main)  │        │   (런타임)    │        │  (동적 생성)  │
└────┬─────┘        └──────┬───────┘        └──────┬───────┘
     │                     │                       │
     │ add_task("w1",      │                       │
     │  "WorkerTask")      │                       │
     │────────────────────>│  태스크 생성           │
     │                     │──────────────────────>│ 실행 시작
     │                     │                       │
     │ get_client("w1")    │                       │
     │────────────────────>│                       │
     │<────────────────────│ RmiClient             │
     │                     │                       │
     │ client.ping()       │                       │
     │─────────────────────────────────────────>│
     │<─────────────────────────────────────────│ "pong"
     │                     │                       │
     │ client.increment()  │                       │
     │─────────────────────────────────────────>│ counter++
     │                     │                       │
     │ client.get_counter()│                       │
     │─────────────────────────────────────────>│
     │<─────────────────────────────────────────│ return 1
     │                     │                       │
     │ get_status()        │                       │
     │────────────────────>│                       │
     │<────────────────────│ {manager_task: OK,     │
     │                     │  w1: OK}              │
     │                     │                       │
     │ remove_task("w1")   │                       │
     │────────────────────>│  태스크 종료           │
     │                     │──────────────────────>│ ╳ 종료
     │                     │                       │
     │ get_status()        │                       │
     │────────────────────>│                       │
     │<────────────────────│ {manager_task: OK}    │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(name="...", mode="thread", restart=False)` | 태스크 데코레이터 |
| `manager.add_task(id, class_name)` | 런타임에 태스크 추가 |
| `manager.remove_task(id)` | 런타임에 태스크 제거 |
| `manager.get_client(id)` | 동적 태스크 RMI 클라이언트 획득 |
| `manager.get_status()` | 전체 태스크 상태 조회 |
| `self.runtime.name` | 태스크 런타임 이름 접근 |
| `self.runtime.running` | 태스크 실행 상태 확인 |
| `signal_subscribe=["event_name"]` + `on_event_name()` | 시그널 자동 구독 및 핸들러 매핑 |

## 설정 (config.json)
```json
"task_config": {
  "manager_task/ManagerTask": {
    "@import": "example.ex150_dynamic_task.tasks"
  }
  // WorkerTask는 런타임에 동적 추가
}
```

## 실행 방법
```bash
python main.py
```

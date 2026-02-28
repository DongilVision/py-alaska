# ex120_task - 기본 태스크 관리 & RMI 통신

## 개요
스레드/프로세스 태스크 관리, RMI 메서드 호출, 파라미터 주입, 양방향 Ping-Pong 통신 등 ALASKA 태스크 시스템의 기본 기능을 종합 시연한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `first_job` | thread | RMI로 second_job 메서드 호출 (add, multiply) |
| `second_job` | thread | RMI 메서드 노출 (add, multiply, get_status) |
| `third_job` | process | 별도 프로세스에서 값 증가 |
| `ping_job` | thread | pong에게 ping 전송 |
| `pong_job` | thread | ping 수신 후 콜백 |

## 시퀀스 다이어그램

### RMI 호출 패턴
```
┌───────────┐                    ┌────────────┐
│ first_job │                    │ second_job │
└─────┬─────┘                    └──────┬─────┘
      │                                │
      │ RMI: second.add(10, 20)        │
      │───────────────────────────────>│
      │<───────────────────────────────│ return 30
      │                                │
      │ RMI: second.multiply(5, 3)     │
      │───────────────────────────────>│
      │<───────────────────────────────│ return 15
      │                                │
      │ RMI: second.get_status()       │
      │───────────────────────────────>│
      │<───────────────────────────────│ return {...}
```

### Ping-Pong 양방향 패턴
```
┌──────────┐                    ┌──────────┐
│ ping_job │                    │ pong_job │
└─────┬────┘                    └────┬─────┘
      │                              │
      │ RMI: pong.receive_ping(1)    │
      │─────────────────────────────>│
      │                              │ 처리
      │<─────────────────────────────│ RMI: ping.get_ping_count()
      │ return count                 │
      │─────────────────────────────>│
      │                              │
      │ RMI: pong.receive_ping(2)    │
      │─────────────────────────────>│
      │         ...반복...            │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task` | 태스크 데코레이터 |
| `TaskManager(task_map)` | 태스크 맵으로 초기화 |
| `task.get_injection()` | 주입된 파라미터 조회 |
| `task.<task_name>.<method>()` | 편의 RMI 문법 |
| `task.rmi.call()` | 대체 RMI 호출 문법 |
| `task.is_running()` | 태스크 실행 상태 확인 |
| `manager.start_all()` / `stop_all()` | 전체 태스크 시작/중지 |
| `manager.get_all_status()` | 전체 태스크 상태 조회 |
| `manager.get_task_names()` | 등록된 태스크 이름 목록 |
| `with TaskManager(...) as manager:` | 컨텍스트 매니저 |
| `manager.start_with_monitor(port)` | 모니터 서버 통합 실행 |

## 실행 방법
```bash
python main.py
```

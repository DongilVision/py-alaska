# ex091_property_rmi - @property RMI 프록시 검증

## 개요
Python `@property` 데코레이터가 RMI 프록시를 통해 정상 동작하는지 검증한다. 프로세스/스레드 모드, 외부/내부 클라이언트별 차이를 테스트한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `DeviceProc` | process | @property getter/setter 노출 (connected, temperature, status) |
| `DeviceThrd` | thread | 동일 인터페이스 — 스레드 모드 비교 |

## 시퀀스 다이어그램

```
┌───────────┐                      ┌─────────────┐
│   Test    │                      │ DeviceProc  │
│  (main)   │                      │ (process)   │
└─────┬─────┘                      └──────┬──────┘
      │                                   │
      │ ── RmiClient (외부 프록시) ──       │
      │ client.connected = True           │
      │──────────────────────────────────>│ @connected.setter
      │                                   │
      │ val = client.temperature          │
      │──────────────────────────────────>│ @property temperature
      │<──────────────────────────────────│ return 36.5
      │                                   │
      │ val = client.status               │
      │──────────────────────────────────>│ @property status (계산)
      │<──────────────────────────────────│ return "connected:36.5°C"
      │                                   │
      │ ── DirectClient (내부 프록시) ──    │
      │ (스레드 모드에서만)                  │
      │ client.connected                  │
      │──────────> _DirectProxy ─────────>│
```

### 테스트 매트릭스

```
                  Process        Thread
외부(RmiClient)   _RmiProxy      _DirectProxy
내부(DirectClient)  N/A          _DirectProxy
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process"/"thread")` | 태스크 모드 지정 |
| `@property` / `@setter` | 파이썬 프로퍼티 데코레이터 (RMI 호환) |
| `RmiClient(task_id, req_q, res_q)` | 프로세스 모드 외부 RMI 클라이언트 |
| `DirectClient(task_id, job_getter)` | 스레드 모드 내부 클라이언트 |
| `target.connected` | 프록시를 통한 프로퍼티 getter/setter |
| `target.is_connected()` | 프록시를 통한 메서드 호출 |

## 실행 방법
```bash
python main.py
```

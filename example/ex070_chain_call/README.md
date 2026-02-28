# ex070_chain_call - RMI 체인 호출

## 개요
여러 중계(Relay) 태스크를 거치는 중첩 RMI 호출 체인을 구성하고, 시그널로 왕복 시간을 측정하는 예제.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `SourceTask` | thread | 토큰을 체인에 전송, 왕복 시간 측정 |
| `RelayTask` (x5: mid1~mid5) | thread | 다음 태스크로 토큰 전달 |
| `RelayTask` (dest) | thread | 끝점 — 시그널로 결과 반환 |

## 시퀀스 다이어그램

```
┌────────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│ Source │   │ mid1 │   │ mid2 │   │ mid3 │   │ mid4 │   │ mid5 │   │ dest │
└───┬────┘   └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘
    │           │           │           │           │           │          │
    │ relay_    │ relay_    │ relay_    │ relay_    │ relay_    │ relay_   │
    │ token()   │ token()   │ token()   │ token()   │ token()   │ token() │
    │──────────>│──────────>│──────────>│──────────>│──────────>│────────>│
    │           │           │           │           │           │          │
    │           │           │           │           │           │          │
    │<════════════════════════════════════════════════════════════════════│
    │                    Signal: token.returned                          │
    │                                                                    │
    │  on_token_returned()                                               │
    │  왕복시간 = now - send_time                                         │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(name="...", mode="thread")` | 스레드 모드 태스크 |
| `self.nextTask.relay_token(token)` | RMI 체인 호출 (RmiClient 주입) |
| `self.signal.token.returned.emit(token)` | 끝점에서 시그널 반환 |
| `on_token_returned(self, signal)` | `on_` 자동 구독으로 결과 수신 |
| `manager.get_client(task_id)` | 런타임 RMI 클라이언트 획득 |
| `gconfig.load()` | 설정 로드 |
| `TaskManager` | 태스크 라이프사이클 관리 |

## 설정 (config.json)
```json
"mid1/RelayTask": {
  "@import": "example.ex070_chain_call.tasks",
  "nextTask": "client:mid2"    // 다음 릴레이로 RmiClient 주입
}
```

## 실행 방법
```bash
python main.py
```

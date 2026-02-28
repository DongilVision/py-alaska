# ex020_debug - Signal/RMI 디버그 모드

## 개요
Signal 발신과 RMI 호출에 대한 디버그 로깅을 활성화하는 방법을 보여준다. `debug` 옵션으로 프로세스 간 통신을 추적할 수 있다.

## 태스크 구성

| 태스크 | 모드 | debug 옵션 | 설명 |
|--------|------|-----------|------|
| `ProducerTask` | process | `"signal"` | 1초 간격으로 `data.ready` 시그널 발신 |
| `ConsumerTask` | process | `"signal,method"` | 시그널 수신 + RMI로 Producer 상태 조회 |

## 시퀀스 다이어그램

```
┌──────────────┐        ┌─────────────┐        ┌──────────────┐
│ ProducerTask │        │ SignalBroker │        │ ConsumerTask │
└──────┬───────┘        └──────┬──────┘        └──────┬───────┘
       │                       │                      │
       │ signal.data.ready     │                      │
       │ emit({count: 1})      │                      │
       │──────────────────────>│  distribute           │
       │  [DEBUG] Emitting     │─────────────────────>│
       │                       │                      │ on_data_ready()
       │                       │                      │ [DEBUG] Received
       │                       │                      │
       │<─────────────────────────────────────────────│ RMI: producer.count
       │  return count         │                      │ [DEBUG] Method call
       │──────────────────────────────────────────────>│
       │                       │                      │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process", debug="signal")` | 시그널 디버그 로깅 활성화 |
| `@task(mode="process", debug="signal,method")` | 시그널 + RMI 메서드 디버그 |
| `self.signal.data.ready.emit(data)` | 네임스페이스 시그널 발신 |
| `on_data_ready(self, signal)` | 자동 시그널 핸들러 (`on_` 접두사 패턴) |
| `self.producer.count` | RMI 프로퍼티 접근 (config에서 `"client:producer"` 주입) |
| `signal.data` | 수신된 시그널 데이터 접근 |

## 설정 (config.json)
```json
"consumer/ConsumerTask": {
  "@import": "example.ex020_debug.tasks",
  "producer": "client:producer"   // RmiClient 주입
}
```

## 실행 방법
```bash
python main.py
```

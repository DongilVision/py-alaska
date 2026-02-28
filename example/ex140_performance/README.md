# ex140_performance - Signal & IPC 성능 테스트

## 개요
ALASKA의 Signal(이벤트 브로드캐스트)과 IPC(RMI 체인 호출)의 지연시간을 스레드/프로세스 모드별로 측정한다. Qt GUI로 실시간 결과를 표시한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `PerformanceGui` | thread (QWidget) | 테스트 제어 + 결과 테이블 표시 |
| `Process1/2/3` | process (restart=True) | 프로세스 모드 체인 호출 노드 |
| `Thread1/2/3` | thread (restart=True) | 스레드 모드 체인 호출 노드 |

## 시퀀스 다이어그램

### Signal 브로드캐스트 테스트
```
┌─────────────┐     ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
│PerformanceGui│    │ P1 │ │ P2 │ │ P3 │ │ T1 │ │ T2 │ │ T3 │
└──────┬──────┘     └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘
       │               │      │      │      │      │      │
       │ wakeup.emit   │      │      │      │      │      │
       │ (timestamp)   │      │      │      │      │      │
       │══════════════>│      │      │      │      │      │
       │══════════════════════>│      │      │      │      │
       │═══════════════════════════>│      │      │      │
       │════════════════════════════════>│      │      │
       │═════════════════════════════════════>│      │
       │══════════════════════════════════════════>│
       │               │      │      │      │      │      │
       │<══════════════│ awake signal (latency 측정)       │
       │<═══════════════════>│      │      │      │      │
       │    ...각 태스크가 awake 응답...                     │
       │                                                   │
       │  결과: avg, min, max, p95, p99                     │
```

### IPC 체인 호출 테스트
```
┌─────────────┐     ┌────┐     ┌────┐     ┌────┐
│PerformanceGui│    │ P1 │     │ P2 │     │ P3 │
└──────┬──────┘     └──┬─┘     └──┬─┘     └──┬─┘
       │               │          │          │
       │ chain_call    │          │          │
       │──────────────>│ chain    │          │
       │               │─────────>│ chain    │
       │               │          │─────────>│
       │               │          │          │ on_chain
       │<──────────────────────────────────│  _result()
       │  return data  │          │          │
       │               │          │          │
       │  지연시간 = now - start_time        │
       │                                    │
       │  기준: Signal <0.5ms               │
       │        IPC <3ms, TPS >300          │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(name="...", mode="process/thread", restart=True)` | 태스크 데코레이터 |
| `self.signal.<ns>.<event>.emit(data)` | 시그널 발신 (브로드캐스트) |
| `@rmi_signal("event_name")` | 시그널 핸들러 등록 데코레이터 |
| `self.next_task.chain_call(data)` | RMI 체인 호출 (주입된 클라이언트) |
| `self.task_name` | 태스크 이름 접근 |
| `AlaskaApp.get_task(name)` | 메인 스레드에서 태스크 인스턴스 획득 |
| `AlaskaApp.get_client(name)` | RMI 클라이언트 획득 |
| `QtSignal(int, int)` | Qt 스레드 안전 UI 갱신 시그널 |
| `AlaskaApp.run()` | Qt + ALASKA 통합 실행 |

## 설정 (config.json)
```json
"p1/Process1": {
  "@import": "example.ex140_performance.task_process",
  "next_task": "client:p2"    // 체인 다음 노드
},
"gui/PerformanceGui": {
  "iterations": 100           // 테스트 반복 횟수
}
```

## 실행 방법
```bash
python main.py
```

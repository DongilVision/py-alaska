# ex050_select_signal - 선택적 시그널 수신

## 개요
동적 시그널 경로(`job.a`, `job.b` 등)를 통해 워커가 자신에게 해당하는 시그널만 선택적으로 구독하는 패턴을 보여준다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `SourceTask` | process | 0.5초 간격으로 랜덤 작업 타입(a/b/c/d) 시그널 발신 |
| `WorkerTask` (x4) | process | 각각 특정 `job_type`만 구독하여 처리 |
| `DestTask` | process (QWidget) | 결과 시그널 수신, UI 통계 표시 |

## 시퀀스 다이어그램

```
┌────────────┐    ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    ┌──────────┐
│ SourceTask │    │Worker_A │  │Worker_B │  │Worker_C │  │Worker_D │    │ DestTask │
└─────┬──────┘    └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘    └────┬─────┘
      │                │            │            │            │              │
      │ job.a emit     │            │            │            │              │
      │───────────────>│            │            │            │              │
      │                │ 처리       │            │            │              │
      │                │ result.emit│            │            │              │
      │                │───────────────────────────────────────────────────>│
      │                │            │            │            │              │ UI 갱신
      │ job.c emit     │            │            │            │              │
      │───────────────────────────>│            │            │              │
      │                │            │ (무시)      │            │              │
      │────────────────────────────────────────>│            │              │
      │                │            │            │ 처리       │              │
      │                │            │            │ result.emit│              │
      │                │            │            │────────────────────────>│
      │                │            │            │            │              │ UI 갱신
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process", debug=True)` | 전체 디버그 활성화 |
| `getattr(self.signal.job, job_type).emit(data)` | 동적 시그널 경로로 발신 |
| `self.runtime.signal.on(signal_name, handler)` | 런타임 시그널 동적 구독 |
| `self.signal.result.emit(data)` | 결과 시그널 발신 |
| `@ui_thread` | Qt 메인 스레드에서 핸들러 실행 |
| Config 파라미터 주입 | `"job_type": "a"` → `__init__` 인자로 전달 |
| `signal.data` | 수신 시그널 데이터 접근 |

## 설정 (config.json)
```json
"worker_a/WorkerTask": {
  "@import": "example.ex050_select_signal.tasks",
  "job_type": "a"   // 파라미터 주입 → WorkerTask.__init__(job_type="a")
}
```

## 실행 방법
```bash
python main.py
```

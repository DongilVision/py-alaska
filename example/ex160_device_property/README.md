# ex160_device_property - DEVICE_PROPERTY 상세 데모

## 개요
ALASKA의 `DEVICE_PROPERTY` 시스템 전체 기능을 시연한다: validator, debounce, notify_mode, @resync 자동 동기화, 조건부 HW 적용 등.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `CameraTask` | process (restart=True) | DEVICE_PROPERTY 풀 기능 카메라 모의 |
| `ControllerTask` | thread | 프로퍼티 변경 시나리오 실행 |

## DEVICE_PROPERTY 선언
```python
DEVICE_PROPERTY = {
    "is_connect:bool": {"setter": "_hw_connect"},
    "exposure:int=100": {
        "validator": "_validate_exposure",   # 0~10000 검증
        "setter": "_hw_write_exposure",      # HW 쓰기
        "debounce": 0.5,                     # 0.5초 쓰로틀
        "notify_mode": "on_write"            # HW 쓰기 시에만 시그널
    },
    "trigger_mode:bool=false": {
        "setter": "_hw_write_trigger_mode"
    },
    "@resync": {
        "open": "_resync_open",              # 세션 잠금
        "close": "_resync_close",            # 세션 해제
        "condition": {"Eq": ["is_connect", True]},
        "order": ["trigger_mode", "exposure"]
    }
}
```

## 시퀀스 다이어그램

```
┌────────────────┐                    ┌─────────────┐
│ ControllerTask │                    │ CameraTask  │
└───────┬────────┘                    └──────┬──────┘
        │                                    │
        │  ── 1. 연결 전 설정 ──              │
        │  cam.exposure = 500                │
        │───────────────────────────────────>│ _cache["exposure"] = 500
        │                                    │ (is_connect=False → HW 미적용)
        │                                    │
        │  ── 2. 연결 → @resync 트리거 ──     │
        │  cam.is_connect = True             │
        │───────────────────────────────────>│
        │                                    │ _hw_connect(True)
        │                                    │
        │                                    │ ── @resync 시작 ──
        │                                    │ _resync_open()  → 잠금
        │                                    │ _hw_write_trigger_mode(false)
        │                                    │ _hw_write_exposure(500)
        │                                    │ _resync_close() → 해제
        │                                    │
        │  ── 3. 정상 동작 (즉시 적용) ──      │
        │  cam.exposure = 1000               │
        │───────────────────────────────────>│
        │                                    │ _validate_exposure(1000) ✓
        │                                    │ _hw_write_exposure(1000)
        │                                    │ Signal 발신 (on_write)
        │                                    │
        │  ── 4. 검증 에러 ──                 │
        │  cam.exposure = -500               │
        │───────────────────────────────────>│
        │                                    │ _validate_exposure(-500)
        │<───────────────────────────────────│ ValueError!
        │  예외 캐치                          │ (프로퍼티 미변경)
        │                                    │
        │  ── 5. 재연결 시뮬레이션 ──          │
        │  cam.is_connect = False            │
        │───────────────────────────────────>│ _hw_connect(False)
        │                                    │
        │  cam.exposure = 2000               │
        │───────────────────────────────────>│ _cache에만 저장
        │                                    │
        │  cam.is_connect = True             │
        │───────────────────────────────────>│ _hw_connect(True)
        │                                    │ @resync: exposure=2000 적용
```

## 사용된 API

| API | 설명 |
|-----|------|
| `DEVICE_PROPERTY` | 딕셔너리 기반 프로퍼티 선언 |
| `"name:type=default"` | 프로퍼티 키 포맷 |
| `"setter": "_method"` | 값 변경 시 HW 쓰기 콜백 |
| `"validator": "_method"` | 값 검증 — 실패 시 ValueError |
| `"debounce": seconds` | 빠른 연속 변경 쓰로틀링 |
| `"notify_mode": "on_write"` | HW 실제 쓰기 시에만 Signal 발신 |
| `@resync` | 조건 충족 시 벌크 HW 동기화 |
| `"condition": {"Eq": [prop, val]}` | resync 활성화 조건 |
| `"order": [...]` | resync HW 적용 순서 |
| `"open" / "close"` | resync 전/후 세션 콜백 |
| `self._cache.get("prop")` | 캐시 프로퍼티 값 읽기 |
| `self.runtime.get_client(name)` | RMI 클라이언트 획득 |
| `cam.property = value` | RMI 프록시 프로퍼티 setter |
| `cam.property` | RMI 프록시 프로퍼티 getter |

## 실행 방법
```bash
python main.py
```

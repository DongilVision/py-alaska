# ex130a_camera - DEVICE_PROPERTY 카메라 (IMI)

## 개요
ex130_camera의 DeviceProperty 버전. CamProperty 디스크립터 대신 `DEVICE_PROPERTY` 딕셔너리 선언으로 카메라 프로퍼티를 관리하며, `@resync`로 하드웨어 자동 동기화를 수행한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `imi_cam_dp` | process (restart=True) | DEVICE_PROPERTY 기반 IMI 카메라 드라이버 |
| `ImiCameraView` | thread (QWidget) | SmBlock 이미지 뷰어 + 설정 다이얼로그 |

## DEVICE_PROPERTY 선언
```python
DEVICE_PROPERTY = {
    "is_connect:bool=false": {},
    "fps:float=900.0": {"setter": "_hw_set_fps"},
    "exposure:int=15000": {"setter": "_hw_set_exposure"},
    "trigger_mode:bool=false": {"setter": "_hw_set_trigger"},
    "@resync": {
        "open": "_session_open",       # 촬영 중지
        "close": "_session_close",      # 촬영 재개
        "condition": {"Eq": ["is_connect", True]},
        "order": ["trigger_mode", "fps", "exposure"]
    }
}
```

## 시퀀스 다이어그램

### 연결 + @resync 자동 동기화
```
┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ImiCameraView │     │  imi_cam_dp  │     │ IMI HW   │
│  (QWidget)   │     │  (process)   │     │ (Camera) │
└──────┬───────┘     └──────┬───────┘     └────┬─────┘
       │                    │                   │
       │ RMI: exposure=1000 │                   │
       │───────────────────>│ _cache에 저장     │
       │                    │ (is_connect=False  │
       │                    │  → HW 미적용)      │
       │                    │                   │
       │                    │ 연결 성공          │
       │                    │<──────────────────│
       │                    │ self.is_connect    │
       │                    │ = True             │
       │                    │                   │
       │                    │ ── @resync 트리거 ──
       │                    │ _session_open()    │
       │                    │──────────────────>│ 촬영 중지
       │                    │                   │
       │                    │ order 순서 적용:   │
       │                    │ 1. trigger_mode   │
       │                    │──────────────────>│ HW 설정
       │                    │ 2. fps            │
       │                    │──────────────────>│ HW 설정
       │                    │ 3. exposure=1000  │
       │                    │──────────────────>│ HW 설정
       │                    │                   │
       │                    │ _session_close()   │
       │                    │──────────────────>│ 촬영 재개
       │                    │                   │
       │                    │ camera.connected   │
       │                    │ signal.emit()      │
       │<───────────────────│                   │
       │ snapshot() 호출     │                   │
       │───────────────────>│                   │
       │<───────────────────│ {is_connect: True, │
       │ 설정 동기화          │  fps: 900,        │
       │                    │  exposure: 1000,   │
       │                    │  trigger_mode: F}  │
```

### 실시간 프레임 수신
```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────────┐
│ IMI HW   │     │  imi_cam_dp  │     │  SmBlock │     │ImiCameraView │
└────┬─────┘     └──────┬───────┘     └────┬─────┘     └──────┬───────┘
     │ 프레임 콜백       │                  │                  │
     │─────────────────>│                  │                  │
     │                  │ malloc(frame)    │                  │
     │                  │─────────────────>│ index=N          │
     │                  │                  │                  │
     │                  │ camera.received.emit({sm_index: N}) │
     │                  │────────────────────────────────────>│
     │                  │                  │                  │ get(N)
     │                  │                  │<─────────────────│
     │                  │                  │─────────────────>│ 표시
     │                  │                  │                  │ mfree(N)
```

## 사용된 API

| API | 설명 |
|-----|------|
| `DEVICE_PROPERTY` | 딕셔너리 기반 프로퍼티 선언 |
| `"name:type=default"` | 프로퍼티 키 포맷 (이름:타입=기본값) |
| `"setter": "_method"` | 프로퍼티 변경 시 HW 쓰기 콜백 |
| `@resync` | 조건 충족 시 자동 벌크 HW 적용 |
| `"condition": {"Eq": [...]}` | resync 활성 조건 |
| `"order": [...]` | resync 적용 순서 |
| `self._cache.get("prop")` | 캐시된 프로퍼티 값 읽기 |
| `target.snapshot()` | 전체 프로퍼티 스냅샷 조회 (RMI) |
| `self.is_connect = True` | 프로퍼티 변경 → resync 자동 트리거 |
| `SmBlock` | 공유 메모리 이미지 전달 |
| `@ui_thread` | Qt 메인 스레드 핸들러 |
| `AlaskaApp.run()` | Qt + ALASKA 통합 실행 |

## 실행 방법
```bash
python main.py
```

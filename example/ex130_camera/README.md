# ex130_camera - Qt 카메라 뷰어 + SmBlock

## 개요
IMI Neptune 카메라 하드웨어와 연동하여, SmBlock(공유 메모리)으로 이미지를 전달하고 Qt GUI 뷰어에 실시간 표시하는 예제.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `imi_cam_driver` | process | IMI 카메라 드라이버 — 프레임 캡처 → SmBlock |
| `ImiCameraView` | thread (QWidget) | SmBlock에서 이미지 조회, FPS/설정 표시 |

## 시퀀스 다이어그램

```
┌────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ IMI Camera │     │imi_cam_driver│     │   SmBlock    │     │ImiCameraView │
│ (Hardware) │     │  (process)   │     │  (공유메모리) │     │  (QWidget)   │
└─────┬──────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
      │                   │                    │                    │
      │  연결 시도         │                    │                    │
      │<──────────────────│                    │                    │
      │  연결 완료         │                    │                    │
      │──────────────────>│                    │                    │
      │                   │ camera.connected   │                    │
      │                   │ signal.emit()      │                    │
      │                   │───────────────────────────────────────>│
      │                   │                    │                    │
      │  프레임 콜백       │                    │                    │
      │──────────────────>│                    │                    │
      │                   │ smblock.malloc     │                    │
      │                   │ (frame_data)       │                    │
      │                   │───────────────────>│ index=N            │
      │                   │                    │                    │
      │                   │ camera.received.emit                   │
      │                   │ ({sm_index: N,     │                    │
      │                   │  fps, exposure})   │                    │
      │                   │───────────────────────────────────────>│
      │                   │                    │                    │ smblock.get(N)
      │                   │                    │<───────────────────│
      │                   │                    │ return image       │
      │                   │                    │───────────────────>│
      │                   │                    │                    │ QLabel 표시
      │                   │                    │                    │ smblock.mfree(N)
      │                   │                    │                    │
      │                   │                    │                    │ 설정 변경
      │                   │<──────────────────────────────────────│ RMI: exposure=2000
      │  HW 설정 적용      │                    │                    │
      │<──────────────────│                    │                    │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task()` | QWidget 기반 태스크 데코레이터 |
| `AlaskaApp.run()` | Qt + ALASKA 통합 앱 실행 |
| `SmBlock` | 공유 메모리 풀 — 대용량 이미지 제로카피 전달 |
| `self.smblock.malloc(data)` | SmBlock에 이미지 할당 |
| `self.smblock.get(index)` | SmBlock에서 이미지 조회 |
| `self.smblock.mfree(index)` | SmBlock 블록 해제 |
| `self.signal.camera.received.emit(dict)` | 프레임 수신 시그널 발신 |
| `self.signal.camera.connected.emit()` | 연결 상태 시그널 |
| `@ui_thread` | Qt 메인 스레드 핸들러 |
| `target.is_opened` | RMI 프로퍼티 — 카메라 연결 상태 |
| `target.exposure = value` | RMI 프로퍼티 setter — 노출 설정 |
| `target.trigger_mode = value` | RMI 프로퍼티 setter — 트리거 모드 |
| Config: `"smblock:smblock2048"` | SmBlock 풀 주입 |
| Config: `"client:camera1"` | RmiClient 주입 |

## 설정 (config.json)
```json
"platform_config": {
  "_smblock": {
    "smblock2048": { "shape": [2048, 2448, 3], "maxsize": 100 }
  }
},
"camera1/imi_cam_driver": {
  "@import": "py_alaska.drives.imi.imi_camera",
  "smblock": "smblock:smblock2048",
  "mac_address": "00:09:7e:24:08:31",
  "fps": 900, "exposure": 15000
}
```

## 실행 방법
```bash
python main.py
```

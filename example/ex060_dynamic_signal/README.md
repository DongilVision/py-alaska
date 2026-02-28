# ex060_dynamic_signal - 런타임 시그널 구독/해제

## 개요
실행 중 시그널 구독을 동적으로 on/off하는 방법을 시연한다. `.on(handler)` / `.off(handler)` API로 런타임에 구독을 제어할 수 있다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `SensorTask` | process | 0.3초 간격으로 `sensor.temp`, `sensor.humidity` 시그널 발신 |
| `MonitorTask` | process | humidity는 항상 수신, temp는 5초 간격 토글 |

## 시퀀스 다이어그램

```
┌────────────┐        ┌──────────────┐
│ SensorTask │        │ MonitorTask  │
└─────┬──────┘        └──────┬───────┘
      │                      │  on_sensor_humidity() 자동 구독
      │                      │  sensor.temp.on(handler) 동적 구독
      │                      │
      │ sensor.temp emit     │
      │─────────────────────>│  temp 핸들러 호출 ✓
      │ sensor.humidity emit │
      │─────────────────────>│  on_sensor_humidity() ✓
      │                      │
      │  ... 5초 경과 ...     │
      │                      │  sensor.temp.off(handler) 해제
      │                      │
      │ sensor.temp emit     │
      │─────────────────────>│  (수신 안 함) ✗
      │ sensor.humidity emit │
      │─────────────────────>│  on_sensor_humidity() ✓
      │                      │
      │  ... 5초 경과 ...     │
      │                      │  sensor.temp.on(handler) 재구독
      │ sensor.temp emit     │
      │─────────────────────>│  temp 핸들러 호출 ✓
```

## 사용된 API

| API | 설명 |
|-----|------|
| `self.signal.sensor.temp.emit(data)` | 네스티드 시그널 발신 |
| `self.signal.sensor.humidity.emit(data)` | 네스티드 시그널 발신 |
| `on_sensor_humidity(self, signal)` | `on_` 접두사 자동 구독 (항상 활성) |
| `self.signal.sensor.temp.on(handler)` | 런타임 동적 구독 |
| `self.signal.sensor.temp.off(handler)` | 런타임 동적 해제 |
| `self.running` | 태스크 실행 상태 플래그 |

## 실행 방법
```bash
python main.py
```

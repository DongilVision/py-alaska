# ex090_signal_rmi_combo - Signal + RMI 복합 패턴

## 개요
시그널로 이벤트(알림)를 받고, RMI로 상세 상태를 조회하는 실전 패턴. 센서가 임계치 초과 시 알림을 보내면 대시보드가 상세 정보를 RMI로 요청한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `SensorTask` | process | 랜덤 센서 값 생성, 임계치 초과 시 `sensor.alert` 시그널 |
| `DashboardTask` | process | 알림 수신 후 RMI로 `get_status()` 호출 |

## 시퀀스 다이어그램

```
┌─────────────┐        ┌───────────────┐
│ SensorTask  │        │ DashboardTask │
└──────┬──────┘        └───────┬───────┘
       │                       │
       │  값 생성: 38.5        │
       │  (임계치 35.0 초과)    │
       │                       │
       │ sensor.alert.emit     │
       │ ({value: 38.5})       │
       │──────────────────────>│  on_sensor_alert()
       │                       │  "알림 수신!"
       │                       │
       │<──────────────────────│  RMI: sensor.get_status()
       │  return {             │
       │    value: 38.5,       │
       │    threshold: 35.0,   │
       │    history: [...]     │
       │  }                    │
       │──────────────────────>│
       │                       │  상세 정보 출력
       │                       │
       │  값 생성: 28.3        │
       │  (임계치 미만 → 무시)  │
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process")` | 프로세스 모드 태스크 |
| `self.signal.sensor.alert.emit(dict)` | 알림 시그널 발신 |
| `on_sensor_alert(self, signal)` | `on_` 자동 구독 핸들러 |
| `self.sensor.get_status()` | RMI 메서드 호출 (`"client:sensor"` 주입) |
| `signal.data` | 수신 시그널 데이터 접근 |

## 설정 (config.json)
```json
"dashboard/DashboardTask": {
  "@import": "example.ex090_signal_rmi_combo.tasks",
  "sensor": "client:sensor"   // RmiClient 주입
}
```

## 실행 방법
```bash
python main.py
```

================================================================================
  ex090_signal_rmi_combo - Signal + RMI 콤보 패턴 예제
================================================================================

[ 개요 ]

  Signal 이벤트 수신 후 RMI로 상세 상태를 조회하는 실전 패턴.

  - SensorTask: 센서 값 생성, 임계값 초과 시 signal.sensor.alert 발행
  - DashboardTask: alert 시그널 수신 → sensor.get_status() RMI 호출로 상세 조회

  Signal(이벤트 알림)과 RMI(상세 데이터 조회)를 조합하여
  "알림 → 조회" 패턴을 구현하는 대표적인 예제.


[ 시그널 + RMI 흐름 ]

  SensorTask (process)                    DashboardTask (process)
  ┌──────────────────┐                    ┌──────────────────────┐
  │ value > threshold │                    │                      │
  │        │          │                    │                      │
  │   [1] Signal emit │   sensor.alert     │ [2] on_sensor_alert  │
  │  sensor.alert ────┼──────────────────>│     시그널 수신       │
  │                   │                    │        │              │
  │                   │   RMI call         │ [3] sensor.get_status│
  │   get_status() <──┼──────────────────│     RMI 호출          │
  │        │          │                    │        │              │
  │   [4] 상세 반환   │   return detail    │ [5] 결과 출력        │
  │  ────────────────>│──────────────────>│                      │
  └──────────────────┘                    └──────────────────────┘

  1. SensorTask: 센서 값이 임계값(35.0) 초과 시 signal.sensor.alert 발행
  2. DashboardTask: on_sensor_alert() 자동 구독으로 alert 수신
  3. DashboardTask: self.sensor.get_status() RMI 호출 (상세 정보 요청)
  4. SensorTask: 현재 센서 상태(value, threshold, is_alert) 반환
  5. DashboardTask: 시그널 데이터 + RMI 응답을 함께 출력


[ 파일 구성 ]

  main.py       - 진입점. gconfig 로드 후 TaskManager 실행
  config.json   - Task 구성 (SensorTask, DashboardTask)
  tasks.py      - SensorTask, DashboardTask 정의


[ config.json 설명 ]

  "sensor/SensorTask": {
    "@import": "example.ex090_signal_rmi_combo.tasks"
  }

  "dashboard/DashboardTask": {
    "@import": "example.ex090_signal_rmi_combo.tasks",
    "sensor": "client:sensor"        ← RmiClient 주입 (sensor 태스크 호출용)
  }

  * "sensor": "client:sensor"
    - "client:" 접두사 → RmiClient 객체를 자동 생성하여 주입
    - DashboardTask.sensor = RmiClient("sensor")
    - self.sensor.get_status() → SensorTask.get_status() 원격 호출


[ 핵심 패턴: Signal + RMI 콤보 ]

  1. Signal로 이벤트 알림 (경량, 브로드캐스트)
     ─────────────────────────────────────────────────────
     self.signal.sensor.alert.emit({
         "value": self.value,
         "threshold": self.threshold,
     })

     - 임계값 초과 시에만 발행 (불필요한 통신 최소화)
     - 여러 구독자가 동시에 수신 가능

  2. RMI로 상세 조회 (요청-응답, 동기)
     ─────────────────────────────────────────────────────
     def on_sensor_alert(self, signal):
         detail = self.sensor.get_status()   # RMI 호출

     - Signal 데이터: 간략한 알림 정보
     - RMI 응답: 최신 상세 상태 (value, threshold, is_alert)

  3. on_* 자동 구독
     ─────────────────────────────────────────────────────
     def on_sensor_alert(self, signal):
       → "sensor.alert" 시그널 자동 구독

     변환 규칙: on_{name} → _ 를 . 으로 치환
       on_sensor_alert  → "sensor.alert"


[ 실행 ]

  python example/ex090_signal_rmi_combo/main.py


[ 예상 출력 ]

  [Dashboard] Alert #1: value=38.2, detail={'value': 38.2, 'threshold': 35.0, 'is_alert': True}
  [Dashboard] Alert #2: value=41.7, detail={'value': 41.7, 'threshold': 35.0, 'is_alert': True}
  [Dashboard] Alert #3: value=36.1, detail={'value': 36.1, 'threshold': 35.0, 'is_alert': True}
  ...
  Enter to stop...


================================================================================

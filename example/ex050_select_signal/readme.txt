================================================================================
  ex050_select_signal - 선택적 시그널 분배 예제
================================================================================

[ 개요 ]

  Source가 랜덤 job(a,b,c,d)을 생성하면,
  각 Worker가 자신의 job_type에 해당하는 시그널만 수신하여 처리하고,
  결과(ok/ng)를 Dest(UI)가 수신하여 PySide6 GUI로 집계 표시한다.

  - Process 간 시그널 통신 (Source, Worker = process 모드)
  - Thread 기반 Qt UI Task (Dest = thread 모드, QObject)
  - 동적 시그널 구독 (job_type injection 기반)
  - @ui_thread 데코레이터로 안전한 UI 업데이트


[ 시그널 흐름 ]

  SourceTask (process)          WorkerTask x4 (process)         DestTask (thread)
  ┌─────────────┐               ┌──────────────┐               ┌──────────────┐
  │ job.a emit ─┼──────────────>│ worker_a     │               │              │
  │ job.b emit ─┼──────────────>│ worker_b     │  result emit  │  on_result   │
  │ job.c emit ─┼──────────────>│ worker_c     │──────────────>│  @ui_thread  │
  │ job.d emit ─┼──────────────>│ worker_d     │               │  GUI 업데이트│
  └─────────────┘               └──────────────┘               └──────────────┘

  1. SourceTask: 0.5초 간격으로 랜덤 job 타입(a~d) 시그널 발행
     - self.signal.job.a.emit(data)  →  시그널명: "job.a"
     - self.signal.job.b.emit(data)  →  시그널명: "job.b"
     - ...

  2. WorkerTask: config에서 주입된 job_type에 따라 동적 구독
     - worker_a: "job.a" 구독  →  on_job() 호출
     - worker_b: "job.b" 구독  →  on_job() 호출
     - 처리 후 self.signal.result.emit({ok/ng}) 발행

  3. DestTask: "result" 시그널 수신 (on_result → 자동 구독)
     - @ui_thread로 Qt UI 스레드에서 안전하게 GUI 업데이트


[ 파일 구성 ]

  main.py       - 진입점. AlaskaApp.run()으로 Qt앱 + TaskManager 시작
  config.json   - Task 구성 (6개 Task: source, worker_a~d, dest)
  tasks.py      - SourceTask, WorkerTask 정의
  dest_ui.py    - DestTask(QObject) + ResultWindow(QWidget) 정의


[ config.json 설명 ]

  "source/SourceTask": {
    "@import": "example.ex050_select_signal.tasks",
    "interval": 0.5              ← self.interval에 주입 (발행 간격)
  }

  "worker_a/WorkerTask": {
    "@import": "example.ex050_select_signal.tasks",
    "job_type": "a"              ← self.job_type에 주입 → "job.a" 구독 결정
  }

  "dest/DestTask": {
    "@import": "example.ex050_select_signal.dest_ui"
  }

  * task_id/TaskClassName 형식: "worker_a/WorkerTask"
    - task_id = "worker_a" (인스턴스 식별)
    - TaskClassName = "WorkerTask" (@task(name=...)으로 등록된 클래스)
    - 같은 클래스를 여러 인스턴스로 사용 가능 (worker_a~d)


[ 주요 기법 ]

  1. 동적 시그널 구독
     ─────────────────────────────────────────────────────
     config.json에서 "job_type": "b"를 주입하면
     WorkerTask.run()에서 동적으로 구독:

       def run(self):
           job_type = getattr(self, 'job_type', 'a')
           self.runtime.signal.on(f"job.{job_type}", self.on_job)

     - self.runtime.signal → SignalClient 직접 접근
     - .on(시그널명, 핸들러) → 해당 시그널 구독 등록

     cf) 정적 구독:
       def on_job_a(self, signal):  ← "job.a" 자동 구독 (클래스에 고정)

  2. 시그널 체인 emit
     ─────────────────────────────────────────────────────
     self.signal.job.a.emit(data)

     - self.signal     → _SignalEmitter (체인 빌더)
     - .job            → path = "job"
     - .a              → path = "job.a"
     - .emit(data)     → SignalClient.emit("job.a", data)

  3. on_* 자동 구독 (정적)
     ─────────────────────────────────────────────────────
     메서드 이름이 on_으로 시작하면 자동 구독:

       def on_result(self, signal):  → "result" 시그널 자동 구독
       def on_job_a(self, signal):   → "job.a" 시그널 자동 구독

     변환 규칙: on_{name} → name 에서 _ → . 치환
       on_sensor_data  → "sensor.data"
       on_job_a        → "job.a"
       on_result       → "result"

  4. @ui_thread 데코레이터
     ─────────────────────────────────────────────────────
     Signal 핸들러는 별도 스레드에서 호출되므로
     Qt 위젯 조작 시 @ui_thread 필요:

       @ui_thread
       def on_result(self, signal):
           _window.update_result(...)  # 안전하게 UI 스레드에서 실행

  5. Process 모드 시그널 통신
     ─────────────────────────────────────────────────────
     SourceTask, WorkerTask = process 모드 (별도 프로세스)
     DestTask = thread 모드 (메인 프로세스)

     Process → Main 시그널 전달:
       subprocess emit → relay queue → main broker → 구독자 queue → handler

     동적 구독 전파:
       subprocess subscribe → relay queue → main broker에 등록


[ 실행 ]

  python example/ex050_select_signal/main.py

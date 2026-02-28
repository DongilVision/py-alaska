ex180 JoyStick - BT 게임패드 CNC Jog 제어
==========================================

구성
----
  main.py            진입점. AlaskaApp.run(config, main_task="ui")
  config.json        task 등록 (joystick: process, ui: main)
  task_joystick.py   BT HID 게임패드 입력 → signal 발행 (별도 프로세스)
  task_ui.py         PySide6 QWidget — signal 수신 → GUI 표시


Signal 흐름
-----------
  JoyStickTask (process)              UITask (main/Qt)
  ─────────────────────               ────────────────
  jog.connect  → bool          ──→    연결 상태 표시 (녹/적)
  jog.pos      → {x,y,z}      ──→    6축 좌표 표시
  jog.shot     → int           ──→    카메라 샷 카운트
  jog.inc      → float         ──→    증분 버튼 checked 갱신
  jog.raw      → str           ──→    Raw Trace 로그 누적

                               ←──    jog.set_inc ← float (더블클릭)


증분(Increment) 관리 설계
-------------------------

1. 증분 리스트
   _INC_LIST = [0.1, 1.0, 5.0, 10.0]   (mm 단위)

2. 증분 선택 방법

   (A) 게임패드 버튼 [2]
       byte[2] 값 변화 감지
       d2 > 0 → 증분 올림 (idx + 1, 최대 3)
       d2 < 0 → 증분 내림 (idx - 1, 최소 0)
       → jog.inc.emit(선택값) 발행

   (B) UI 더블클릭
       증분 버튼 더블클릭 → jog.set_inc.emit(값) 발행
       JoyStickTask.on_jog_set_inc() 수신
       → _inc_idx 갱신 → jog.inc.emit(값) 확인 응답
       → UITask.on_jog_inc() 수신 → 버튼 checked 갱신

3. 증분 적용 — Z축 step

   D-pad 좌/우 입력 시:
     dz = data[3] - idle[3]
     zs = {-6: +1.0, -2: -1.0}.get(dz, 0)   (방향: 좌=+, 우=-)

     Z += zs * inc
         ↑        ↑
         방향     선택된 증분값 (_INC_LIST[_inc_idx])

   예) inc=5.0, D-pad 좌 → Z += (+1.0) * 5.0 = +5.0mm
       inc=0.1, D-pad 우 → Z += (-1.0) * 0.1 = -0.1mm

4. 증분 설정 시퀀스

   [UI 더블클릭 5.0]
        │
        ▼
   jog.set_inc.emit(5.0)  ──→  JoyStickTask.on_jog_set_inc()
                                  │ _inc_idx = 2
                                  │ inc = _INC_LIST[2] = 5.0
                                  ▼
                                jog.inc.emit(5.0)  ──→  UITask.on_jog_inc()
                                                          │ _update_inc(5.0)
                                                          │ [0.1][ 1 ][*5*][ 10]
                                                          ▼
                                                        확인 완료

   [게임패드 버튼 올림]
        │
        ▼
   byte[2] 변화 감지, d2 > 0
     _inc_idx: 2 → 3
     inc = _INC_LIST[3] = 10.0
        │
        ▼
   jog.inc.emit(10.0)  ──→  UITask.on_jog_inc()
                               │ [0.1][ 1 ][ 5 ][*10*]
                               ▼
                             표시 갱신

5. Z축 계산 전체 흐름

   매 0.25초 (4Hz):
     nz = D-pad 상하 → 연속 jog 방향 (+1/-1/0)
     zs = D-pad 좌우 → step 방향 (+1/-1/0)
     inc = _INC_LIST[_inc_idx]

     Z += nz * 50.0 * dt    (연속 jog: 최대 50mm/s)
        + zs * inc           (step: 증분값만큼 1회)

     → jog.pos.emit({x, y, z})


기능 요약
---------

JoyStickTask (mode="process")
  - BT HID 자동 감지: hidapi로 GamePad(0x05)/Joystick(0x04) 스캔
  - BT 자동 활성화: bthprops.cpl로 페어링된 게임패드 HID 서비스 활성화
  - 연결/해제 감지: HID open → connect(True), close → connect(False)
  - X,Y 축: 16bit LE (byte[4:6]=X, byte[6:8]=Y), 32768 정규화, deadzone 30%
  - Z 축: D-pad 상하 → 연속 jog, D-pad 좌우 → 증분 step
  - 카메라 샷: byte[1]=0x40 → shot_count 증가
  - 증분 전환: byte[2] 변화 → 리스트 순환
  - 증분 설정 수신: UI jog.set_inc → 갱신 → jog.inc 확인 응답
  - Raw 이벤트: 모든 바이트 변화를 "[i]=XX" 문자열로 발행

UITask (PySide6 QWidget)
  - 블랙테마: 바탕색 #333
  - 연결 상태 바: CONNECTED(녹) / DISCONNECTED(적)
  - 6축 좌표: X,Y,Z,A,B,C — Consolas 녹색(#0f0) 표시
  - 카메라 샷 카운트: 오렌지(#ff9800)
  - 증분 버튼: [0.1, 1.0, 5.0, 10.0] — 더블클릭 시 구동기에 설정, 응답 확인
  - Raw Trace: 하단 채움, 스크롤 200줄, Clear 버튼


조작 (Nintendo Switch Pro Controller)
--------------------------------------
  좌스틱 좌우        X축 jog (속도 비례, 50mm/s max)
  좌스틱 상하        Y축 jog (속도 비례, 50mm/s max)
  D-pad 상/하        Z축 연속 jog
  D-pad 좌/우        Z축 증분 step (선택된 inc값)
  버튼 [1]=0x40      카메라 샷
  버튼 [2]           증분 올림/내림


실행
----
  python example/ex180_JoyStick/main.py

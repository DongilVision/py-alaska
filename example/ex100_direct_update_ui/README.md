# ex100_direct_update_ui - 프로세스 시그널 → Qt UI 직접 갱신

## 개요
백그라운드 프로세스 태스크가 시그널로 점수 데이터를 전송하면, QWidget 태스크가 `@ui_thread`를 통해 안전하게 UI를 갱신한다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `SumProcess` | process | 0.1초 간격 랜덤 점수 생성, `score.update` 시그널 발신 |
| `ScoreTask` | thread (QWidget) | 시그널 수신, QLabel 갱신 |

## 시퀀스 다이어그램

```
┌────────────┐        ┌─────────────┐        ┌────────────┐
│ SumProcess │        │ SignalBroker │        │ ScoreTask  │
│ (process)  │        │              │        │ (QWidget)  │
└─────┬──────┘        └──────┬───────┘        └─────┬──────┘
      │                      │                      │
      │  score = random(1~100)                      │
      │  total += score      │                      │
      │                      │                      │
      │ score.update.emit    │                      │
      │ ({score, total,      │                      │
      │   count})            │  distribute          │
      │─────────────────────>│─────────────────────>│
      │                      │                      │ @ui_thread
      │                      │                      │ on_score_update()
      │                      │                      │ ┌──────────────┐
      │                      │                      │ │ Score: 75    │
      │                      │                      │ │ Total: 1250  │
      │                      │                      │ │ Count: 20    │
      │  sleep(0.1)          │                      │ └──────────────┘
      │                      │                      │
      │ score.update.emit    │                      │
      │─────────────────────>│─────────────────────>│ UI 갱신
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(debug="rmi, signal")` | RMI + Signal 디버그 동시 활성화 |
| `self.signal.score.update.emit(dict)` | 딕셔너리 데이터 시그널 발신 |
| `@ui_thread` | Qt 메인 스레드에서 안전하게 핸들러 실행 |
| `on_score_update(self, signal)` | `on_` 자동 구독 핸들러 |
| `signal.data` | 수신 시그널 딕셔너리 접근 |
| `AlaskaApp.run(..., main_task="score")` | 특정 태스크를 메인 윈도우로 실행 |

## 실행 방법
```bash
python main.py
```

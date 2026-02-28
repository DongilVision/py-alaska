# ex080_persistent - 영속적 카운터 + Qt UI

## 개요
백그라운드 프로세스 태스크가 카운터를 증가시키며 시그널로 Qt UI에 실시간 업데이트한다. 슬라이더로 인터벌을 동적으로 변경할 수 있다.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `SourceTask` | process | 설정 인터벌로 카운터 증가, `count` 시그널 발신 |
| `ViewerTask` | thread (QWidget) | 시그널 수신, UI 갱신, 슬라이더로 인터벌 변경 |

## 시퀀스 다이어그램

```
┌────────────┐        ┌─────────────┐        ┌────────────┐
│ SourceTask │        │ SignalBroker │        │ ViewerTask │
│ (process)  │        │              │        │ (QWidget)  │
└─────┬──────┘        └──────┬───────┘        └─────┬──────┘
      │                      │                      │
      │  gconfig.data_get    │                      │
      │  ("user_config.      │                      │
      │   interval")         │                      │
      │  → 1.8s              │                      │
      │                      │                      │
      │ count.emit(value)    │                      │
      │─────────────────────>│  distribute          │
      │                      │─────────────────────>│
      │                      │                      │ @ui_thread
      │                      │                      │ update_count()
      │  sleep(1.8s)         │                      │ QLabel 갱신
      │                      │                      │
      │                      │                      │ 슬라이더 변경
      │                      │                      │ gconfig.data_set
      │                      │                      │ ("user_config.
      │                      │                      │  interval", 0.5)
      │  gconfig.data_get    │                      │
      │  → 0.5s (변경됨)      │                      │
      │                      │                      │
      │ count.emit(value)    │                      │
      │─────────────────────>│─────────────────────>│ UI 갱신
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process")` | 프로세스 모드 태스크 |
| `self.signal.count.emit(value)` | 시그널 발신 |
| `self.runtime.signal.on(name, handler)` | 시그널 구독 |
| `@ui_thread` | Qt 메인 스레드 핸들러 데코레이터 |
| `gconfig.data_get(key)` | 런타임 설정 값 읽기 |
| `gconfig.data_set(key, value)` | 런타임 설정 값 변경 |
| `AlaskaApp.run()` | Qt 앱 + ALASKA 통합 실행 |

## 실행 방법
```bash
python main.py
```

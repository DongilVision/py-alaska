# ex110_smblock - SmBlock 공유 메모리 Producer-Consumer

## 개요
SmBlock(공유 메모리 풀)을 사용하여 대용량 numpy 배열을 프로세스 간 제로카피로 전달하는 Producer-Consumer 패턴.

## 태스크 구성

| 태스크 | 모드 | 설명 |
|--------|------|------|
| `Producer` (x3) | process | 랜덤 이미지 생성 → SmBlock 할당 → Consumer에 인덱스 전달 |
| `Consumer` | process | 인덱스 수신 → SmBlock 데이터 조회 → 처리 → 해제 |

## 시퀀스 다이어그램

```
┌───────────┐  ┌───────────┐  ┌───────────┐        ┌─────────────┐
│ Producer1 │  │ Producer2 │  │ Producer3 │        │  Consumer   │
└─────┬─────┘  └─────┬─────┘  └─────┬─────┘        └──────┬──────┘
      │              │              │                      │
      │ smblock.malloc(image)       │                      │
      │──┐ index=0   │              │                      │
      │<─┘            │              │                      │
      │              │ smblock.malloc(image)                │
      │              │──┐ index=1   │                      │
      │              │<─┘            │                      │
      │              │              │ smblock.malloc(image) │
      │              │              │──┐ index=2            │
      │              │              │<─┘                    │
      │              │              │                      │
      │ RMI: consumer.on_input(0)  │                      │
      │───────────────────────────────────────────────────>│
      │              │              │                      │ smblock.get(0)
      │              │ RMI: consumer.on_input(1)           │ 처리
      │              │────────────────────────────────────>│ smblock.mfree(0)
      │              │              │                      │
      │              │              │ RMI: consumer.on_input(2)
      │              │              │─────────────────────>│ smblock.get(2)
      │              │              │                      │ 처리
      │              │              │                      │ smblock.mfree(2)

    ┌─────────────────────────────────────────────┐
    │         SmBlock Pool (공유 메모리)            │
    │  shape: [480, 640, 3]  maxsize: 1000        │
    │  ┌─────┐┌─────┐┌─────┐         ┌─────┐     │
    │  │ [0] ││ [1] ││ [2] │  ...    │[999]│     │
    │  └─────┘└─────┘└─────┘         └─────┘     │
    └─────────────────────────────────────────────┘
```

## 사용된 API

| API | 설명 |
|-----|------|
| `@task(mode="process", restart=True)` | 프로세스 모드 + 자동 재시작 |
| `self.smblock.malloc(data)` | 공유 메모리에 데이터 할당, 인덱스 반환 |
| `self.smblock.get(index)` | 인덱스로 공유 메모리 데이터 조회 |
| `self.smblock.mfree(index)` | 공유 메모리 블록 해제 |
| `self.consumer.on_input(index)` | RMI로 인덱스 전달 (`"client:consumer"` 주입) |
| `self.task_name` | 태스크 이름 접근 |
| Config: `"smblock:pool_name"` | SmBlock 풀 참조 주입 |

## 설정 (config.json)
```json
"platform_config": {
  "_smblock": {
    "pool": { "shape": [480, 640, 3], "maxsize": 1000 }
  }
},
"producer1/Producer": {
  "smblock": "smblock:pool",          // SmBlock 풀 주입
  "consumer": "client:consumer"       // RmiClient 주입
}
```

## 실행 방법
```bash
python main.py
```

# Signal / RMI 성능 시험

## 목적
Signal 및 RMI(Remote Method Invocation)의 성능을 측정한다.

## 구성요소
- View: 1개 (GUI)
- Process: 3개
- Thread: 3개

---

## 시험 항목

### 1. Signal 브로드캐스트 성능 시험
- 모든 Task에 signal(wakeup)을 발신
- 각 Task가 응답(awake)하는 시간을 측정
- 측정 항목:
  - 시그널 발생 시각
  - 수신 소요 시간
  - 응답 발신 시각
- GUI에 회신별 응답 시간 표시
- 반복 횟수: 100회

### 2. 중첩 IPC 성능 시험

#### 2-1. Process 간 중첩 IPC
```
P1 → P2 → P3 → GUI
```

#### 2-2. Thread 간 중첩 IPC
```
T1 → T2 → T3 → GUI
```

#### 2-3. Process/Thread 혼합 중첩 IPC
```
P1 → T1 → P2 → T2 → GUI
```

### 3. Nowait 성능 시험
- 비동기(nowait) 호출의 성능을 측정

### 4. 부하 및 스트레스 시험

#### 4-1. 부하 테스트 (Load Test)
- 동시 호출 수를 점진적으로 증가 (10 → 50 → 100 → 500)
- 각 단계별 응답 시간 및 성공률 측정

#### 4-2. 스트레스 테스트 (Stress Test)
- 시스템 한계치까지 부하 증가
- 장애 발생 시점 및 복구 동작 확인

### 5. 리소스 모니터링
- CPU 사용률 측정
- 메모리 사용량 측정
- Cold start vs Warm run 성능 비교

---

## 시험 환경

### 하드웨어
- CPU: (기재 필요)
- RAM: (기재 필요)

### 소프트웨어
- OS: Windows / Linux
- Python 버전: 3.x
- 네트워크: 로컬 (localhost)

---

## 시험 조건

| 항목 | 값 |
|------|-----|
| 메시지 페이로드 크기 | 소형(1KB) / 중형(10KB) / 대형(100KB) |
| 반복 횟수 | 100회 |
| Warm-up 횟수 | 10회 |
| Timeout | 5000ms |
| 동시 호출 수 | 1 / 10 / 50 / 100 |

---

## 측정 지표

| 지표 | 설명 |
|------|------|
| 평균 (Avg) | 전체 응답 시간의 평균 |
| 최소 (Min) | 가장 빠른 응답 시간 |
| 최대 (Max) | 가장 느린 응답 시간 |
| 표준편차 (Std) | 응답 시간의 분산 정도 |
| P50 | 50번째 백분위수 (중앙값) |
| P95 | 95번째 백분위수 |
| P99 | 99번째 백분위수 |
| TPS | 초당 처리 건수 (Transactions Per Second) |

---

## 성공 기준

| 항목 | 목표 |
|------|------|
| Signal 응답 시간 | < 0.1ms |
| IPC 응답 시간 | < 0.1ms |
| 실패율 | < 0.1% |
| TPS | > 10000 |

---

## 실행 방법

```bash
# 시험 실행
python main.py

# 특정 시험만 실행
python main.py --test signal
python main.py --test ipc
python main.py --test nowait
python main.py --test stress
```

---

## 결과 출력

### 출력 위치
- 콘솔: 실시간 진행 상황
- GUI: 그래프 및 통계
- 파일: `results/performance_YYYYMMDD_HHMMSS.json`

### 결과 형식
```json
{
  "test_name": "signal_broadcast",
  "timestamp": "2026-02-10T12:00:00",
  "iterations": 100,
  "metrics": {
    "avg_ms": 5.2,
    "min_ms": 1.1,
    "max_ms": 15.8,
    "std_ms": 2.3,
    "p50_ms": 4.8,
    "p95_ms": 10.2,
    "p99_ms": 14.1,
    "tps": 1250,
    "success_rate": 100.0
  }
}
```
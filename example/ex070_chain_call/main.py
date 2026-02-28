# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
Chain Call Example - 중첩 RMI 호출 & Signal 이벤트 테스트
=========================================================

목적: 중첩 호출(Chain RMI)과 이벤트(Signal)를 시험

실행:
  python -m example.chain_call.main
"""

import sys
import time
import multiprocessing
from pathlib import Path

# 프로젝트 루트 경로 설정
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import TaskManager, gconfig, banner


def main():
    """Chain Call 예제 실행"""
    # 배너 출력
    banner("Chain Call Example", [
        "Chain RMI: source -> mid1 -> mid2 -> mid3 -> mid4 -> mid5 -> dest",
        "Signal Event: dest -> source (token.returned)",
        "RelayTask: nextTask 주입으로 체인 구성",
    ])

    # 설정 파일 로드
    config_path = Path(__file__).parent / "config.json"
    gconfig.load(config_path)

    print("\n[Main] Starting Chain Call example...")
    print("=" * 60)

    # TaskManager 생성 및 시작
    with TaskManager(gconfig) as manager:
        print("\n[Main] All tasks started. Waiting for completion...\n")

        # Task 초기화 대기
        time.sleep(2.0)

        # 토큰 처리 모니터링 (최대 30초)
        start_time = time.time()
        max_wait = 30

        while (time.time() - start_time) < max_wait:
            try:
                # source의 상태 확인
                source_client = manager.get_client("source")
                status = source_client.get_status()

                round_count = status.get("round_count", 0)
                total_rounds = status.get("total_rounds", 10)
                tokens = status.get("tokens", 0)
                min_time = status.get("min_round_time", 0)
                avg_time = status.get("avg_round_time", 0)
                max_time = status.get("max_round_time", 0)

                print(f"[Main] Progress: {round_count}/{total_rounds} rounds, "
                      f"tokens: {tokens}, "
                      f"min: {min_time:.2f}ms, avg: {avg_time:.2f}ms, max: {max_time:.2f}ms")

                if round_count >= total_rounds:
                    print("\n[Main] All rounds completed!")
                    break

            except Exception as e:
                print(f"[Main] Status check: {e}")

            time.sleep(3.0)

        # 최종 상태 출력
        print("\n" + "=" * 60)
        print("[Main] Final Status:")
        print("=" * 60)

        try:
            source_status = manager.get_client("source").get_status()
            print(f"  Source: {source_status}")
            # relay task 카운트 동적 조회
            for tid in ["mid1", "mid2", "mid3", "mid4", "mid5", "dest"]:
                try:
                    count = manager.get_client(tid).get_relay_count()
                    print(f"  {tid} relay count: {count}")
                except Exception:
                    pass
        except Exception as e:
            print(f"  Error: {e}")

        print("=" * 60)

    print("\n[Main] Chain Call example completed!")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

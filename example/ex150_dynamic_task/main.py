# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""동적 Task 생성/삭제 예제
==============================
목적: add_task / remove_task API로 런타임에 Task를 추가/삭제
실행: python main.py
"""
import sys
import multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import TaskManager, gconfig

if __name__ == "__main__":
    multiprocessing.freeze_support()
    gconfig.load(Path(__file__).parent / "config.json")

    manager = TaskManager(gconfig)
    manager.start_all()

    print("\n=== 동적 Task 생성/삭제 예제 ===")
    print("  add <id>      : WorkerTask 동적 추가")
    print("  remove <id>   : Task 동적 삭제")
    print("  ping <id>     : Task에 ping RMI 호출")
    print("  inc <id>      : Task counter 증가")
    print("  status        : 전체 Task 상태 조회")
    print("  quit          : 종료\n")

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            if action == "quit":
                break

            elif action == "add" and len(parts) >= 2:
                tid = parts[1]
                ok = manager.add_task(tid, "WorkerTask")
                print(f"  → add_task('{tid}'): {ok}")

            elif action == "remove" and len(parts) >= 2:
                tid = parts[1]
                ok = manager.remove_task(tid)
                print(f"  → remove_task('{tid}'): {ok}")

            elif action == "ping" and len(parts) >= 2:
                tid = parts[1]
                try:
                    client = manager.get_client(tid)
                    print(f"  → {client.ping()}")
                except Exception as e:
                    print(f"  → Error: {e}")

            elif action == "inc" and len(parts) >= 2:
                tid = parts[1]
                try:
                    client = manager.get_client(tid)
                    val = client.increment()
                    print(f"  → counter = {val}")
                except Exception as e:
                    print(f"  → Error: {e}")

            elif action == "status":
                status = manager.get_status()
                if not status:
                    print("  (no tasks)")
                for tid, info in status.items():
                    print(f"  {tid}: class={info.get('class','?')}, alive={info.get('alive','?')}")

            else:
                print("  Unknown command. Try: add/remove/ping/inc/status/quit")

    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        manager.stop_all()
        print("Stopped.")

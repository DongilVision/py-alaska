# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
Process TASK 예제 - 간단 버전
Process TASK에 RMI 호출하고 응답 받기

config.json 구조:
{
    "app_info": { "name": "...", "id": "...", "version": "..." },
    "task_config": {
        "process1/aaa": { "nextTask": "client:process2", "counter": 120000 },
        "process2/aaa": { "nextTask": "client:process1", "counter": 120000 },
        "_monitor": {
            "port": 7000,      // 모니터 포트 (필수)
            "exit_hook": true  // 프로세스 종료 시 stop_all 자동 호출
        }
    }
}
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import os
from src import TaskManager
from src import gconfig

import example.task_aaa as task_aaa  # noqa: F401 - rmi_class 등록용


def main():
    print("=== Process TASK 예제 ===\n")

    # 예제 디렉토리로 이동 (config.json 위치)
    os.chdir(Path(__file__).resolve().parent)

    # gconfig에서 task_config 읽어서 TaskManager 초기화
    # _monitor.port 있으면 모니터 시작, exit_hook=true면 종료 핸들러 등록
    gconfig.load("config.json").dump()
    manager = TaskManager(gconfig)
    manager.start_all()
    time.sleep(100000)
    manager.stop_all()


if __name__ == "__main__":
    main()

# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
Webcam Driver (OpenCV VideoCapture)
====================================
cv2.VideoCapture 기반 웹캠 드라이버
- SmBlock 기반 프레임 공유
- camera.received / camera.connected / camera.disconnected 시그널
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from py_alaska import task
from py_alaska.core.task_signal_decl import TSignal



@task(name="webcam_driver", mode="process", restart=True)
class webcam_driver:
    """OpenCV Webcam Driver"""

    camera_connected = TSignal(dict, name="camera.connected")
    camera_disconnected = TSignal(dict, name="camera.disconnected")
    camera_received = TSignal(dict, name="camera.received")

    def __init__(self):
        self.smblock = None
        self.is_opened = False
        self.rx_count = 0
        self.rx_drop = 0

        # config에서 주입
        self.camera_index = 0       # 웹캠 인덱스 (0=기본)
        self.fps = 30               # 목표 FPS
        self.width = 640            # 캡처 해상도
        self.height = 480

        self._cap = None
        self._running = False

    # 테스트할 일반적인 해상도 목록
    COMMON_RESOLUTIONS = [
        (160, 120), (176, 144), (320, 240), (352, 288),
        (640, 360), (640, 480), (800, 600), (960, 540),
        (1024, 768), (1280, 720), (1280, 960), (1280, 1024),
        (1600, 900), (1600, 1200), (1920, 1080), (2560, 1440),
        (3840, 2160),
    ]

    @staticmethod
    def get_webcam_count(max_check: int = 10) -> int:
        """연결된 웹캠 수 반환"""
        count = 0
        for i in range(max_check):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                count += 1
                cap.release()
            else:
                break
        print(f"[WebcamDriver] Connected webcams: {count}")
        return count

    def _probe_resolutions(self):
        """현재 열린 _cap으로 지원 해상도 탐색 (별도 open 없음)"""
        if not self._cap or not self._cap.isOpened():
            return []

        # 현재 설정 백업
        orig_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        supported = []
        for w, h in self.COMMON_RESOLUTIONS:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            res = (actual_w, actual_h)
            if res not in supported:
                supported.append(res)

        # 원래 해상도 복원
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, orig_w)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, orig_h)

        supported.sort(key=lambda r: r[0] * r[1])
        print(f"[WebcamDriver] Supported resolutions (cam {self.camera_index}):")
        for w, h in supported:
            print(f"  {w}x{h}")
        return supported

    def run(self):
        """메인 루프: 웹캠 열기 → 캡처 루프"""
        print(f"[WebcamDriver] Starting webcam (index={self.camera_index})")
        self._running = True

        while self._running:
            # 카메라 열기
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                print(f"[WebcamDriver] Cannot open webcam {self.camera_index}, retry in 2s")
                time.sleep(2)
                continue

            # 해상도/FPS 설정
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.fps)

            # AutoFocus 활성화
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[WebcamDriver] Opened: {actual_w}x{actual_h}")

            self.is_opened = True
            self.camera_connected.emit({"width": actual_w, "height": actual_h})

            # 캡처 루프
            frame_interval = 1.0 / self.fps if self.fps > 0 else 0.033
            try:
                self._capture_loop(frame_interval)
            except Exception as e:
                import traceback
                print(f"[WebcamDriver] Capture error: {e}")
                traceback.print_exc()
            finally:
                self.is_opened = False
                self._cap.release()
                self._cap = None
                self.camera_disconnected.emit({})
                print("[WebcamDriver] Webcam closed")

            if self._running:
                print("[WebcamDriver] Reconnecting in 2s...")
                time.sleep(2)

    def _capture_loop(self, frame_interval: float):
        """프레임 캡처 루프"""
        log_interval = 100  # 100프레임마다 상태 출력
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                print("[WebcamDriver] Frame read failed, breaking")
                break

            if not self.smblock:
                time.sleep(frame_interval)
                continue

            sm_shape = self.smblock.shape
            target_h, target_w = sm_shape[0], sm_shape[1]
            sm_channels = sm_shape[2] if len(sm_shape) > 2 else 1

            # 웹캠 프레임을 SmBlock shape에 맞게 변환
            if frame.shape[0] != target_h or frame.shape[1] != target_w:
                frame = cv2.resize(frame, (target_w, target_h))

            # 채널 매칭
            if sm_channels == 1 and frame.ndim == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            elif sm_channels == 3 and frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            # SmBlock 할당 + 복사
            index = self.smblock.malloc(frame)
            if index < 0:
                self.rx_drop += 1
                if self.rx_drop % log_interval == 1:
                    print(f"[WebcamDriver] SmBlock full (drop={self.rx_drop})")
                continue

            self.rx_count += 1
            self.camera_received.emit({
                "sm_index": index,
                "trigger_mode": False,
                "rx_sequence": self.rx_count,
                "rx_timestamp": time.time(),
                "rx_count": self.rx_count,
                "rx_drop": self.rx_drop
            })

            if self.rx_count % log_interval == 0:
                print(f"[WebcamDriver] rx={self.rx_count} drop={self.rx_drop} frame={frame.shape}")

    def close(self):
        """종료"""
        self._running = False
        if self._cap and self._cap.isOpened():
            self._cap.release()

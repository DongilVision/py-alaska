# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-07
"""
SimCam — 시뮬레이션 카메라 (이미지 Replay)
==========================================
저장된 이미지를 재생하여 실제 카메라와 100% 동일한 인터페이스를 제공한다.

인터페이스 계약 (imi_cam_dp 동일):
  시그널:  camera.connected / camera.disconnected / camera.received
  SmBlock: alloc → copy → emit (소비자가 mfree)
  DEVICE_PROPERTY: is_connect, fps, exposure, trigger_mode
  RMI: one_shot(), seek(), get_info(), set_session(), pause(),
       set_replay_mode(), set_loop()

config.json 주입:
  smblock       — "smblock:smblock2048"
  replay_path   — 재생 디렉토리 (SaveImage 출력 구조)
  session       — 세션명 ("S001", "" = 최신)
  replay_mode   — "realtime" | "original" | "fast" | "step"
  fps           — realtime 모드 재생 fps (기본 30)
  loop          — False | True | int (반복 횟수)
  start_frame   — 시작 프레임 (0-based, 기본 0)
  end_frame     — 끝 프레임 (-1 = 전체, 기본 -1)

설계서: doc/6020____sim_cam기능설계.txt
"""

import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from py_alaska import task
from py_alaska.core.task_signal_decl import TSignal


@task(name="sim_cam", mode="process", restart=True)
class SimCam:
    """SimCam — 이미지 Replay 카메라.

    DEVICE_PROPERTY는 imi_cam_dp와 동일 구조.
    @resync open/close는 _noop (HW 없음).
    """

    camera_connected = TSignal(dict, name="camera.connected")
    camera_disconnected = TSignal(dict, name="camera.disconnected")
    camera_received = TSignal(dict, name="camera.received")

    DEVICE_PROPERTY = {
        "is_connect:bool=false": {},
        "fps:float=30.0": {
            "setter": "_sim_set_fps",
        },
        "exposure:int=15000": {},
        "trigger_mode:bool=false": {
            "setter": "_sim_set_trigger",
        },
        "@resync": {
            "open": "_noop",
            "close": "_noop",
            "condition": {"Eq": ["is_connect", True]},
            "order": ["trigger_mode", "fps", "exposure"]
        }
    }

    def __init__(self):
        self.rx_count = 0
        self.rx_drop = 0
        self.trigger_source = "software"

        # config.json 주입
        self.replay_path = ""
        self.session = ""
        self.replay_mode = "realtime"
        self.loop = False
        self.start_frame = 0
        self.end_frame = -1

        # 내부 상태
        self._frame_interval = 1.0 / 30.0
        self._trigger_event = None
        self._paused = False
        self._files = []
        self._current_index = 0
        self._seek_index = -1
        self._prev_ts = 0.0
        self._start_time = 0.0
        self._stop_requested = False

    # ═══════════════════════════════════════════════════════════════════════
    # DEVICE_PROPERTY helpers
    # ═══════════════════════════════════════════════════════════════════════
    def _noop(self):
        pass

    def _sim_set_fps(self, value):
        if value > 0:
            self._frame_interval = 1.0 / value
            self.print(f"fps={value:.1f} interval={self._frame_interval*1000:.1f}ms")

    def _sim_set_trigger(self, enabled):
        self._paused = enabled
        if not enabled and self._trigger_event:
            self._trigger_event.set()
        self.print(f"trigger_mode={'ON (paused)' if enabled else 'OFF (playing)'}")

    # ═══════════════════════════════════════════════════════════════════════
    # RMI — 실제 카메라 호환
    # ═══════════════════════════════════════════════════════════════════════
    def one_shot(self, count=1):
        """RMI: trigger 모드에서 N프레임 전진 (기본 1)."""
        if not self.is_connect:
            self.print("WARN one_shot called but not connected")
            return
        if self.trigger_source != "software":
            self.print(f"WARN one_shot: trigger_source='{self.trigger_source}' "
                       "(SimCam ignores, proceeding)")
        if self._trigger_event:
            for _ in range(count):
                self._trigger_event.set()
                # 짧은 대기 — clear 후 다시 set 가능하도록
                time.sleep(0.001)

    # ═══════════════════════════════════════════════════════════════════════
    # RMI — SimCam 전용
    # ═══════════════════════════════════════════════════════════════════════
    def seek(self, frame_index: int):
        """RMI: 지정 프레임으로 이동 (0-based)."""
        if 0 <= frame_index < len(self._files):
            self._seek_index = frame_index
            self.print(f"seek → {frame_index}")

    def get_info(self) -> dict:
        """RMI: 재생 정보 반환."""
        replay_path = Path(self.replay_path)
        sessions = []
        if replay_path.exists():
            for d in sorted(replay_path.rglob("S*")):
                if d.is_dir():
                    sessions.append(d.name)
        return {
            "total": len(self._files),
            "current": self._current_index,
            "session": self.session,
            "sessions": sessions,
            "replay_mode": self.replay_mode,
            "loop": self.loop,
            "fps": self._cache.get("fps", 30.0),
        }

    def set_session(self, name: str):
        """RMI: 세션 전환."""
        self.session = name
        self._stop_requested = True
        if self._trigger_event:
            self._trigger_event.set()
        self.print(f"set_session → {name}")

    def pause(self):
        """RMI: 재생 중지."""
        self._stop_requested = True
        if self._trigger_event:
            self._trigger_event.set()
        self.print("pause requested")

    def set_replay_mode(self, mode: str):
        """RMI: 재생 모드 변경."""
        if mode in ("realtime", "original", "fast", "step"):
            self.replay_mode = mode
            if mode == "step":
                self._paused = True
            self.print(f"replay_mode → {mode}")

    def set_loop(self, value):
        """RMI: 루프 설정 변경."""
        self.loop = value
        self.print(f"loop → {value}")

    # ═══════════════════════════════════════════════════════════════════════
    # 파일 스캔
    # ═══════════════════════════════════════════════════════════════════════
    def _scan_session(self):
        """replay_path 하위 세션 디렉토리 탐색 → 이미지 파일 목록 반환."""
        replay_path = Path(self.replay_path)
        if not replay_path.exists():
            self.print(f"ERROR replay_path not found: {self.replay_path}")
            return []

        # 세션 디렉토리 탐색
        session_dirs = sorted(
            [d for d in replay_path.rglob("S*") if d.is_dir()])
        if not session_dirs:
            self.print(f"ERROR no session directories found in {self.replay_path}")
            return []

        # 세션 선택
        if self.session:
            target = [d for d in session_dirs if d.name == self.session]
            session_dir = target[0] if target else session_dirs[-1]
        else:
            session_dir = session_dirs[-1]

        self.session = session_dir.name
        self.print(f"Session: {session_dir}")

        # 이미지 파일 수집 (정렬)
        exts = ("*.png", "*.bmp", "*.jpg", "*.jpeg", "*.tif", "*.tiff")
        files = []
        for ext in exts:
            files.extend(session_dir.glob(ext))
        files.sort(key=lambda f: f.name)

        # start_frame / end_frame 슬라이싱
        if self.start_frame > 0:
            files = files[self.start_frame:]
        if self.end_frame > 0:
            files = files[:self.end_frame - max(self.start_frame, 0)]

        self.print(f"Found {len(files)} images")
        return files

    # ═══════════════════════════════════════════════════════════════════════
    # 타임스탬프 / 타이밍
    # ═══════════════════════════════════════════════════════════════════════
    def _get_timestamp(self, filepath):
        """파일명에서 원본 타임스탬프 복원, 실패 시 현재 시각."""
        name = filepath.stem
        parts = name.split("_")
        try:
            date_str = parts[2]
            time_str = parts[3]
            ms_str = parts[4]
            dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
            return dt.timestamp() + int(ms_str) / 1000.0
        except (IndexError, ValueError):
            return time.time()

    def _pace(self, frame_idx):
        """재생 모드별 타이밍 제어."""
        if self.replay_mode == "realtime":
            # drift 보정
            elapsed = time.perf_counter() - self._start_time
            expected = (frame_idx + 1) * self._frame_interval
            drift = expected - elapsed
            if drift > 0.001:
                time.sleep(drift)

        elif self.replay_mode == "original":
            ts = self._get_timestamp(self._files[self._current_index])
            if frame_idx > 0 and self._prev_ts > 0:
                dt = ts - self._prev_ts
                if 0 < dt < 10:
                    time.sleep(dt)
            self._prev_ts = ts

        # fast / step: sleep 없음

    # ═══════════════════════════════════════════════════════════════════════
    # Trigger 대기
    # ═══════════════════════════════════════════════════════════════════════
    def _should_wait_trigger(self):
        if self.replay_mode == "step":
            return True
        return self._paused

    def _wait_trigger(self):
        """trigger/one_shot 대기. True=프레임 전진, False=should_stop."""
        while not self.runtime.should_stop() and not self._stop_requested:
            if self._trigger_event.wait(timeout=0.5):
                self._trigger_event.clear()
                return True
        return False

    # ═══════════════════════════════════════════════════════════════════════
    # Signal Emit
    # ═══════════════════════════════════════════════════════════════════════
    def _emit_connected(self):
        self.camera_connected.emit({
            "source": self.runtime.name,
            "mode": "sim",
            "fps": self._cache.get("fps", 30.0)
        })

    def _emit_disconnected(self, reason="end_of_replay"):
        self.camera_disconnected.emit({
            "source": self.runtime.name,
            "reason": reason,
            "captured": self.rx_count,
            "dropped": self.rx_drop
        })

    # ═══════════════════════════════════════════════════════════════════════
    # Main Loop
    # ═══════════════════════════════════════════════════════════════════════
    def run(self):
        self._trigger_event = threading.Event()

        # step 모드 → 강제 trigger
        if self.replay_mode == "step":
            self._paused = True

        while not self.runtime.should_stop():
            self._stop_requested = False

            # 1. 파일 스캔
            self._files = self._scan_session()
            if not self._files:
                self.print("ERROR: no images found, retry in 3s")
                time.sleep(3)
                continue

            # 2. FPS 초기화
            self._frame_interval = 1.0 / max(
                self._cache.get("fps", 30.0), 0.1)

            # 3. 연결 시그널
            self.rx_count = 0
            self.rx_drop = 0
            self.is_connect = True
            self._emit_connected()

            # 4. 재생 루프
            loop_count = 0
            while not self.runtime.should_stop() and not self._stop_requested:
                self._start_time = time.perf_counter()
                self._prev_ts = 0.0

                for i in range(len(self._files)):
                    if self.runtime.should_stop() or self._stop_requested:
                        break

                    # seek 처리
                    if self._seek_index >= 0:
                        i = self._seek_index
                        self._seek_index = -1

                    self._current_index = i

                    # trigger 대기
                    if self._should_wait_trigger():
                        if not self._wait_trigger():
                            break

                    # 이미지 로드
                    filepath = self._files[i]
                    image = cv2.imread(str(filepath), cv2.IMREAD_UNCHANGED)
                    if image is None:
                        self.rx_drop += 1
                        self.print(f"WARN imread failed: {filepath.name}")
                        continue

                    # SmBlock 할당
                    index = self.smblock.alloc()
                    if index == -1:
                        self.rx_drop += 1
                        continue

                    # SmBlock에 복사
                    dst = self.smblock.get_buffer(index)
                    try:
                        dst[:] = image
                    except ValueError:
                        self.smblock.mfree(index)
                        self.rx_drop += 1
                        self.print(f"WARN shape mismatch: "
                                   f"image={image.shape} smblock={dst.shape}")
                        continue

                    # 시그널 발신
                    self.rx_count += 1
                    try:
                        self.camera_received.emit({
                            "sm_index": index,
                            "trigger_mode": self._cache.get(
                                "trigger_mode", False),
                            "rx_sequence": self.rx_count,
                            "rx_timestamp": self._get_timestamp(filepath),
                            "rx_count": self.rx_count,
                            "rx_drop": self.rx_drop,
                        })
                    except Exception:
                        self.smblock.mfree(index)

                    # 타이밍 제어
                    if not self._should_wait_trigger():
                        self._pace(i)

                # 루프 판정
                loop_count += 1
                if not self._should_loop(loop_count):
                    break

            # 5. 종료
            self.is_connect = False
            self._emit_disconnected()

    def _should_loop(self, loop_count):
        """루프 조건 판정."""
        if self._stop_requested:
            return False
        if self.loop is True:
            return True
        if isinstance(self.loop, int) and self.loop > 0:
            return loop_count < self.loop
        return False

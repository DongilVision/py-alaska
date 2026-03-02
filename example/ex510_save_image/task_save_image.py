# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
# Project : ALASKA 2.0 — Multiprocess Task Framework
# Date    : 2026-03-02
"""
SaveImage — 이미지 저장 워커 (process 모드)
===========================================
카메라 프레임을 디스크에 저장하는 백그라운드 프로세스.

Classes:
    SaveImage   @task(mode="process") — 이미지 저장 워커

주요 기능:
    run()               — 메인 루프 (single-slot → rate limit → 병렬 쓰기)
    on_camera_received  — 프레임 수신 → pending slot 교체 + mfree
    start_saving        — RMI: 세션 디렉토리(S001) 생성 + 저장 시작
    stop_saving         — RMI: 저장 중지 + 세션 닫기
    get_status          — RMI: 현재 상태 조회

파이프라인:
    camera.received → copy → _pending_frame 교체 → mfree
    main loop → pending pickup → max_fps check → executor.submit(_write_image)
    _write_image → cv2.imwrite → saved.emit (워커 스레드)

config.json 주입:
    smblock       — 공유 메모리 블록
    save_path     — 저장 루트 경로 (기본: D:/images)
    retain_days   — 보존 일수 (0=무제한, 기본: 30)
    image_format  — png / bmp / jpg (기본: png)
    max_fps       — 초당 최대 저장 수 (기본: 10)

주의:
    - Task 이름 "saver" (언더스코어 금지 — 시그널 파서 매칭 실패)
    - threading 객체는 pickle 불가 → __init__에서 None, run()에서 생성
    - mfree는 saver가 단독 담당 (viewer는 copy만)
"""

import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import cv2
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait

from py_alaska import task


@task(name="saver", mode="process")
class SaveImage:
    """이미지 저장 워커 (process 모드)."""

    def __init__(self):
        # config.json 주입 속성
        self.save_path = "D:/images"
        self.retain_days = 30
        self.image_format = "png"
        self.max_fps = 10

        # 세션 상태
        self._saving = False
        self._base_dir = None        # save_path/YYYY/MM/DD
        self._session_dir = None     # save_path/YYYY/MM/DD/S001
        self._session_num = 0
        self._session_seq = 0
        self._dropped_count = 0

        # 인코딩
        self._ext = ".png"
        self._encode_params = []

        # threading 객체 — pickle 불가 → run()에서 생성
        self._pending_lock = None
        self._pending_frame = None   # (image, meta) or None
        self._pending_event = None
        self._executor = None
        self._emit_lock = None
        self._write_futures = []

        # 30분 세션 타임아웃
        self._session_timeout = 30 * 60
        self._last_activity_time = None

    # ═══════════════════════════════════════════════════════════════════════
    # Run loop
    # ═══════════════════════════════════════════════════════════════════════
    def run(self):
        """메인 루프: pending slot → rate limit → 병렬 쓰기."""
        self._pending_lock = threading.Lock()
        self._pending_event = threading.Event()
        self._emit_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._write_futures = []
        self._min_interval = 1.0 / self.max_fps if self.max_fps > 0 else 0
        self._last_save_time = 0.0
        self._init_encode_params()
        self.print(f"ready: save_path={self.save_path}, format={self.image_format}, "
                   f"retain={self.retain_days}d, workers=4, max_fps={self.max_fps}")

        while not self.runtime.should_stop():
            if not self._pending_event.wait(timeout=1.0):
                if (self._base_dir and self._last_activity_time and
                        time.time() - self._last_activity_time > self._session_timeout):
                    self.print("session timeout (30min idle)")
                    self._session_close()
                continue

            self._pending_event.clear()

            with self._pending_lock:
                frame_data = self._pending_frame
                self._pending_frame = None

            if frame_data is None or self._session_dir is None:
                continue

            if not self._check_disk_space():
                continue

            image, meta = frame_data

            # max_fps 제한 — dropped 카운트는 saved 시그널에 포함
            now = time.time()
            if self._min_interval > 0 and (now - self._last_save_time) < self._min_interval:
                self._dropped_count += 1
                continue

            self._session_seq += 1
            self._last_activity_time = now
            self._last_save_time = now
            filename = self._make_filename(meta)
            filepath = str(self._session_dir / filename)
            seq = self._session_seq
            dropped = self._dropped_count

            future = self._executor.submit(
                self._write_image, image, filepath, seq, dropped)
            self._write_futures.append(future)

            # 완료된 future 정리
            self._write_futures = [f for f in self._write_futures if not f.done()]

        self._executor.shutdown(wait=True)

    def _write_image(self, image, filepath, seq, dropped):
        """디스크 기록 (ThreadPoolExecutor 워커에서 실행)."""
        try:
            ok = cv2.imwrite(filepath, image, self._encode_params)
            if not ok:
                self.print(f"WARN imwrite failed: {filepath}")
                return
            with self._emit_lock:
                self.signal.saver.saved.emit({
                    "path": filepath,
                    "seq": seq,
                    "dropped": dropped,
                })
        except Exception as e:
            self.exception(e)

    # ═══════════════════════════════════════════════════════════════════════
    # Signal handlers
    # ═══════════════════════════════════════════════════════════════════════
    def on_camera_connected(self, signal):
        """카메라 연결 → 날짜 디렉토리 준비."""
        self._prepare_base_dir()

    def on_camera_disconnected(self, signal):
        """카메라 해제 → 세션 닫기 + 만료 정리."""
        self._session_close()

    def on_camera_received(self, signal):
        """프레임 수신 → pending slot 교체 + mfree. 드롭 판단은 main loop."""
        data = signal.data
        sm_index = data["sm_index"]
        try:
            if not self._saving or self._session_dir is None or self._base_dir is None:
                return
            if self._pending_event is None:
                return
            image = self.smblock.get_buffer(sm_index).copy()
            with self._pending_lock:
                self._pending_frame = (image, data)
            self._pending_event.set()
        finally:
            self.smblock.mfree(sm_index)

    # ═══════════════════════════════════════════════════════════════════════
    # RMI (SaveImageUI에서 호출)
    # ═══════════════════════════════════════════════════════════════════════
    def start_saving(self):
        """세션 디렉토리(S001) 생성 + 저장 시작."""
        if self._base_dir is None:
            self._prepare_base_dir()

        # S??? 디렉토리 스캔 → 다음 번호
        max_num = 0
        try:
            for d in self._base_dir.iterdir():
                if d.is_dir() and d.name.startswith("S") and len(d.name) == 4:
                    try:
                        max_num = max(max_num, int(d.name[1:]))
                    except ValueError:
                        pass
        except OSError:
            pass

        self._session_num = max_num + 1
        self._session_dir = self._base_dir / f"S{self._session_num:03d}"
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._saving = True
        self._session_seq = 0
        self._dropped_count = 0

        self.signal.saver.session.emit({
            "action": "open",
            "path": str(self._session_dir),
            "continued": 0,
        })
        self.print(f"saving started: {self._session_dir}")

    def stop_saving(self):
        """저장 중지 + 세션 닫기."""
        self._saving = False
        self.signal.saver.session.emit({
            "action": "close",
            "saved_count": self._session_seq,
            "dropped_count": self._dropped_count,
        })
        self.print(f"saving stopped (saved={self._session_seq})")
        self._session_dir = None

    def get_status(self):
        """현재 상태 조회."""
        return {
            "saving": self._saving,
            "session_dir": str(self._session_dir) if self._session_dir else None,
            "session_seq": self._session_seq,
            "pending": self._pending_frame is not None,
            "dropped_count": self._dropped_count,
            "image_format": self.image_format,
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Session management
    # ═══════════════════════════════════════════════════════════════════════
    def _prepare_base_dir(self):
        """날짜 기반 베이스 디렉토리 준비 (save_path/YYYY/MM/DD)."""
        now = datetime.now()
        self._base_dir = (
            Path(self.save_path)
            / f"{now.year}" / f"{now.month:02d}" / f"{now.day:02d}"
        )
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._last_activity_time = time.time()
        self.print(f"base dir: {self._base_dir}")

    def _session_close(self):
        """활성 세션 닫기 → flush → futures 대기 → 만료 정리."""
        if self._base_dir is None:
            return

        if self._session_dir is not None:
            self._saving = False
            self._flush_pending()

            if self._write_futures:
                futures_wait(self._write_futures)
                self._write_futures.clear()

            self.signal.saver.session.emit({
                "action": "close",
                "saved_count": self._session_seq,
                "dropped_count": self._dropped_count,
            })
            self.print(f"session close: saved={self._session_seq}, "
                       f"dropped={self._dropped_count}")
            self._session_dir = None

        self._cleanup_expired()
        self._base_dir = None
        self._last_activity_time = None

    def _flush_pending(self):
        """pending slot 잔여 프레임 → executor 제출."""
        if self._pending_lock is None:
            return
        with self._pending_lock:
            frame_data = self._pending_frame
            self._pending_frame = None

        if frame_data is None or self._session_dir is None:
            return

        image, meta = frame_data
        self._session_seq += 1
        filename = self._make_filename(meta)
        filepath = str(self._session_dir / filename)
        seq = self._session_seq
        dropped = self._dropped_count

        if self._executor:
            future = self._executor.submit(
                self._write_image, image, filepath, seq, dropped)
            self._write_futures.append(future)

    # ═══════════════════════════════════════════════════════════════════════
    # File naming & encoding
    # ═══════════════════════════════════════════════════════════════════════
    def _init_encode_params(self):
        """이미지 포맷별 인코딩 파라미터 설정."""
        fmt = self.image_format.lower()
        if fmt == "png":
            self._encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 1]
            self._ext = ".png"
        elif fmt == "bmp":
            self._encode_params = []
            self._ext = ".bmp"
        elif fmt in ("jpg", "jpeg"):
            self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, 95]
            self._ext = ".jpg"
        else:
            self.print(f"WARN unknown format '{fmt}', fallback to png")
            self._encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 1]
            self._ext = ".png"

    def _make_filename(self, meta):
        """타임스탬프 기반 파일명 생성: img_{seq}_{datetime}_{ms}.{ext}"""
        ts = meta.get("rx_timestamp", time.time())
        dt = datetime.fromtimestamp(ts)
        ms = int(dt.microsecond / 1000)
        return (f"img_{self._session_seq:04d}_"
                f"{dt.strftime('%Y%m%d_%H%M%S')}_{ms:03d}{self._ext}")

    # ═══════════════════════════════════════════════════════════════════════
    # Disk & retention
    # ═══════════════════════════════════════════════════════════════════════
    def _check_disk_space(self):
        """디스크 여유 공간 확인 (100MB 미만 시 False)."""
        try:
            usage = shutil.disk_usage(str(self.save_path))
            if usage.free < 100 * 1024 * 1024:
                self.print(f"WARN disk low: {usage.free // (1024 * 1024)}MB free")
                return False
        except OSError:
            pass
        return True

    def _cleanup_expired(self):
        """보존 기간 초과 날짜 디렉토리 삭제."""
        if self.retain_days <= 0:
            return

        cutoff = datetime.now() - timedelta(days=self.retain_days)
        base = Path(self.save_path)
        if not base.exists():
            return

        try:
            year_dirs = sorted(base.iterdir())
        except OSError:
            return

        for year_dir in year_dirs:
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            try:
                month_dirs = sorted(year_dir.iterdir())
            except OSError:
                continue
            for month_dir in month_dirs:
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                try:
                    day_dirs = sorted(month_dir.iterdir())
                except OSError:
                    continue
                for day_dir in day_dirs:
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue
                    try:
                        dir_date = datetime(
                            int(year_dir.name),
                            int(month_dir.name),
                            int(day_dir.name))
                        if dir_date < cutoff:
                            shutil.rmtree(day_dir)
                            self.print(f"expired: {day_dir}")
                    except (ValueError, OSError) as e:
                        self.print(f"cleanup error: {day_dir}: {e}")

                try:
                    if month_dir.exists() and not any(month_dir.iterdir()):
                        month_dir.rmdir()
                except OSError:
                    pass

            try:
                if year_dir.exists() and not any(year_dir.iterdir()):
                    year_dir.rmdir()
            except OSError:
                pass

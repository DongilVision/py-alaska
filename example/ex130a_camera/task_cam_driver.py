# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""
IMI Camera Driver (DEVICE_PROPERTY 버전)
========================================
- CamProperty 제거 → DEVICE_PROPERTY 선언형으로 전환
- _lazy_reset() 제거 → @resync가 자동 처리
- is_opened 제거 → is_connect (DeviceProperty) 사용

변경 요약:
  Before (CamProperty)           After (DEVICE_PROPERTY)
  ─────────────────────────────────────────────────────
  fps = CamProperty(...)         "fps:float=900.0": {setter, getter}
  _lazy_updates + _lazy_reset    @resync 자동 처리
  is_opened (수동)               is_connect (DeviceProperty)
"""

import ctypes
import multiprocessing
import queue
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from py_alaska import task

try:
    from py_alaska import SmBlock
    from py_alaska import gconfig
    from py_alaska.drives.imi.Neptune_API import *
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from py_alaska import SmBlock
    from py_alaska import gconfig
    from py_alaska.drives.imi.Neptune_API import *

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════
AUTO_SELECT_MAC = "ff:ff:ff:ff:ff:ff"
HEARTBEAT_TIME = 100
INITIAL_WAIT = 1
QUEUE_TIMEOUT = 0.3

TAG = "[imi_cam_dp]"  # staticmethod용 (self.print 불가)


@dataclass
class FrameInfo:
    sm_index: int
    trigger_mode: bool
    rx_sequence: int
    rx_timestamp: float
    rx_count: int
    rx_drop: int


# ═══════════════════════════════════════════════════════════════════════════════
# IMI Camera Driver (DEVICE_PROPERTY)
# ═══════════════════════════════════════════════════════════════════════════════
@task(name="imi_cam_dp", mode="process", restart=True)
class imi_cam_dp:
    """IMI Camera Driver using DEVICE_PROPERTY.

    is_connect: 연결 플래그 (setter 없음 — run() 루프가 관리)
    fps, exposure, trigger_mode: HW 속성
      - 비연결 상태에서 값 설정 → 캐시만 저장 (opstate 미충족)
      - is_connect=True 시 @resync → _session_open → 순서대로 HW 적용 → _session_close
    """

    # ─── DEVICE_PROPERTY 선언 ────────────────────────────────────────────
    DEVICE_PROPERTY = {
        # is_connect: 연결 상태 플래그 (setter 없음 — run()이 직접 관리)
        "is_connect:bool=false": {},

        # HW 속성: setter만 (getter는 캐시 의존, 필요 시 read_all() 사용)
        "fps:float=900.0": {
            "setter": "_hw_set_fps",
        },
        "exposure:int=15000": {
            "setter": "_hw_set_exposure",
        },
        "trigger_mode:bool=false": {
            "setter": "_hw_set_trigger",
        },

        # @resync: is_connect=True 시 일괄 적용
        "@resync": {
            "open": "_session_open",
            "close": "_session_close",
            "condition": {"Eq": ["is_connect", True]},
            "order": ["trigger_mode", "fps", "exposure"]
        }
    }

    # ─── Class Variables ─────────────────────────────────────────────────
    DriverInit = False
    _last_mac_list: list = []
    _last_discovery_result: str = ""

    # ─── Init ────────────────────────────────────────────────────────────
    def __init__(self):
        self.rx_cmdq = None
        self.rx_drop = 0
        self.rx_count = 0
        self.handle = None
        self.trigger_source = "software"
        # 콜백 캐시 안전 기본값 (연결 전 콜백 방어)
        self._dst_addrs = None
        self._emit_received = None
        self._frame_payload = None
        self._frame_size = 0

    # ═══════════════════════════════════════════════════════════════════════
    # Resync Session (acquisition stop/start)
    # ═══════════════════════════════════════════════════════════════════════
    def _session_open(self):
        """@resync open: acquisition 정지"""
        if self.handle:
            ntcSetAcquisition(self.handle,
                              ENeptuneBoolean.NEPTUNE_BOOL_FALSE.value)
            self.print("Session open (acquisition stopped)")

    def _session_close(self):
        """@resync close: acquisition 재개"""
        if self.handle:
            ntcSetAcquisition(self.handle,
                              ENeptuneBoolean.NEPTUNE_BOOL_TRUE.value)
            self.print("Session close (acquisition started)")

    # ═══════════════════════════════════════════════════════════════════════
    # HW Setters (DEVICE_PROPERTY용)
    # ═══════════════════════════════════════════════════════════════════════
    def _hw_set_fps(self, value):
        emFPS = ctypes.c_int32(ENeptuneFrameRate.FPS_VALUE.value)
        dbFPS = ctypes.c_double(value)
        err = ntcSetFrameRate(self.handle, emFPS.value, dbFPS.value)
        if err != 0:
            self.print(f"ERROR ntcSetFrameRate failed: fps={value}, err={err}")
        else:
            self.print(f"FPS set to {value}")

    def _hw_set_exposure(self, value):
        pui = ctypes.c_uint32(value)
        if ntcSetExposureTime(self.handle, pui) != 0:
            self.print("ERROR ntcSetExposureTime failed")
        else:
            self.print(f"Exposure set to {value}")

    def _hw_set_trigger(self, enabled):
        st_trigger = NEPTUNE_TRIGGER()
        if self.trigger_source == "hardware":
            st_trigger.Source = ENeptuneTriggerSource.NEPTUNE_TRIGGER_SOURCE_LINE1.value
        else:
            st_trigger.Source = ENeptuneTriggerSource.NEPTUNE_TRIGGER_SOURCE_SW.value
        st_trigger.Mode = ENeptuneTriggerMode.NEPTUNE_TRIGGER_MODE_0.value
        st_trigger.Polarity = ENeptunePolarity.NEPTUNE_POLARITY_FALLINGEDGE.value
        st_trigger.OnOff = (ENeptuneBoolean.NEPTUNE_BOOL_TRUE.value
                            if enabled
                            else ENeptuneBoolean.NEPTUNE_BOOL_FALSE.value)

        if ntcSetTrigger(self.handle, st_trigger) != ENeptuneError.NEPTUNE_ERR_Success.value:
            self.print("ERROR ntcSetTrigger failed")
        else:
            self.print(f"Trigger set to {enabled}")

    # ═══════════════════════════════════════════════════════════════════════
    # Connection Lifecycle
    # ═══════════════════════════════════════════════════════════════════════
    def re_connect(self):
        """카메라 연결 시도. 성공 시 is_connect=True → @resync 트리거."""
        if not imi_cam_dp.DriverInit:
            if ntcInit() != ENeptuneError.NEPTUNE_ERR_Success.value:
                self.print("ERROR Driver initialization failed")
                return False
            imi_cam_dp.DriverInit = True
            self.print("Driver initialized")

        if self.is_connect:
            return True

        if self.handle:
            ntcClose(self.handle)
        self.handle = ctypes.c_void_p(0)
        found_mac = self.discovery(self.mac_address)
        if found_mac is None:
            return False
        err = ntcOpen(bytes(found_mac, encoding='utf-8'),
                      ctypes.byref(self.handle))
        if err != ENeptuneError.NEPTUNE_ERR_Success.value:
            self.print(f"ERROR ntcOpen failed: {self.mac_address} (err={err})")
            return False

        if ntcSetHeartbeatTime(self.handle, HEARTBEAT_TIME) != ENeptuneError.NEPTUNE_ERR_Success.value:
            self.print("ERROR ntcSetHeartbeatTime failed")
            return False

        # Callback setup
        self.frameCallBack = ctypes.CFUNCTYPE(
            None, NEPTUNE_IMAGE, ctypes.c_void_p)(self.RecvFrameCallBack)
        ntcSetFrameCallback(self.handle, self.frameCallBack, self.handle)

        self.callback_drop_func = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p)(self.RecvFrameDropCallBack)
        ntcSetFrameDropCallback(self.handle, self.callback_drop_func, self.handle)

        self.callback_device_check_func = ctypes.CFUNCTYPE(
            None, ctypes.c_int, ctypes.c_void_p)(self.RecvDeviceCheckCallBack)
        ntcSetDeviceCheckCallback(self.callback_device_check_func, self.handle)

        self.func_unplug = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p)(self.RecvUnPlugCallBack)
        ntcSetUnplugCallback(self.handle, self.func_unplug, self.handle)

        self.func_timeout = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p)(self.RecvTimeoutCallBack)
        ntcSetRecvTimeoutCallback(self.handle, self.func_timeout, self.handle)

        # Acquisition start (initial)
        for state in [False, True]:
            ntcSetAcquisition(
                self.handle,
                ENeptuneBoolean.NEPTUNE_BOOL_TRUE.value
                if state else ENeptuneBoolean.NEPTUNE_BOOL_FALSE.value)

        # ★ is_connect=True → DeviceProperty 캐시 업데이트 + @resync 자동 트리거
        #   → _session_open (acq stop) → trigger_mode, fps, exposure 순서로 HW 적용
        #   → _session_close (acq start)
        #   기존 _lazy_reset()을 완전히 대체
        self.is_connect = True
        self._warm_callback_cache()
        self.print("Connected")
        self._emit_connected()
        return True

    def _warm_callback_cache(self):
        """콜백 핫 패스용 캐시 프리워밍 (연결 시 1회)"""
        # ① dst 주소 테이블: get_buffer(i).ctypes.data를 매 프레임 호출 제거
        n = self.smblock.maxsize
        self._dst_addrs = [self.smblock.get_buffer(i).ctypes.data for i in range(n)]
        # ② signal emit 함수 직접 참조: getattr + 속성 체인 제거
        self._emit_received = (self.signal.camera.received.emit
                               if getattr(self, 'signal', None) else None)
        # ③ 재사용 dict: 매 프레임 dict 생성 + key 해싱 제거
        self._frame_payload = {
            "sm_index": 0, "trigger_mode": False,
            "rx_sequence": 0, "rx_timestamp": 0,
            "rx_count": 0, "rx_drop": 0,
        }
        # ④ 프레임 크기 캐시 (첫 프레임에서 설정)
        self._frame_size = 0

    def _invalidate_callback_cache(self):
        """연결 해제 시 콜백 캐시 무효화 — 콜백이 stale 참조 사용 방지"""
        self._dst_addrs = None
        self._emit_received = None
        self._frame_size = 0

    def close(self):
        self.print(f"Close called, connected={self.is_connect}")
        if not self.is_connect:
            return
        try:
            self.put_cmd("close", "user_close")
            ntcClose(self.handle)
            self.print("Closed")
        except Exception as e:
            self.print(f"ERROR during close: {e}")
            self.put_cmd("disconnect", "close_error")

    # ═══════════════════════════════════════════════════════════════════════
    # Signal Emit
    # ═══════════════════════════════════════════════════════════════════════
    def _emit_connected(self):
        if getattr(self, 'signal', None):
            self.signal.camera.connected.emit({
                "source": self.runtime.name,
                "mode": "real",
                "fps": self._cache.get("fps", 900.0)
            })

    def _emit_disconnected(self, reason="stopped"):
        if getattr(self, 'signal', None):
            self.signal.camera.disconnected.emit({
                "source": self.runtime.name,
                "reason": reason,
                "captured": self.rx_count,
                "dropped": self.rx_drop
            })

    # ═══════════════════════════════════════════════════════════════════════
    # Task Loop
    # ═══════════════════════════════════════════════════════════════════════
    def put_cmd(self, action, source):
        if self.rx_cmdq is not None:
            self.rx_cmdq.put({"action": action, "source": source})

    def run(self):
        self.rx_cmdq = multiprocessing.Queue()
        self.handle = ctypes.c_void_p(0)
        self.put_cmd("connect", "init")
        disconnect_counter = 0

        while not self.runtime.should_stop():
            try:
                cmd = self.rx_cmdq.get(timeout=QUEUE_TIMEOUT)
                action = cmd["action"]
                source = cmd["source"]
                self.print(f"cmd: {action} (from {source})")

                if action == "close":
                    self._invalidate_callback_cache()
                    self._emit_disconnected(f"close:{source}")
                    self.is_connect = False
                    break
                elif action == "connect":
                    self.re_connect()
                elif action == "disconnect":
                    self._invalidate_callback_cache()
                    self._emit_disconnected(f"disconnect:{source}")
                    self.is_connect = False
            except queue.Empty:
                pass

            # Auto-reconnect
            if self.is_connect:
                disconnect_counter = 0
            else:
                disconnect_counter += 1
                wait_count = int(INITIAL_WAIT / QUEUE_TIMEOUT)
                log_interval = int(10 / QUEUE_TIMEOUT)
                if disconnect_counter >= wait_count:
                    if (disconnect_counter - wait_count) % log_interval == 0:
                        elapsed = int(disconnect_counter * QUEUE_TIMEOUT)
                        self.print(f"reconnecting... ({elapsed}s)")
                    self.re_connect()

        # 종료 정리: 콜백 캐시 무효화 → 카메라 닫기 → SDK 해제
        self._invalidate_callback_cache()
        if self.handle and self.is_connect:
            ntcSetAcquisition(self.handle,
                              ENeptuneBoolean.NEPTUNE_BOOL_FALSE.value)
            ntcClose(self.handle)
            self.handle = None
        self.is_connect = False
        self._emit_disconnected("end_of_run")
        self.print("run stopped")

    # ═══════════════════════════════════════════════════════════════════════
    # Hardware Callbacks
    # ═══════════════════════════════════════════════════════════════════════
    def RecvDeviceCheckCallBack(self, state, pContext=None):
        self.print(f"Device {'added' if state == 0 else 'removed'}")
        if state == 0:
            self.put_cmd("connect", "device_added")
        else:
            self.put_cmd("disconnect", "device_removed")

    def RecvUnPlugCallBack(self, _=None):
        self.put_cmd("disconnect", "unplug")

    def RecvTimeoutCallBack(self, _=None):
        self.print("WARN Frame timeout")

    def RecvFrameCallBack(self, pImage, pContext=None):
        self.rx_count += 1

        # 캐시 미초기화 또는 SmBlock 없음 → 무시
        if self._dst_addrs is None or self.smblock is None:
            return

        index = self.smblock.alloc()
        if index == -1:
            self.rx_drop += 1
            return

        try:
            # ① 프레임 크기 캐시 (첫 프레임 1회만 ctypes 접근)
            sz = self._frame_size
            if not sz:
                sz = pImage.uiSize
                self._frame_size = sz

            # ② Raw memcpy: 프리캐시 주소 + 직접 memmove
            ctypes.memmove(
                self._dst_addrs[index],
                ctypes.cast(pImage.pData, ctypes.c_void_p).value,
                sz)

            # ③ 프리캐시 emit + dict 재사용
            emit = self._emit_received
            if emit:
                d = self._frame_payload
                d["sm_index"] = index
                d["rx_sequence"] = self.rx_count
                d["rx_timestamp"] = pImage.uiTimestamp
                d["rx_count"] = self.rx_count
                d["rx_drop"] = self.rx_drop
                emit(d)
            else:
                self.smblock.mfree(index)
        except Exception as e:
            # emit 실패 (뷰어 다운 등) → SmBlock 슬롯 직접 회수
            try:
                self.smblock.mfree(index)
            except Exception:
                pass

    def RecvFrameDropCallBack(self, _=None):
        self.rx_drop += 1

    # ═══════════════════════════════════════════════════════════════════════
    # Utility
    # ═══════════════════════════════════════════════════════════════════════
    def one_shot(self):
        if not self.is_connect:
            self.print("WARN one_shot called but not connected")
            return
        if self.trigger_source != "software":
            self.print("WARN one_shot: trigger_source is not 'software'")
            return
        err = ntcRunSWTrigger(self.handle)
        if err != ENeptuneError.NEPTUNE_ERR_Success.value:
            self.print(f"ERROR ntcRunSWTrigger failed (err={err})")

    def acquisition(self, enable):
        ntcSetAcquisition(
            self.handle,
            ENeptuneBoolean.NEPTUNE_BOOL_TRUE.value
            if enable else ENeptuneBoolean.NEPTUNE_BOOL_FALSE.value)

    def clear_counters(self):
        self.rx_count = 0
        self.rx_drop = 0

    def discovery(self, target_mac=None):
        mac_list = self.get_mac_list(silent=True)
        self.print(f"find camera count={len(mac_list)}")
        if not mac_list:
            return None

        mac_list_lower = [m.lower() for m in mac_list]
        target_lower = target_mac.lower() if target_mac else None

        if target_lower is None or target_lower == AUTO_SELECT_MAC:
            if len(mac_list) == 1:
                self._log_discovery_table(mac_list, mac_list[0], "auto-select")
                return mac_list[0]
            else:
                self._log_discovery_table(mac_list, None, "ERROR: mac_address required")
                return None

        if target_lower in mac_list_lower:
            idx = mac_list_lower.index(target_lower)
            self._log_discovery_table(mac_list, mac_list[idx], "matched")
            return mac_list[idx]

        self._log_discovery_table(mac_list, target_mac, "NOT FOUND")
        return None

    def _log_discovery_table(self, mac_list, result, status):
        key = f"{mac_list}|{result}|{status}"
        if key == imi_cam_dp._last_discovery_result:
            return
        imi_cam_dp._last_discovery_result = key
        self.print(f"Discovery: {len(mac_list)} camera(s), target={result}, status={status}")

    @staticmethod
    def get_mac_list(silent=False):
        numberOfCamera = ctypes.c_uint32(0)
        err = ntcGetCameraCount(ctypes.pointer(numberOfCamera))
        if err != ENeptuneError.NEPTUNE_ERR_Success.value or numberOfCamera.value == 0:
            return []

        cam_count = numberOfCamera.value
        info = (NEPTUNE_CAM_INFO * cam_count)()
        err = ntcGetCameraInfo(info, cam_count)
        if err != ENeptuneError.NEPTUNE_ERR_Success.value:
            return []

        mac_list = [info[i].strMAC.decode('utf-8') for i in range(cam_count)]
        if mac_list != imi_cam_dp._last_mac_list:
            imi_cam_dp._last_mac_list = mac_list[:]
            if not silent:
                print(f"{TAG} Found {cam_count} camera(s): {mac_list}")
        return mac_list

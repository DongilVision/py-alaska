# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
"""JoyStick Task - HID 게임패드 → signal 발행
   signal.jog.connect : bool          연결 상태
   signal.jog.pos     : {x,y,z,a,b,c} 6축 좌표
   signal.jog.shot    : int           카메라 샷 카운트
   signal.jog.inc     : float         증분 선택값 (0.1, 1, 5, 10)
   signal.jog.raw     : str           원시 HID 바이트 변화
"""
import ctypes, time
from ctypes import wintypes
from py_alaska import task

# ── ctypes 구조체 ──

class _BtDevInfo(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("Address", ctypes.c_ulonglong),
        ("ulClassofDevice", ctypes.c_ulong),
        ("fConnected", wintypes.BOOL), ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", ctypes.c_ushort * 8), ("stLastUsed", ctypes.c_ushort * 8),
        ("szName", ctypes.c_wchar * 248)]

class _BtSearchParams(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong),
        ("fReturnAuthenticated", wintypes.BOOL), ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL), ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL), ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wintypes.HANDLE)]

_HID_GUID = (ctypes.c_ubyte * 16)(
    0x24,0x11,0x00,0x00, 0x00,0x00, 0x00,0x10,
    0x80,0x00,0x00,0x80, 0x5F,0x9B,0x34,0xFB)

_INC_LIST = [0.1, 1.0, 5.0, 10.0]
_DEADZONE = 0.3


@task(name="JoyStickTask", mode="process")
class JoyStickTask:
    """BT HID 게임패드 → jog signal 발행"""

    def __init__(self):
        self._bt = self._hid = self._idle = None
        self._x = self._y = self._z = self._a = self._b = self._c = 0.0
        self._shot_count = 0
        self._inc_idx = 0
        self._prev_dz = 0
        self._prev_b1 = 0
        self._prev_b2 = 0
        self._last_t = 0.0
        # BT DLL
        try:
            bt = ctypes.windll.LoadLibrary("bthprops.cpl")
            bt.BluetoothFindFirstDevice.restype = wintypes.HANDLE
            bt.BluetoothFindNextDevice.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
            bt.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]
            self._bt = bt
        except OSError: pass

    def run(self):
        self.signal.jog.inc.emit(_INC_LIST[self._inc_idx])
        self.signal.jog.connect.emit(False)

        while self.running:
            if self._try_connect():
                continue
            if self._activate_bt():
                time.sleep(2)
                if self._try_connect():
                    continue
            time.sleep(2)

    # ── 헬퍼 ──

    def _try_connect(self):
        """HID open → read loop → close. 연결 성공 시 True."""
        if not self._open_hid():
            return False
        self.signal.jog.connect.emit(True)
        self._read_loop()
        self.signal.jog.connect.emit(False)
        return True

    def _emit_pos(self):
        """현재 6축 좌표 signal 발행."""
        self.signal.jog.pos.emit({
            "x": round(self._x, 2), "y": round(self._y, 2),
            "z": round(self._z, 2), "a": round(self._a, 2),
            "b": round(self._b, 2), "c": round(self._c, 2),
        })

    def _change_inc(self, delta):
        """증분 인덱스 변경 (+1/-1) 후 signal 발행."""
        self._inc_idx = max(0, min(self._inc_idx + delta, len(_INC_LIST) - 1))
        self.signal.jog.inc.emit(_INC_LIST[self._inc_idx])

    # ── signal 수신 ──

    def on_jog_set_inc(self, signal):
        """UI 클릭 → 증분 설정 후 확인 응답"""
        val = signal.data
        if val in _INC_LIST:
            self._inc_idx = _INC_LIST.index(val)
            self.signal.jog.inc.emit(_INC_LIST[self._inc_idx])

    # ── HID ──

    def _open_hid(self):
        try: import hid
        except ImportError: return False
        for d in hid.enumerate():
            if d.get('usage_page') != 0x01 or d.get('usage') not in (0x05, 0x04):
                continue
            try:
                h = hid.device(); h.open_path(d['path'])
                self._hid, self._idle = h, None
                self._last_t = time.time()
                print(f"  [HID] {d.get('product_string') or '?'}", flush=True)
                return True
            except Exception: pass
        return False

    def _read_loop(self):
        try:
            while self.running:
                try: data = self._hid.read(64)
                except Exception: return
                if not data: return
                if self._idle is None:
                    self._idle = list(data)
                    continue
                self._process(data)
        finally:
            if self._hid:
                try: self._hid.close()
                except Exception: pass
                self._hid = None

    def _process(self, data):
        idle = self._idle
        inc = _INC_LIST[self._inc_idx]

        # Raw 이벤트
        raw = [f"[{i}]={b:02X}" for i, b in enumerate(data)
               if b != (idle[i] if i < len(idle) else 0)]
        if raw:
            self.signal.jog.raw.emit(" | ".join(raw))

        # [1] Bitmask Rising Edge
        b1 = data[1] if len(data) > 1 else 0
        rising = b1 & ~self._prev_b1

        if rising & 0x40:                           # Bit 6 → 카메라 샷
            self._shot_count += 1
            self.signal.jog.shot.emit(self._shot_count)

        c_changed = False                           # Bit 1/2 → C축
        if rising & 0x02:
            self._c += inc; c_changed = True
        if rising & 0x04:
            self._c -= inc; c_changed = True
        if c_changed:
            self._emit_pos()
        self._prev_b1 = b1

        # [2] Bitmask Rising/Falling Edge → 증분 전환
        b2 = data[2] if len(data) > 2 else 0
        if b2 & ~self._prev_b2:                    # Rising → 올림
            self._change_inc(+1)
        elif ~b2 & self._prev_b2:                   # Falling → 내림
            self._change_inc(-1)
        self._prev_b2 = b2

        # 축: 16bit LE X=[4:6], Y=[6:8], A=[8:10], B=[10:12], Z=D-pad[3]
        if len(data) <= 11: return
        nx = ((data[4] | data[5] << 8) - (idle[4] | idle[5] << 8)) / 32768.0
        ny = -((data[6] | data[7] << 8) - (idle[6] | idle[7] << 8)) / 32768.0
        na = ((data[8] | data[9] << 8) - (idle[8] | idle[9] << 8)) / 32768.0
        nb = -((data[10] | data[11] << 8) - (idle[10] | idle[11] << 8)) / 32768.0

        dz = data[3] - idle[3] if len(data) > 3 else 0
        zd = {-8: 1.0, -4: -1.0}.get(dz, 0)       # D-pad 상하 → Z step

        if dz != self._prev_dz:                     # D-pad 좌우 → 증분 선택
            if dz == -6:   self._change_inc(+1)     # 우 → 올림
            elif dz == -2: self._change_inc(-1)     # 좌 → 내림
        self._prev_dz = dz

        # 데드존
        if abs(nx) < _DEADZONE: nx = 0
        if abs(ny) < _DEADZONE: ny = 0
        if abs(na) < _DEADZONE: na = 0
        if abs(nb) < _DEADZONE: nb = 0

        # 누적 적분 (0.25초 주기)
        now = time.time()
        dt = now - self._last_t
        if dt >= 0.25:
            changed = False
            if nx or ny or na or nb:
                self._x += nx * inc * dt
                self._y += ny * inc * dt
                self._a += na * inc * dt
                self._b += nb * inc * dt
                changed = True
            if zd:
                self._z += zd * inc
                changed = True
            if changed:
                self._emit_pos()
            self._last_t = now

    # ── Bluetooth ──

    def _activate_bt(self):
        if not self._bt: return False
        sp = _BtSearchParams(); sp.dwSize = ctypes.sizeof(sp)
        sp.fReturnAuthenticated = sp.fReturnRemembered = True
        sp.fReturnConnected = sp.fReturnUnknown = True
        di = _BtDevInfo(); di.dwSize = ctypes.sizeof(di)
        h = self._bt.BluetoothFindFirstDevice(ctypes.byref(sp), ctypes.byref(di))
        if not h or h == wintypes.HANDLE(-1).value: return False
        found = None
        try:
            while True:
                if (di.ulClassofDevice >> 8) & 0x1F == 5:
                    found = _BtDevInfo()
                    ctypes.memmove(ctypes.byref(found), ctypes.byref(di),
                                   ctypes.sizeof(di))
                    break
                di = _BtDevInfo(); di.dwSize = ctypes.sizeof(di)
                if not self._bt.BluetoothFindNextDevice(h, ctypes.byref(di)): break
        finally:
            self._bt.BluetoothFindDeviceClose(h)
        if not found or not found.fConnected: return False
        ret = self._bt.BluetoothSetServiceState(
            None, ctypes.byref(found), ctypes.byref(_HID_GUID), 0x01)
        return ret == 0

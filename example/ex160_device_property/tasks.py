# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
from py_alaska import task, Signal, rmi_run
import time

@task(mode="process", restart=True)
class CameraTask:
    DEVICE_PROPERTY = {
        "is_connect:bool": {"setter": "_hw_connect"},
        "exposure:int=100": {
            "validator": "_validate_exposure",
            "setter": "_hw_write_exposure",
            "debounce": 0.5,
            "notify_mode": "on_write"
        },
        "trigger_mode:bool=false": {
            "setter": "_hw_write_trigger_mode"
        },
        "@resync": {
            "open": "_resync_open",
            "close": "_resync_close",
            "condition": {"Eq": ["is_connect", True]},
            "order": ["trigger_mode", "exposure"]
        }
    }

    def __init__(self):
        print("[CameraTask] Instance Created")
        self._hw_exposure = 100
        self._hw_connected = False
        self._hw_trigger = False

    def _resync_open(self):
        print("[CameraTask] HW Session Open (Lock)")

    def _resync_close(self):
        print("[CameraTask] HW Session Close (Unlock)")

    def _validate_exposure(self, value):
        if value < 0 or value > 10000:
            raise ValueError(f"Exposure must be 0~10000, got {value}")
        return value

    def _hw_connect(self, value):
        print(f"[CameraTask] HW Connect: {value}")
        self._hw_connected = value

    def _hw_write_exposure(self, value):
        print(f"[CameraTask] HW Write Exposure: {value}")
        self._hw_exposure = value

    def _hw_read_exposure(self):
        print(f"[CameraTask] HW Read Exposure")
        return self._hw_exposure

    def _hw_write_trigger_mode(self, value):
        print(f"[CameraTask] HW Write Trigger: {value}")
        self._hw_trigger = value

    def run(self):
        print("[CameraTask] Started")
        while self.running:
            time.sleep(0.1)

@task(mode="thread")
class ControllerTask:
    def run(self):
        print("[Controller] Started")
        time.sleep(1.0)
        
        cam = self.runtime.get_client("camera")
        
        # 1. Before connection
        print("\n[Controller] Setting exposure to 500 (is_connect=False)")
        cam.exposure = 500  
        print(f"[Controller] Current Logic Exposure: {cam.exposure}")

        # 2. Connect
        print("\n[Controller] Connecting camera...")
        cam.is_connect = True 
        
        time.sleep(1.0) 
        
        # 3. Normal Operation
        print("\n[Controller] Setting exposure to 1000 (is_connect=True)")
        cam.exposure = 1000 
        
        time.sleep(1.0)
        
        # 4. Validation Error
        print("\n[Controller] Setting invalid exposure -500")
        try:
            cam.exposure = -500
        except Exception as e:
            print(f"[Controller] Caught expected error: {e}")
            
        # 5. Reset Simulation
        print("\n[Controller] Simulating device reset")
        cam.is_connect = False
        cam.exposure = 2000 
        time.sleep(0.5)
        cam.is_connect = True 
        
        time.sleep(1.0)
        print("\n[Controller] Example finished.")
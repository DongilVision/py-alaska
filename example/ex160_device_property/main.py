# Copyright (c) 2026 동일비전(Dongil Vision Korea). All Rights Reserved.
import sys
import multiprocessing
from pathlib import Path
import time

# Add project root and src to sys.path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import TaskManager, gconfig

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    config_path = Path(__file__).parent / "config.json"
    gconfig.load(config_path)

    print("ALASKA DeviceProperty Example (ex160)")
    
    manager = TaskManager(gconfig)
    print("Manager created.")
    manager.start_all()
    print("Manager started.")
    
    cam = manager.get_client("camera")
    print(f"Client for camera: {cam}")
    
    print("\n[Main] Setting exposure to 500 (is_connect=False)")
    cam.exposure = 500  
    print(f"[Main] Current Logic Exposure: {cam.exposure}")

    print("\n[Main] Connecting camera...")
    cam.is_connect = True 
    
    time.sleep(2.0) 
    
    print("\n[Main] Setting exposure to 1000")
    cam.exposure = 1000 
    
    time.sleep(1.0) 
    
    manager.stop_all()
    print("Done.")

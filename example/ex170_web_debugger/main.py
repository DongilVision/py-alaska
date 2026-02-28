import sys
import time
import multiprocessing
from pathlib import Path

# Add project root and src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from py_alaska import TaskManager, gconfig

def main():
    multiprocessing.freeze_support()
    
    # Load config
    config_path = Path(__file__).parent / "config.json"
    gconfig.load(config_path)
    
    print("="*60)
    print(" ALASKA v2.1 Web Debugger Example")
    print(" 1. Open your browser and go to http://localhost:7000")
    print(" 2. Monitor 'sensor.value' traffic in real-time.")
    print(" 3. Watch the console for 'PayloadTooLargeError' logs.")
    print("="*60)

    with TaskManager(gconfig) as manager:
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping example...")

if __name__ == "__main__":
    main()

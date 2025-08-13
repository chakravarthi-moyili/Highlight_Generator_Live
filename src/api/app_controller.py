from multiprocessing import Event, Process
from src.core.highlight_detector import main_loop

stop_event = Event()
process = None

def start_detection():
    global process, stop_event
    if process and process.is_alive():
        print("Detection already running.")
        return
    stop_event.clear()
    process = Process(target=main_loop, args=(stop_event,))
    process.start()
    print(f"Detection started in process {process.pid}")

def stop_detection():
    global process, stop_event
    if process and process.is_alive():
        print("Stopping detection...")
        stop_event.set()
        process.join(timeout=5)
        print("Detection stopped.")
    else:
        print("No detection process running.")

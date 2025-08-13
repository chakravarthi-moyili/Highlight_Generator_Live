import signal
from multiprocessing import Event, Process
from src.core.highlight_detector import main_loop

stop_event = Event()
process = None

def _run_main_loop():
    # Ignore SIGINT in chuld so parent handles it
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    main_loop(stop_event)

def start_detection():
    global process, stop_event
    if process and process.is_alive():
        print("Detection already running. restarting it...")
        stop_detection() # Clean stop before restart
    stop_event.clear()
    process = Process(target=_run_main_loop)
    process.start()
    print(f"Detection started in process {process.pid}")

def stop_detection():
    global process, stop_event
    if process and process.is_alive():
        print("Stopping detection...")
        stop_event.set()
        process.join(timeout=5)
        if process.is_alive():
            print("Process did not stop gracefully, terminating...")
            process.terminate()
            process.join()
        print("Detection stopped.")
    else:
        print("No detection process running.")

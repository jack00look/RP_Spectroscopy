import zerorpc
import threading
import time

def background_listener(callback):
    """
    Connects to the Zerorpc server and waits for signals in a loop.
    This function blocks while waiting for the stream.
    """
    print("[Listener] Starting background client...")
    client = zerorpc.Client()
    client.connect("tcp://127.0.0.1:4242")
    
    try:
        # This will block and wait for signals yielded by the server
        for signal in client.subscribe_to_signals():
            print(f"[Listener] Received: {signal}")
            callback(signal)
    except Exception as e:
        print(f"[Listener] Error: {e}")

def my_app_launch_logic(signal):
    """
    The function that gets triggered when a signal arrives.
    """
    print(f"[App Logic] !!! TRIGGERED BY {signal} !!!")
    print("[App Logic] Performing some urgent task...")

if __name__ == "__main__":
    # Start the listener in a background thread
    # daemon=True ensures the process can exit even if this thread is running
    t = threading.Thread(target=background_listener, args=(my_app_launch_logic,), daemon=True)
    t.start()
    
    print("[Main App] Application started and doing main work.")
    
    # Simulate main application work
    for i in range(12):
        print(f"[Main App] Working on main task {i}...")
        time.sleep(1)
        
    print("[Main App] Main work finished. Exiting.")

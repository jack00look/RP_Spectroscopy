import zerorpc
import logging
import pickle
from GettingStarted_lib.config_manager import ConfigManager
from GettingStarted_lib.LaserLockingController import LaserLockingController
from GettingStarted_lib.Interface import Interface
import threading
import time
from pathlib import Path

class LaserLockServer:
    def __init__(self, board_name="RedPitaya_K"):
        print(f"Initializing Laser Lock Server for {board_name}...")
        
        # Load config via ConfigManager (now uses default path automatically)
        self.config_manager = ConfigManager()
        
        # Get board specific parameters
        board = self.config_manager.get_board(board_name)
        if not board:
            raise ValueError(f"Board {board_name} not found in config.")
        
        user, pw = self.config_manager.get_credentials(board_name)
        
        # Instantiate pure Interface
        self.interface = Interface(
            host=board.ip,
            linien_port=board.linien_port,
            username=user,
            password=pw,
            ssh_port=board.ssh_port
        )
        self.controller = LaserLockingController(self.interface)
        self.lock_thread = None
        self._stop_requested = False

    def start_lock(self, line_name):
        """
        Starts the automatic locking procedure for a given line.
        Runs in the background thread if not already running.
        """
        if self.lock_thread and self.lock_thread.is_alive():
            return "Error: Locking is already in progress."
        
        self.controller.force_stop = False
        self.lock_thread = threading.Thread(
            target=self.controller.automatic_lock_relock,
            args=(line_name,),
            kwargs={'relock': True},
            daemon=True
        )
        self.lock_thread.start()
        return f"Started automatic locking for {line_name}"

    def stop_lock(self):
        """
        Signals the controller to stop locking and start sweeping.
        """
        print("Stop signal received!")
        self.controller.force_stop = True
        return "Stop signal sent to controller."

    @zerorpc.stream
    def get_status_stream(self):
        """
        Streams current system status to the client.
        """
        while True:
            try:
                # Refresh parameters and history for accurate telemetry
                self.interface.check_for_changed_parameters()
                to_plot = pickle.loads(self.interface.client.parameters.to_plot.value)
                history = self.interface.get_history()
                
                status = {
                    "is_locked": "error_signal" in to_plot,
                    "monitor_mean": float(sum(history['monitor_values'][-10:]) / 10) if 'monitor_values' in history else 0.0,
                    "stop_flag": self.controller.force_stop,
                    "timestamp": time.time()
                }
                yield status
            except Exception as e:
                yield {"error": str(e)}
            
            time.sleep(1)

    def get_sweep_data(self):
        """
        Returns full sweep data for plotting.
        """
        return self.interface.get_sweep()

if __name__ == "__main__":
    server = zerorpc.Server(LaserLockServer())
    server.bind("tcp://0.0.0.0:4242")
    print("Laser Lock Zerorpc Server running on port 4242...")
    server.run()

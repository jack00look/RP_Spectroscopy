import sys
import time
import threading
import logging
import numpy as np
import zerorpc

# --- PYSIDE6 IMPORTS ---
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                               QPushButton, QLabel, QWidget, QTextEdit)

# =============================================================================
# SECTION 1: HARDWARE WORKER (LANE 2 - Hardware Thread)
# =============================================================================

class LaserLockController(QObject):
    """
    The Worker Class. Lives in the Hardware Thread.
    Uses 'Signal' instead of 'pyqtSignal'.
    """
    # Signals for Data Visualization (High Frequency)
    sig_sweep_data = Signal(np.ndarray, np.ndarray) # x, y
    sig_jitter_data = Signal(float, float)          # time, shift
    
    # Signals for Logging/Status (Low Frequency)
    sig_log_message = Signal(str)
    sig_lock_status = Signal(str) # "LOCKED", "UNLOCKED", "SCANNING"

    def __init__(self, interface, data_handler):
        super().__init__()
        self.interface = interface
        self.data_handler = data_handler
        self._stop_requested = False
        self._is_running = False

    @Slot(str)
    def start_auto_lock(self, line_name):
        """Main entry point called by GUI or RPC"""
        self._stop_requested = False
        self._is_running = True
        self.sig_log_message.emit(f"Worker: Starting Auto-Lock for {line_name}...")
        
        try:
            self._run_locking_logic(line_name)
        except Exception as e:
            self.sig_log_message.emit(f"Worker Error: {str(e)}")
        finally:
            self._is_running = False
            self.sig_lock_status.emit("STOPPED")

    @Slot()
    def stop(self):
        """Sets flag to kill loops. Safe to call from any thread."""
        self._stop_requested = True
        self.sig_log_message.emit("Worker: Stop requested...")

    def _run_locking_logic(self, line_name):
        """Simulates the locking physics loop"""
        
        # 1. Broad Search Phase
        self.sig_lock_status.emit("SCANNING")
        self.sig_log_message.emit("Worker: Finding reference lines...")
        
        for i in range(5):
            if self._stop_requested: return
            time.sleep(0.5) # Simulate hardware scan time
            
            # Emit scan data
            x = np.linspace(0, 100, 100)
            y = np.sin(x + i) # Moving wave
            self.sig_sweep_data.emit(x, y)

        if self._stop_requested: return

        # 2. Lock Maintenance Loop
        self.sig_lock_status.emit("LOCKED")
        self.sig_log_message.emit(f"Worker: Locked on {line_name}")
        
        start_time = time.time()
        
        while not self._stop_requested:
            # Simulate PID Hardware Read
            # current_val = self.interface.read_input() 
            current_shift = np.random.normal(0, 0.1) # Fake noise
            
            # Emit Data
            elapsed = time.time() - start_time
            self.sig_jitter_data.emit(elapsed, current_shift)
            
            # Throttle loop
            time.sleep(0.05) 

# =============================================================================
# SECTION 2: COMMS WORKER (LANE 3 - Service Thread)
# =============================================================================

class LaserRPC_API:
    """The Public Interface for Remote Control (ZeroRPC)"""
    def __init__(self, service_manager):
        self.sm = service_manager

    def remote_lock(self, line_name):
        print(f"RPC: Received lock request for {line_name}")
        # Emit signal to Qt system
        self.sm.sig_incoming_lock.emit(line_name)
        return "Command Sent"

    def remote_stop(self):
        print("RPC: Received stop request")
        self.sm.sig_incoming_stop.emit()
        return "Command Sent"

class ServiceManager(QObject):
    # Signals TO the Laser Controller
    sig_incoming_lock = Signal(str)
    sig_incoming_stop = Signal()

    def __init__(self, grafana_manager):
        super().__init__()
        self.grafana = grafana_manager
        
        # Setup ZeroRPC
        self.rpc_api = LaserRPC_API(self)
        self.server = zerorpc.Server(self.rpc_api)

    def start_rpc_server(self):
        # Run blocking server in a standard daemon thread 
        # so it doesn't block this QThread's event loop
        t = threading.Thread(target=self._server_loop, daemon=True)
        t.start()

    def _server_loop(self):
        print("ServiceManager: RPC Server listening on :4242")
        self.server.bind("tcp://0.0.0.0:4242")
        try:
            self.server.run()
        except Exception as e:
            print(f"RPC Server Error: {e}")

    @Slot(float, float)
    def handle_jitter_data(self, timestamp, shift):
        """
        Receives data from LLC (Lane 2) to upload to Grafana.
        Failures here do not crash the laser.
        """
        try:
            # self.grafana.log(timestamp, shift)
            pass
        except:
            pass

# =============================================================================
# SECTION 3: THE COORDINATOR (GENERAL MANAGER)
# =============================================================================

class GeneralManager:
    def __init__(self):
        # 1. Resources (Mocks)
        self.interface = MockInterface() 
        self.data_handler = MockDataHandler() 
        self.grafana = None 

        # 2. Workers
        self.llc = LaserLockController(self.interface, self.data_handler)
        self.comms = ServiceManager(self.grafana)

        # 3. Threads
        self.hw_thread = QThread()
        self.comms_thread = QThread()
        
        self.llc.moveToThread(self.hw_thread)
        self.comms.moveToThread(self.comms_thread)

        # 4. Connections
        # Data flow: LLC -> Comms
        self.llc.sig_jitter_data.connect(self.comms.handle_jitter_data)
        
        # Command flow: Comms -> LLC
        self.comms.sig_incoming_lock.connect(self.llc.start_auto_lock)
        self.comms.sig_incoming_stop.connect(self.llc.stop)

        # 5. Start
        self.hw_thread.start()
        self.comms_thread.start()
        
        # Start the RPC server (inside the Comms logic)
        self.comms.start_rpc_server()

    def cleanup(self):
        """Graceful shutdown"""
        self.llc.stop()
        self.hw_thread.quit()
        self.comms_thread.quit()
        self.hw_thread.wait()
        self.comms_thread.wait()

# =============================================================================
# SECTION 4: THE GUI (LANE 1 - Main Thread)
# =============================================================================

class MainWindow(QMainWindow):
    def __init__(self, manager):
        super().__init__()
        self.mgr = manager
        self.setWindowTitle("Laser Control (PySide6)")
        self.resize(600, 400)

        # Layout
        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # Controls
        self.btn_lock = QPushButton("Auto Lock (Rb87)")
        self.btn_stop = QPushButton("Emergency Stop")
        self.lbl_status = QLabel("Status: IDLE")
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)

        layout.addWidget(self.lbl_status)
        layout.addWidget(self.btn_lock)
        layout.addWidget(self.btn_stop)
        layout.addWidget(QLabel("Logs:"))
        layout.addWidget(self.txt_log)

        # Interactions
        self.btn_lock.clicked.connect(lambda: self.mgr.llc.start_auto_lock("Rb87"))
        self.btn_stop.clicked.connect(self.mgr.llc.stop)

        # Feedback from Worker
        self.mgr.llc.sig_log_message.connect(self.append_log)
        self.mgr.llc.sig_lock_status.connect(self.update_status)

    @Slot(str)
    def append_log(self, msg):
        self.txt_log.append(msg)

    @Slot(str)
    def update_status(self, status):
        self.lbl_status.setText(f"Status: {status}")
        style = "color: green; font-weight: bold;" if status == "LOCKED" else "color: black;"
        self.lbl_status.setStyleSheet(style)

# =============================================================================
# MOCKS
# =============================================================================
class MockInterface:
    def read_input(self): return 0.0
class MockDataHandler:
    pass

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    gm = GeneralManager()
    
    window = MainWindow(gm)
    window.show()
    
    # Note: app.exec() instead of app.exec_() in PySide6
    exit_code = app.exec()
    
    gm.cleanup()
    sys.exit(exit_code)
import sys
import time
import threading
import numpy as np
import zerorpc

# --- PYSIDE6 IMPORTS ---
from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                               QPushButton, QLabel, QWidget, QTextEdit, 
                               QLineEdit, QDialog, QCheckBox)

# =============================================================================
# SECTION 1: HARDWARE WORKER (LANE 2 - Hardware Thread)
# =============================================================================

class LaserLockController(QObject):
    """
    The Worker Class. Lives in the Hardware Thread.
    """
    # Signals for Data Visualization
    sig_sweep_data = Signal(np.ndarray, np.ndarray) # x, y
    sig_jitter_data = Signal(float, float)          # time, shift
    
    # Signals for Logging/Status
    sig_log_message = Signal(str)
    sig_lock_status = Signal(str) 

    def __init__(self, interface, data_handler):
        super().__init__()
        self.interface = interface
        self.data_handler = data_handler
        self._stop_requested = False
        self._is_running = False
        
        # --- LOGIC CONTROL FLAGS ---
        # Default: True (Automatic detection and relock is ON)
        self._auto_relock_enabled = True 

    # --- SETTINGS SLOTS (Thread-Safe Inputs) ---
    @Slot(bool)
    def set_auto_relock(self, enabled):
        """
        Called by the Settings Window via Signal.
        Safely updates the internal flag used in the loop.
        """
        self._auto_relock_enabled = enabled
        state_str = "ENABLED" if enabled else "DISABLED"
        self.sig_log_message.emit(f"Worker: Auto-Relock logic is now {state_str}")

    @Slot(str)
    def start_auto_lock(self, line_name):
        """Main entry point called by GUI or RPC"""
        if self._is_running:
            self.sig_log_message.emit("Worker: Already running!")
            return

        self._stop_requested = False
        self._is_running = True
        self.sig_log_message.emit(f"Worker: Starting Auto-Lock for '{line_name}'...")
        
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
        """Simulates the blocking locking loop"""
        
        # 1. Broad Search Phase
        self.sig_lock_status.emit("SCANNING")
        
        for i in range(5):
            if self._stop_requested: return
            time.sleep(0.5) 
            x = np.linspace(0, 100, 100)
            y = np.sin(x + i) 
            self.sig_sweep_data.emit(x, y)

        if self._stop_requested: return

        # 2. Lock Maintenance Loop
        self.sig_lock_status.emit("LOCKED")
        self.sig_log_message.emit(f"Worker: Locked on {line_name}")
        
        start_time = time.time()
        
        while not self._stop_requested:
            # A. Simulate hardware I/O
            current_shift = np.random.normal(0, 0.1) 
            elapsed = time.time() - start_time
            
            # B. Emit Data for Plotting
            self.sig_jitter_data.emit(elapsed, current_shift)
            
            # C. RELOCK LOGIC CHECK
            # This is where we check the flag set by the tickbox
            if self._auto_relock_enabled:
                # Simulate a check: "If unlock detected -> relock"
                # if check_unlock_condition():
                #     self.relock()
                pass
            
            # Throttle
            time.sleep(0.05) 

# =============================================================================
# SECTION 2: COMMS WORKER (LANE 3 - Service Thread)
# =============================================================================

class LaserRPC_API:
    def __init__(self, service_manager):
        self.sm = service_manager

    def remote_lock(self, line_name):
        print(f"RPC: Received lock request for {line_name}")
        self.sm.sig_incoming_lock.emit(line_name)
        return "Command Sent"

    def remote_stop(self):
        print("RPC: Received stop request")
        self.sm.sig_incoming_stop.emit()
        return "Command Sent"

class ServiceManager(QObject):
    sig_incoming_lock = Signal(str)
    sig_incoming_stop = Signal()

    def __init__(self, grafana_manager):
        super().__init__()
        self.grafana = grafana_manager
        self.rpc_api = LaserRPC_API(self)
        self.server = zerorpc.Server(self.rpc_api)

    def start_rpc_server(self):
        t = threading.Thread(target=self._server_loop, daemon=True)
        t.start()

    def _server_loop(self):
        print("ServiceManager: RPC Server listening on :4242")
        self.server.bind("tcp://0.0.0.0:4242")
        try:
            self.server.run()
        except Exception: pass

    @Slot(float, float)
    def handle_jitter_data(self, timestamp, shift):
        # Upload to Grafana logic here
        pass

# =============================================================================
# SECTION 3: THE GUI (LANE 1 - Main Thread)
# =============================================================================

class SettingsWindow(QDialog):
    """
    Separate Window for configuring the Laser Controller behavior.
    """
    # Signal carrying the boolean state of the checkbox
    sig_relock_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lock Settings")
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        
        # The Toggle Box
        self.chk_relock = QCheckBox("Enable Automatic Relock")
        self.chk_relock.setChecked(True) # Default must match LLC default
        self.chk_relock.setToolTip("If unchecked, the laser will NOT try to regain lock if lost.")
        
        layout.addWidget(self.chk_relock)
        
        # Connect internal signal
        self.chk_relock.toggled.connect(self.sig_relock_toggled.emit)

class MainWindow(QMainWindow):
    # Signals to request actions
    sig_request_lock = Signal(str)
    sig_request_stop = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Control Center")
        self.resize(600, 500)

        # 1. Initialize Settings Window (Hidden)
        self.settings_window = SettingsWindow(self)

        # 2. Main Layout
        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        # Inputs & Controls
        self.input_line = QLineEdit("Rb87")
        self.input_line.setPlaceholderText("Enter Target Line Name...")
        
        self.btn_lock = QPushButton("Start Auto-Lock")
        self.btn_settings = QPushButton("Settings") # Opens the dialog
        self.btn_stop = QPushButton("EMERGENCY STOP")
        self.btn_stop.setStyleSheet("background-color: red; color: white; font-weight: bold;")

        # Status & Logs
        self.lbl_status = QLabel("Status: IDLE")
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)

        layout.addWidget(QLabel("Target Line:"))
        layout.addWidget(self.input_line)
        layout.addWidget(self.btn_lock)
        layout.addWidget(self.btn_settings)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.lbl_status)
        layout.addWidget(self.txt_log)

        # User Interactions
        self.btn_lock.clicked.connect(self.on_lock_clicked)
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        self.btn_settings.clicked.connect(self.settings_window.show)

    def on_lock_clicked(self):
        line_name = self.input_line.text()
        if line_name:
            self.txt_log.append(f"GUI: Requesting lock for {line_name}...")
            self.sig_request_lock.emit(line_name)

    def on_stop_clicked(self):
        self.txt_log.append("GUI: Requesting STOP.")
        self.sig_request_stop.emit()

    # Slots for Updates
    @Slot(str)
    def append_log(self, msg):
        self.txt_log.append(msg)

    @Slot(str)
    def update_status(self, status):
        self.lbl_status.setText(f"Status: {status}")
        if status == "LOCKED":
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
        elif status == "STOPPED":
            self.lbl_status.setStyleSheet("color: red;")
        else:
            self.lbl_status.setStyleSheet("color: black;")

# =============================================================================
# SECTION 4: THE COORDINATOR (GENERAL MANAGER)
# =============================================================================

class GeneralManager:
    def __init__(self):
        # 1. Setup Resources
        self.interface = MockInterface() 
        self.data_handler = MockDataHandler() 
        self.grafana = None 

        # 2. Setup Workers
        self.llc = LaserLockController(self.interface, self.data_handler)
        self.comms = ServiceManager(self.grafana)

        # 3. Setup Threads
        self.hw_thread = QThread()
        self.comms_thread = QThread()
        
        self.llc.moveToThread(self.hw_thread)
        self.comms.moveToThread(self.comms_thread)

        # 4. Setup GUI
        self.window = MainWindow()

        # --- WIRING DIAGRAM ---
        
        # A. GUI -> Hardware Worker (Commands)
        self.window.sig_request_lock.connect(self.llc.start_auto_lock)
        self.window.sig_request_stop.connect(self.llc.stop)
        
        # B. Settings Window -> Hardware Worker (Configuration)
        # This connects the checkbox signal directly to the worker's slot
        self.window.settings_window.sig_relock_toggled.connect(
            self.llc.set_auto_relock
        )

        # C. Hardware -> GUI (Feedback)
        self.llc.sig_log_message.connect(self.window.append_log)
        self.llc.sig_lock_status.connect(self.window.update_status)
        
        # D. Hardware -> Comms (Data)
        self.llc.sig_jitter_data.connect(self.comms.handle_jitter_data)
        
        # E. Comms (RPC) -> Hardware (Remote Control)
        self.comms.sig_incoming_lock.connect(self.llc.start_auto_lock)
        self.comms.sig_incoming_stop.connect(self.llc.stop)

        # 5. Start Engines
        self.hw_thread.start()
        self.comms_thread.start()
        self.comms.start_rpc_server()
        
        # 6. Show Window
        self.window.show()

    def cleanup(self):
        self.llc.stop()
        self.hw_thread.quit()
        self.comms_thread.quit()
        self.hw_thread.wait()
        self.comms_thread.wait()

# =============================================================================
# MOCKS
# =============================================================================
class MockInterface:
    def read_input(self): return 0.0
class MockDataHandler:
    pass

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    gm = GeneralManager()
    
    exit_code = app.exec()
    
    gm.cleanup()
    sys.exit(exit_code)
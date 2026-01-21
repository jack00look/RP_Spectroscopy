import sys
import zerorpc
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette

class StatusWorker(QObject):
    status_received = pyqtSignal(dict)
    connection_lost = pyqtSignal()

    def __init__(self, client):
        super().__init__()
        self.client = client
        self._running = True

    def run(self):
        try:
            # Subscribing to the status stream from the server
            for status in self.client.get_status_stream():
                if not self._running:
                    break
                self.status_received.emit(status)
        except Exception as e:
            print(f"Connection error: {e}")
            self.connection_lost.emit()

    def stop(self):
        self._running = False

class LaserLockGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Lock Controller PRO")
        self.setMinimumSize(400, 300)
        
        # Connect to Zerorpc Server
        self.client = zerorpc.Client(timeout=10)
        self.client.connect("tcp://127.0.0.1:4242")
        
        self.init_ui()
        self.start_status_listener()

    def init_ui(self):
        # Premium Dark Theme Palette
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #E0E0E0; font-family: 'Segoe UI', sans-serif; }
            QPushButton { 
                border-radius: 8px; 
                padding: 15px; 
                font-size: 16px; 
                font-weight: bold;
                color: white;
            }
            #btn_start { background-color: #2E7D32; }
            #btn_start:hover { background-color: #388E3C; }
            #btn_stop { background-color: #C62828; }
            #btn_stop:hover { background-color: #D32F2F; }
            #status_card { 
                background-color: #1E1E1E; 
                border: 1px solid #333; 
                border-radius: 12px;
                padding: 20px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header
        header = QLabel("AUTOMATIC LASER LOCK")
        header.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header)

        # Status Card
        self.status_card = QFrame()
        self.status_card.setObjectName("status_card")
        card_layout = QVBoxLayout(self.status_card)
        
        self.lbl_lock_status = QLabel("STATUS: UNKNOWN")
        self.lbl_lock_status.setFont(QFont("Segoe UI", 16))
        self.lbl_lock_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_lock_status)

        self.lbl_monitor = QLabel("Monitor Signal: -- V")
        self.lbl_monitor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_monitor)

        main_layout.addWidget(self.status_card)

        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("START LOCK")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.clicked.connect(self.on_start_clicked)
        button_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("STOP & SWEEP")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        button_layout.addWidget(self.btn_stop)

        main_layout.addLayout(button_layout)

    def start_status_listener(self):
        self.thread = QThread() # Note: QThread needs to be imported
        # Fixed: using threading.Thread + pyqtSignal instead of QThread for simplicity if needed, 
        # but let's use the Worker pattern correctly.
        from PyQt6.QtCore import QThread
        self.worker_thread = QThread()
        self.worker = StatusWorker(self.client)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.status_received.connect(self.update_status)
        self.worker.connection_lost.connect(self.handle_connection_lost)
        self.worker_thread.start()

    def update_status(self, status):
        if status.get("is_locked"):
            self.lbl_lock_status.setText("LOCKED")
            self.lbl_lock_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.lbl_lock_status.setText("UNLOCKED / SWEEPING")
            self.lbl_lock_status.setStyleSheet("color: #FF5252; font-weight: bold;")
        
        val = status.get("monitor_mean", 0.0)
        self.lbl_monitor.setText(f"Monitor Signal: {val:.4f} V")

    def handle_connection_lost(self):
        self.lbl_lock_status.setText("SERVER DISCONNECTED")
        self.lbl_lock_status.setStyleSheet("color: orange;")

    def on_start_clicked(self):
        try:
            res = self.client.start_lock("D2_line") # Example line name
            print(res)
        except Exception as e:
            print(f"Error starting lock: {e}")

    def on_stop_clicked(self):
        try:
            res = self.client.stop_lock()
            print(res)
        except Exception as e:
            print(f"Error stopping lock: {e}")

    def closeEvent(self, event):
        self.worker.stop()
        self.worker_thread.quit()
        self.worker_thread.wait()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = LaserLockGUI()
    gui.show()
    sys.exit(app.exec())

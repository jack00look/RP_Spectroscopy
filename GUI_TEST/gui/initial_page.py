from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QSpacerItem, QSizePolicy)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal, QTimer
import os

class InitialPage(QWidget):
    sig_request_connection = Signal()
    sig_request_reference_lines = Signal()

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.logger.info("InitialPage initialized.")
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # Title
        self.title = QLabel("Lock it!")
        self.title.setStyleSheet("font-size: 36px; font-weight: bold; margin-bottom: 20px;")
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)

        # Image
        self.image_label = QLabel()
        self.image_label.setFixedSize(400, 300)
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # Load Images
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.img_open_path = os.path.join(base_dir, 'images', 'open_lock.png')
        self.img_closed_path = os.path.join(base_dir, 'images', 'closed_lock.png')
        
        self.pixmap_open = self._load_pixmap(self.img_open_path)
        self.pixmap_closed = self._load_pixmap(self.img_closed_path)
        
        self.update_image(self.pixmap_open)
        
        layout.addWidget(self.image_label, 0, Qt.AlignCenter)

        layout.addSpacing(30)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_ref_lines = QPushButton("Reference lines")
        self.btn_connection = QPushButton("Red Pitaya connection")
        
        self.btn_ref_lines.setMinimumHeight(50)
        self.btn_connection.setMinimumHeight(50)

        self.btn_ref_lines.setStyleSheet("font-size: 18px;")
        self.btn_connection.setStyleSheet("font-size: 18px;")

        btn_layout.addWidget(self.btn_ref_lines)
        btn_layout.addSpacing(20)
        btn_layout.addWidget(self.btn_connection)
        
        layout.addLayout(btn_layout)

        # Connections
        self.btn_ref_lines.clicked.connect(self.on_ref_lines_clicked)
        self.btn_connection.clicked.connect(self.on_connection_clicked)

        # Timer for simulated delay
        self.transition_timer = QTimer(self)
        self.transition_timer.setSingleShot(True)
        self.transition_timer.timeout.connect(self.finish_connection_transition)

    def _load_pixmap(self, path):
        if os.path.exists(path):
            return QPixmap(path)
        else:
            self.logger.error(f"Image not found at {path}")
            # Return a placeholder pixmap in red
            pix = QPixmap(400, 300)
            pix.fill(Qt.red)
            return pix

    def update_image(self, pixmap):
        if not pixmap or pixmap.isNull():
            return
        # Scale to fit label, keeping aspect ratio
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def on_ref_lines_clicked(self):
        self.logger.info("Reference Lines button clicked.")
        self.sig_request_reference_lines.emit()

    def on_connection_clicked(self):
        self.logger.info("Connection button clicked. Starting transition...")
        # Change image to Closed Lock
        self.update_image(self.pixmap_closed)
        
        # Disable button to prevent double clicks
        self.btn_connection.setEnabled(False)
        
        # Start timer for 1 second
        self.transition_timer.start(500)

    def finish_connection_transition(self):
        self.logger.info("Transition complete. Requesting Connection Page.")
        self.sig_request_connection.emit()
        
        # Reset state for next time (optional, depending on if we want it to reset when coming back)
        self.reset_state()

    def reset_state(self):
        self.update_image(self.pixmap_open)
        self.btn_connection.setEnabled(True)

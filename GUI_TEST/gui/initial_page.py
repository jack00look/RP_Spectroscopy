from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer

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

        # Image Placeholder
        self.image_label = QLabel("Image Placeholder 1")
        self.image_label.setStyleSheet("background-color: #DDDDDD; border: 2px dashed #999; font-size: 20px;")
        self.image_label.setFixedSize(400, 300)
        self.image_label.setAlignment(Qt.AlignCenter)
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

    def on_ref_lines_clicked(self):
        self.logger.info("Reference Lines button clicked.")
        self.sig_request_reference_lines.emit()

    def on_connection_clicked(self):
        self.logger.info("Connection button clicked. Starting transition...")
        # Change image to Simulated Image 2
        self.image_label.setText("Image Placeholder 2")
        self.image_label.setStyleSheet("background-color: #AADDAA; border: 2px solid #55AA55; font-size: 20px;")
        
        # Disable button to prevent double clicks
        self.btn_connection.setEnabled(False)
        
        # Start timer for 1 second
        self.transition_timer.start(1000)

    def finish_connection_transition(self):
        self.logger.info("Transition complete. Requesting Connection Page.")
        self.sig_request_connection.emit()
        
        # Reset state for next time (optional, depending on if we want it to reset when coming back)
        self.reset_state()

    def reset_state(self):
        self.image_label.setText("Image Placeholder 1")
        self.image_label.setStyleSheet("background-color: #DDDDDD; border: 2px dashed #999; font-size: 20px;")
        self.btn_connection.setEnabled(True)

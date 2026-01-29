from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel)
from PySide6.QtCore import Qt, Signal

class ReferenceLinesPage(QWidget):
    sig_request_back = Signal()

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.logger.info("ReferenceLinesPage initialized.")
        
        layout = QVBoxLayout(self)

        title = QLabel("Reference Lines")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Placeholder content
        content = QLabel("Reference Lines functionality will be implemented here.")
        content.setAlignment(Qt.AlignCenter)
        layout.addWidget(content)

        layout.addStretch()

        # Back Button
        self.btn_back = QPushButton("Back")
        self.btn_back.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.btn_back, 0, Qt.AlignLeft)

        self.btn_back.clicked.connect(self.on_back_clicked)

    def on_back_clicked(self):
        self.logger.info("Back button clicked in ReferenceLinesPage.")
        self.sig_request_back.emit()

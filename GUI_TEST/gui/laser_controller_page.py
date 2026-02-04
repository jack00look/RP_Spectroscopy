from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class LaserControllerPage(QWidget):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        layout = QVBoxLayout(self)
        label = QLabel("Laser Controller Page")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

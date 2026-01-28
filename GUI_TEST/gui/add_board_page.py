from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QHeaderView, QAbstractItemView, QPushButton,
                               QLabel, QTableWidgetItem, QLineEdit)
from PySide6.QtCore import Qt, Signal, Slot

class AddBoardPage(QWidget):
    sig_request_back = Signal()
    sig_submit_board = Signal(str, str, str, str)

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.logger.info("AddBoardPage initialized.")
        layout = QVBoxLayout(self)

        title = QLabel("Add a new Red Pitaya")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(50, 20, 50, 20)
        
        self.inp_name = QLineEdit(); self.inp_name.setPlaceholderText("Name")
        self.inp_ip = QLineEdit(); self.inp_ip.setPlaceholderText("IP")
        self.inp_lport = QLineEdit("18862"); self.inp_lport.setPlaceholderText("Linien Port")
        self.inp_sport = QLineEdit("22"); self.inp_sport.setPlaceholderText("SSH Port")

        layout.addWidget(QLabel("Board Name:"))
        layout.addWidget(self.inp_name)
        layout.addWidget(QLabel("IP Address:"))
        layout.addWidget(self.inp_ip)
        layout.addWidget(QLabel("Linien Port:"))
        layout.addWidget(self.inp_lport)
        layout.addWidget(QLabel("SSH Port:"))
        layout.addWidget(self.inp_sport)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_add = QPushButton("Add")
        
        btn_layout.addWidget(self.btn_back)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)

        self.btn_back.clicked.connect(self.sig_request_back.emit)
        self.btn_add.clicked.connect(self.on_add_clicked)

    def on_add_clicked(self):
        if self.inp_name.text() and self.inp_ip.text():
            self.sig_submit_board.emit(
                self.inp_name.text(), self.inp_ip.text(), 
                self.inp_lport.text(), self.inp_sport.text()
            )
            self.inp_name.clear(); self.inp_ip.clear()
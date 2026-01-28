from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QHeaderView, QAbstractItemView, QPushButton,
                               QLabel, QTableWidgetItem)
from PySide6.QtCore import Qt, Signal, Slot

class ConnectionPage(QWidget):
    sig_request_connect = Signal(str)
    sig_request_remove = Signal(str)
    sig_request_add_page = Signal()
    sig_request_refresh = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Red Pitaya connection")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "IP Address", "Linien Port", "SSH Port"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("↻")
        self.btn_confirm = QPushButton("Confirm")
        self.btn_remove = QPushButton("-")
        self.btn_add = QPushButton("+")

        self.btn_confirm.setStyleSheet("background-color: #4CAF50; color: white;")
        self.btn_remove.setStyleSheet("background-color: #f44336; color: white;")
        
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

        self.btn_add.clicked.connect(self.sig_request_add_page.emit)
        self.btn_refresh.clicked.connect(self.sig_request_refresh.emit)
        self.btn_confirm.clicked.connect(self.on_confirm_clicked)
        self.btn_remove.clicked.connect(self.on_remove_clicked)

    def on_confirm_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            name = self.table.item(row, 0).text()
            self.sig_request_connect.emit(name)

    def on_remove_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            name = self.table.item(row, 0).text()
            self.sig_request_remove.emit(name)

    @Slot(list)
    def update_table(self, board_list):
        self.table.setRowCount(0)
        for board in board_list:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(board.get('name', 'Unknown'))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(board.get('ip', ''))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(board.get('linien_port', ''))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(board.get('ssh_port', ''))))

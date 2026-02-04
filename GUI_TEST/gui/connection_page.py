from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
                               QHeaderView, QAbstractItemView, QPushButton,
                               QLabel, QTableWidgetItem)
from PySide6.QtCore import Qt, Signal, Slot

class ConnectionPage(QWidget):
    sig_request_connect = Signal(dict)
    sig_request_remove = Signal(str)
    sig_request_add_page = Signal()
    sig_request_refresh = Signal()
    sig_request_back = Signal()

    def __init__(self, logger):
        super().__init__()
        self.logger = logger
        self.logger.info("ConnectionPage initialized.")
        self.board_map = {} # Store board dicts by name

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
        self.btn_refresh = QPushButton("Refresh")
        self.btn_confirm = QPushButton("Connect")
        self.btn_remove = QPushButton("Delete")
        self.btn_add = QPushButton("Add")
        self.btn_back = QPushButton("Back")

        self.btn_confirm.setStyleSheet("background-color: #4CAF50; color: white;")
        self.btn_remove.setStyleSheet("background-color: #f44336; color: white;")
        
        btn_layout.addWidget(self.btn_back)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

        self.btn_back.clicked.connect(self.sig_request_back.emit)
        self.btn_add.clicked.connect(self.sig_request_add_page.emit)
        self.btn_refresh.clicked.connect(self.sig_request_refresh.emit)
        self.btn_confirm.clicked.connect(self.on_confirm_clicked)
        self.btn_remove.clicked.connect(self.on_remove_clicked)

    def on_confirm_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            name = self.table.item(row, 0).text()
            board = self.board_map.get(name)
            if board:
                self.sig_request_connect.emit(board)
            else:
                self.logger.error(f"Board {name} not found in map.")

    def on_remove_clicked(self):
        row = self.table.currentRow()
        if row >= 0:
            name = self.table.item(row, 0).text()
            self.sig_request_remove.emit(name)

    @Slot(list)
    def update_table(self, board_list):
        self.table.setRowCount(0)
        self.board_map.clear()
        for board in board_list:
            name = str(board.get('name', 'Unknown'))
            self.board_map[name] = board
            
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(board.get('ip', ''))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(board.get('linien_port', ''))))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(board.get('ssh_port', ''))))

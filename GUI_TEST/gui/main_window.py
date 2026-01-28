from PySide6.QtWidgets import (QMainWindow, QStackedWidget)
from connection_page import ConnectionPage
from add_board_page import AddBoardPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LaserLock Application")
        self.resize(800, 600)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.page_connect = ConnectionPage()
        self.page_add = AddBoardPage()

        self.stack.addWidget(self.page_connect)
        self.stack.addWidget(self.page_add)

    def go_to_connection(self):
        self.stack.setCurrentWidget(self.page_connect)

    def go_to_add(self):
        self.stack.setCurrentWidget(self.page_add)
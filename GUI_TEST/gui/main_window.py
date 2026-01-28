from PySide6.QtWidgets import (QMainWindow, QStackedWidget)
from .connection_page import ConnectionPage
from .add_board_page import AddBoardPage
import logging
import os
from libraries.logging_config import setup_logging

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LaserLock Application")
        self.resize(800, 600)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Setup Logging
        # We need to know where logs are. MainWindow doesn't have direct access to config object unless passed.
        # But we can assume default relative path or check if config loading in main app sets env or singleton.
        # For simplicity, let's look for "logs" folder in specific location or just use "./logs"
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, 'logs')
        log_file = os.path.join(log_dir, 'gui.log')
        
        self.logger = logging.getLogger('GUI')
        setup_logging(self.logger, log_file)
        self.logger.info("GUI MainWindow initialized.")

        self.page_connect = ConnectionPage(self.logger)
        self.page_add = AddBoardPage(self.logger)

        self.stack.addWidget(self.page_connect)
        self.stack.addWidget(self.page_add)

    def go_to_connection(self):
        self.stack.setCurrentWidget(self.page_connect)

    def go_to_add(self):
        self.stack.setCurrentWidget(self.page_add)
from PySide6.QtWidgets import (QMainWindow, QStackedWidget)
from .connection_page import ConnectionPage
from .add_board_page import AddBoardPage
from .initial_page import InitialPage
from .reference_lines_page import ReferenceLinesPage
from .laser_controller_page import LaserControllerPage
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

        self.page_initial = InitialPage(self.logger)
        self.page_connect = ConnectionPage(self.logger)
        self.page_add = AddBoardPage(self.logger)
        self.page_reflines = ReferenceLinesPage(self.logger)
        self.page_laser = LaserControllerPage(self.logger)

        self.stack.addWidget(self.page_initial)
        self.stack.addWidget(self.page_connect)
        self.stack.addWidget(self.page_add)
        self.stack.addWidget(self.page_reflines)
        self.stack.addWidget(self.page_laser)
        
        # Set initial page
        self.stack.setCurrentWidget(self.page_initial)

    def go_to_connection(self):
        self.stack.setCurrentWidget(self.page_connect)

    def go_to_add(self):
        self.stack.setCurrentWidget(self.page_add)

    def go_to_initial_page(self):
        self.stack.setCurrentWidget(self.page_initial)
        self.page_initial.reset_state()

    def go_to_reference_lines(self):
        self.stack.setCurrentWidget(self.page_reflines)

    def go_to_laser_controller(self):
        self.stack.setCurrentWidget(self.page_laser)
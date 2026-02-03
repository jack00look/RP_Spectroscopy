from .service_manager import ServiceManager
from PySide6.QtCore import QThread
from gui.main_window import MainWindow
import logging
import os
from .logging_config import setup_logging


class GeneralManager:
    def __init__(self, config=None):
        # Load config robustly
        self.cfg = config
        if not self.cfg:
             # Fallback: Assume board_list is in the script folder if config fails
            print("WARNING: Using default config fallback.", flush=True)
            self.cfg = {'paths': {'hardware': './', 'logs': './logs'}}

        # Setup Logging
        log_path = self.cfg.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'general_manager.log')
        self.logger = logging.getLogger('GeneralManager')
        setup_logging(self.logger, log_file)
        self.logger.info("GeneralManager starting up...")

        self.services = ServiceManager(self.cfg)
        self.logger.info("ServiceManager initialized.")
        self.svc_thread = QThread()
        self.services.moveToThread(self.svc_thread)
        self.logger.info("ServiceManager moved to thread.")

        self.window = MainWindow()
        self.logger.info("MainWindow initialized.")

        # Wiring
        self.window.page_connect.sig_request_add_page.connect(self.window.go_to_add)
        self.window.page_add.sig_request_back.connect(self.window.go_to_connection)
        self.window.page_add.sig_submit_board.connect(self.services.add_board)
        self.window.page_add.sig_submit_board.connect(self.window.go_to_connection)
        self.window.page_connect.sig_request_remove.connect(self.services.remove_board)
        self.window.page_connect.sig_request_refresh.connect(self.services.load_boards)
        self.window.page_connect.sig_request_connect.connect(self.connect_to_board)
        self.services.sig_board_list_updated.connect(self.window.page_connect.update_table)
        
        # New Navigation Wiring
        self.window.page_initial.sig_request_reference_lines.connect(self.window.go_to_reference_lines)
        self.window.page_initial.sig_request_connection.connect(self.window.go_to_connection)
        self.window.page_reflines.sig_request_back.connect(self.window.go_to_initial_page)

        self.window.page_connect.sig_request_back.connect(self.window.go_to_initial_page)
        
        # Inject ServiceManager into ReferenceLinesPage
        self.window.page_reflines.set_service_manager(self.services)
        self.logger.info("ServiceManager injected into ReferenceLinesPage.")

        self.svc_thread.start()
        self.logger.info("ServiceManager thread started.")
        
        # Trigger initial load via signal (Thread safe practice)
        # We need a temporary signal or just call it directly since loop hasn't started yet
        self.services.load_boards() 
        
        self.window.show()

    def connect_to_board(self, board_name):
        print(f"MANAGER: Connecting to {board_name}...", flush=True)

    def cleanup(self):
        self.logger.info("GeneralManager shutting down...")
        self.svc_thread.quit()
        self.svc_thread.wait()
        self.logger.info("GeneralManager shut down.")
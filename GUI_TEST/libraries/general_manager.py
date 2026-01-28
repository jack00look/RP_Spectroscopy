from .service_manager import ServiceManager
from PySide6.QtCore import QThread
from gui.main_window import MainWindow


class GeneralManager:
    def __init__(self, config=None):
        # Load config robustly
        self.cfg = config
        if not self.cfg:
             # Fallback: Assume board_list is in the script folder if config fails
            print("WARNING: Using default config fallback.", flush=True)
            self.cfg = {'paths': {'hardware': './'}}

        self.services = ServiceManager(self.cfg)
        self.svc_thread = QThread()
        self.services.moveToThread(self.svc_thread)

        self.window = MainWindow()

        # Wiring
        self.window.page_connect.sig_request_add_page.connect(self.window.go_to_add)
        self.window.page_add.sig_request_back.connect(self.window.go_to_connection)
        self.window.page_add.sig_submit_board.connect(self.services.add_board)
        self.window.page_add.sig_submit_board.connect(self.window.go_to_connection)
        self.window.page_connect.sig_request_remove.connect(self.services.remove_board)
        self.window.page_connect.sig_request_refresh.connect(self.services.load_boards)
        self.window.page_connect.sig_request_connect.connect(self.connect_to_board)
        self.services.sig_board_list_updated.connect(self.window.page_connect.update_table)

        self.svc_thread.start()
        
        # Trigger initial load via signal (Thread safe practice)
        # We need a temporary signal or just call it directly since loop hasn't started yet
        self.services.load_boards() 
        
        self.window.show()

    def connect_to_board(self, board_name):
        print(f"MANAGER: Connecting to {board_name}...", flush=True)

    def cleanup(self):
        self.svc_thread.quit()
        self.svc_thread.wait()
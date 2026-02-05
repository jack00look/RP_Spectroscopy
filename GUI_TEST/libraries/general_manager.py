from .service_manager import ServiceManager
from .laser_manager import LaserManager
from PySide6.QtCore import QThread, Slot
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

    def connect_to_board(self, board):
        board_name = board.get('name', 'Unknown')
        self.logger.info(f"Connecting to {board_name}...")

        self.laser = LaserManager(self.cfg, board)
        self.logger.info("LaserManager initialized.")
        self.lsr_thread = QThread()
        self.laser.moveToThread(self.lsr_thread)
        self.logger.info("LaserManager moved to thread.")
        
        # Connect started signal to setup method to ensure it runs in the thread
        self.lsr_thread.started.connect(self.laser.setup)
        
        # Connect connection signal to GUI update
        # We need Qt.QueuedConnection because signal is from thread, slot is in GUI thread
        # In PySide/Qt, default connection type is AutoConnection which handles this automatically
        self.laser.sig_connected.connect(self.window.page_laser.set_connected_state)
        self.laser.sig_connected.connect(self.on_laser_connected)
        
        self.lsr_thread.start()
        self.logger.info("LaserManager thread started.")
        
        # Switch to Laser Controller Page and set to connecting state
        self.window.page_laser.set_connecting_state()
        self.window.go_to_laser_controller()

    @Slot()
    def on_laser_connected(self):
        """
        Called when laser manager is fully connected.
        Populate the parameters table.
        """
        # We access the interface params. 
        # Note: self.laser.interface might be in use by the thread.
        # But reading the dict of params structure is likely fine once setup is done.
        
        if self.laser.interface and hasattr(self.laser.interface, 'writeable_params'):
            params = self.laser.interface.writeable_params
            self.window.page_laser.page_parameters.load_parameters(params)
            self.logger.info("Parameters loaded into GUI.")
        else:
            self.logger.warning("Could not load parameters: Interface not ready or no params.")

    def cleanup(self):
        self.logger.info("GeneralManager shutting down...")
        self.svc_thread.quit()
        self.svc_thread.wait()
        
        if hasattr(self, 'lsr_thread') and self.lsr_thread.isRunning():
            # Stop the timer before quitting the thread
            # We use QMetaObject.invokeMethod to call the slot in the thread context
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(self.laser, "stop", Qt.BlockingQueuedConnection)
            
            self.lsr_thread.quit()
            self.lsr_thread.wait()
            
        self.logger.info("GeneralManager shut down.")
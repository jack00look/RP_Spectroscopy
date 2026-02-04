from .logging_config import setup_logging

from PySide6.QtCore import QObject, Signal, Slot
import os

class LaserManager(QObject):
    def __init__(self, config, board):
        super().__init__()

        self.cfg = config
        self.board = board

        self.interface = None 
        self.controller = None 
        self.timer = None
        
        # Setup Logging
        log_path = self.cfg.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'laser_manager.log')
        self.logger = logging.getLogger('LaserManager')
        setup_logging(self.logger, log_file)

        self.logger.info("LaserManager initialized.")

    @Slot()
    def setup(self):
        """
        Sets up the HardwareInterface and the Controller
        """
        try:
            self.interface = HardwareInterface(self.cfg, self.board)
            self.controller = Controller(self.interface)

            #Setup internal Timer for the control loop
            self.timer = QTimer()
            self.timer.timeout.connect(self.run_control_loop)
            self.timer.start(self.cfg['app']['update_interval_ms'])

        except Exception as e:
            self.logger.error(f"Failed to initialize HardwareInterface and Controller: {e}")

    @Slot()
    def control_loop(self):
        """
        Runs every x seconds and decides what to do
        based on the current state of the Finite State Machine.
        """

        self.logger.info("Control loop running...")


        
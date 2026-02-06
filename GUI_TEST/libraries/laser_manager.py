from .logging_config import setup_logging
from .interface import HardwareInterface
from .controller import LockController
from PySide6.QtCore import QObject, Signal, Slot, QTimer
import os
import logging

class LaserManager(QObject):
    sig_connected = Signal()
    sig_parameters_updated = Signal()

    def __init__(self, config, board):
        super().__init__()
        # ... (rest of init)


        self.cfg = config
        self.board = board

        self.interface = None 
        self.controller = None 
        self.timer = None

        self.state = "IDLE"
        
        # Setup Logging
        log_path = self.cfg.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'laser_manager.log')
        self.logger = logging.getLogger('LaserManager')
        setup_logging(self.logger, log_file)

        self.logger.info("LaserManager initialized.")

    @Slot()
    def stop(self):
        """
        Stops the control loop timer
        """
        if self.timer and self.timer.isActive():
            self.timer.stop()
            self.logger.info("Control loop timer stopped.")

    @Slot()
    def setup(self):
        """
        Sets up the HardwareInterface and the Controller
        """
        try:
            self.interface = HardwareInterface(self.cfg, self.board)
            self.controller = LockController(self.interface)

            #Setup internal Timer for the control loop
            self.timer = QTimer()
            self.timer.timeout.connect(self.control_loop)
            self.timer.start(self.cfg['app']['update_interval_ms'])
            
            self.logger.info("LaserManager setup complete. Control loop started.")
            self.sig_connected.emit()

        except Exception as e:
            self.logger.error(f"Failed to initialize HardwareInterface and Controller: {e}")

    @Slot()
    def control_loop(self):
        """
        Runs every x seconds and decides what to do
        based on the current state of the Finite State Machine.
        """
        if self.state == "IDLE":
            self.interface.start_sweep()
            self.state = "SWEEP"
        elif self.state == "SWEEP":
            self.get_and_send_sweep()
        else:
            self.logger.warning(f"Unknown state: {self.state}")

    @Slot()
    def get_and_send_sweep(self):
        pass

    @Slot()
    def restore_default_parameters(self):
        """
        Reloads the default parameters from the config file and updates the interface.
        """
        if self.interface:
            try:
                self.interface.load_default_RedPitaya_parameters()
                self.logger.info("Default parameters restored.")
                self.sig_parameters_updated.emit()
            except Exception as e:
                self.logger.error(f"Failed to restore default parameters: {e}")

    @Slot()
    def save_parameters(self):
        """
        Saves current parameters back to the YAML file.
        """
        if self.interface:
            try:
                self.interface.save_RedPitaya_parameters_before_closing()
            except Exception as e:
                self.logger.error(f"Failed to save parameters: {e}")
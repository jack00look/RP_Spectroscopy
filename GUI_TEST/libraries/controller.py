from .logging_config import setup_logging
import logging
import os

class LockController():
    """
    This class manages the high level lock algorithm.
    """

    def __init__(self, interface):
        self.interface = interface
        # Access config via interface if not passed directly
        self.config = self.interface.config

        # Setup Logging
        log_path = self.config.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'controller.log')
        self.logger = logging.getLogger('Controller')
        setup_logging(self.logger, log_file)


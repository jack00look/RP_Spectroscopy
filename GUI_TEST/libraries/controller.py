from .logging_config import setup_logging

class LockController():
    """
    This class manages the high level lock algorithm.
    """

    def __init__(self, interface):
        self.interface = interface

        # Setup Logging
        log_path = self.config.get('paths', {}).get('logs', './logs')
        log_file = os.path.join(log_path, 'controller.log')
        self.logger = logging.getLogger('Controller')
        setup_logging(self.logger, log_file)

